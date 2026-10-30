from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.deps import require_role
from app.models import Analysis, Batch, JobDescription, User, utcnow
from app.schemas import DecisionIn
from app.services import engine
from app.services.common import check_quota, friendly_error, get_or_create_jd, resolve_jd_text
from app.services.documents import extract_text, read_upload
from app.services.serializers import analysis_detail, batch_summary, iso, results_to_csv

router = APIRouter(prefix="/hr", tags=["hr"])

hr_only = require_role("hr")


# ---------------------------------------------------------------------
# Job descriptions
# ---------------------------------------------------------------------

def _jd_out(jd: JobDescription, with_text: bool = False) -> dict:
    out = {
        "id": jd.id,
        "title": jd.title,
        "parsed": jd.parsed,
        "created_at": iso(jd.created_at),
    }
    if with_text:
        out["raw_text"] = jd.raw_text
    return out


def _own_jd(db: Session, user: User, jd_id: int) -> JobDescription:
    jd = db.scalar(select(JobDescription).where(JobDescription.id == jd_id, JobDescription.owner_id == user.id))
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found.")
    return jd


@router.post("/jds", status_code=201)
def create_jd(
    jd_text: str | None = Form(None),
    jd_file: UploadFile | None = File(None),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(hr_only),
):
    text = resolve_jd_text(jd_text, jd_file)
    jd = get_or_create_jd(db, user, text, title)
    return _jd_out(jd)


@router.get("/jds")
def list_jds(db: Session = Depends(get_db), user: User = Depends(hr_only)):
    rows = db.scalars(
        select(JobDescription).where(JobDescription.owner_id == user.id).order_by(JobDescription.created_at.desc())
    ).all()
    return [_jd_out(jd) for jd in rows]


@router.get("/jds/{jd_id}")
def get_jd(jd_id: int, db: Session = Depends(get_db), user: User = Depends(hr_only)):
    return _jd_out(_own_jd(db, user, jd_id), with_text=True)


@router.delete("/jds/{jd_id}", status_code=204)
def delete_jd(jd_id: int, db: Session = Depends(get_db), user: User = Depends(hr_only)):
    jd = _own_jd(db, user, jd_id)
    db.execute(delete(Analysis).where(Analysis.jd_id == jd.id))
    db.execute(delete(Batch).where(Batch.jd_id == jd.id))
    db.delete(jd)
    db.commit()


# ---------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------

def _parse_must_have(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    cleaned = engine._dedupe([p[:60] for p in parts if p])
    if len(cleaned) > 10:
        raise HTTPException(status_code=422, detail="Please give at most 10 must-have skills.")
    return cleaned


def process_batch(batch_id: int, items: list[tuple[int, str, bytes]]) -> None:
    """Runs in the background after the upload request has returned.

    The AI calls run in a small thread pool. All database writes happen in this
    one thread, so no database session is ever shared between threads.
    """
    db = SessionLocal()
    try:
        batch = db.get(Batch, batch_id)
        jd = db.get(JobDescription, batch.jd_id)
        job = engine.JobD.model_validate(jd.parsed)
        must_have = list(batch.must_have or [])

        batch.status = "running"
        db.commit()

        def work(item):
            analysis_id, filename, data = item
            try:
                text = extract_text(filename, data)
                return analysis_id, engine.analyze_resume_text(job, text, filename, must_have), None
            except Exception as exc:  # one bad resume must not stop the batch
                return analysis_id, None, friendly_error(exc)

        with ThreadPoolExecutor(max_workers=max(1, settings.batch_workers)) as pool:
            futures = [pool.submit(work, item) for item in items]
            for future in as_completed(futures):
                analysis_id, result, error = future.result()
                row = db.get(Analysis, analysis_id)
                if error or result is None:
                    row.status = "failed"
                    row.error = error
                    batch.failed += 1
                else:
                    row.status = "done"
                    row.candidate_name = result["candidate"]["name"]
                    row.candidate_email = result["candidate"]["email"]
                    row.score = result["score"]
                    row.details = result["details"]
                    row.parsed_resume = result["parsed_resume"]
                    row.ats_checks = result["ats_checks"]
                    row.flags = result["flags"]
                    row.missing_must_have = result["missing_must_have"]
                    batch.completed += 1
                db.commit()

        batch.status = "done"
        batch.finished_at = utcnow()
        db.commit()
    except Exception:
        db.rollback()
        batch = db.get(Batch, batch_id)
        if batch:
            batch.status = "failed"
            batch.finished_at = utcnow()
            db.commit()
    finally:
        db.close()


@router.post("/batches", status_code=202)
def create_batch(
    background: BackgroundTasks,
    jd_id: int = Form(...),
    must_have: str = Form(""),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(hr_only),
):
    if not files:
        raise HTTPException(status_code=422, detail="Please upload at least one resume.")
    if len(files) > settings.max_batch_size:
        raise HTTPException(
            status_code=422,
            detail=f"You can screen up to {settings.max_batch_size} resumes at a time.",
        )

    jd = _own_jd(db, user, jd_id)
    must = _parse_must_have(must_have)
    check_quota(db, user, wanted=len(files))

    batch = Batch(owner_id=user.id, jd_id=jd.id, status="pending", total=len(files), must_have=must)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    to_process: list[tuple[int, str, bytes]] = []
    for upload in files:
        try:
            name, data = read_upload(upload)
            error = None
            extract_text(name, data)  # quick check so obviously bad files fail right away
        except Exception as exc:
            name = (upload.filename or "file")[:255]
            data, error = b"", friendly_error(exc)

        row = Analysis(
            owner_id=user.id,
            jd_id=jd.id,
            batch_id=batch.id,
            filename=name[:255],
            status="failed" if error else "pending",
            error=error,
        )
        db.add(row)
        db.flush()
        if error:
            batch.failed += 1
        else:
            to_process.append((row.id, name, data))

    if not to_process:
        batch.status = "done"
        batch.finished_at = utcnow()
    db.commit()

    if to_process:
        background.add_task(process_batch, batch.id, to_process)
    return batch_summary(batch, jd.title)


def _own_batch(db: Session, user: User, batch_id: int) -> tuple[Batch, str]:
    row = db.execute(
        select(Batch, JobDescription.title)
        .join(JobDescription, JobDescription.id == Batch.jd_id)
        .where(Batch.id == batch_id, Batch.owner_id == user.id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return row[0], row[1]


@router.get("/batches")
def list_batches(db: Session = Depends(get_db), user: User = Depends(hr_only)):
    rows = db.execute(
        select(Batch, JobDescription.title)
        .join(JobDescription, JobDescription.id == Batch.jd_id)
        .where(Batch.owner_id == user.id)
        .order_by(Batch.created_at.desc(), Batch.id.desc())
        .limit(100)
    ).all()
    return [batch_summary(b, title) for b, title in rows]


def _ranked_results(db: Session, batch: Batch, jd_title: str, blind: bool) -> list[dict]:
    rows = db.scalars(select(Analysis).where(Analysis.batch_id == batch.id).order_by(Analysis.id)).all()
    # Blind labels follow upload order, so they stay stable between page refreshes.
    labels = {r.id: f"Candidate {i}" for i, r in enumerate(rows, start=1)}
    items = [analysis_detail(r, jd_title, blind=blind, label=labels[r.id]) for r in rows]

    def sort_key(item):
        done = item["status"] == "done"
        return (0 if done else 1, -(item["score"] or 0), item["id"])

    items.sort(key=sort_key)
    for rank, item in enumerate((i for i in items if i["status"] == "done"), start=1):
        item["rank"] = rank
    return items


def _stats(results: list[dict]) -> dict:
    scores = [r["score"] for r in results if r["status"] == "done" and r["score"] is not None]
    buckets = [0] * 5  # 0-19, 20-39, 40-59, 60-79, 80-100
    for s in scores:
        buckets[min(4, int(s // 20))] += 1
    labels = ["0-19", "20-39", "40-59", "60-79", "80-100"]
    return {
        "average": round(sum(scores) / len(scores), 1) if scores else None,
        "highest": max(scores) if scores else None,
        "lowest": min(scores) if scores else None,
        "buckets": [{"range": l, "count": c} for l, c in zip(labels, buckets)],
    }


@router.get("/batches/{batch_id}")
def get_batch(
    batch_id: int,
    blind: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(hr_only),
):
    batch, title = _own_batch(db, user, batch_id)
    results = _ranked_results(db, batch, title, blind)
    # The big parsed resume is only sent for a single candidate, not in the list.
    for r in results:
        r["parsed_resume"] = None
    out = batch_summary(batch, title)
    out["results"] = results
    out["stats"] = _stats(results)
    out["blind"] = blind
    return out


@router.get("/batches/{batch_id}/export")
def export_batch(
    batch_id: int,
    blind: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(hr_only),
):
    batch, title = _own_batch(db, user, batch_id)
    results = [r for r in _ranked_results(db, batch, title, blind) if r["status"] == "done"]
    csv_text = results_to_csv(results)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="shortlist_batch_{batch.id}.csv"'},
    )


@router.delete("/batches/{batch_id}", status_code=204)
def delete_batch(batch_id: int, db: Session = Depends(get_db), user: User = Depends(hr_only)):
    batch, _ = _own_batch(db, user, batch_id)
    db.execute(delete(Analysis).where(Analysis.batch_id == batch.id))
    db.delete(batch)
    db.commit()


# ---------------------------------------------------------------------
# Single candidate
# ---------------------------------------------------------------------

def _own_hr_analysis(db: Session, user: User, analysis_id: int) -> tuple[Analysis, str]:
    row = db.execute(
        select(Analysis, JobDescription.title)
        .join(JobDescription, JobDescription.id == Analysis.jd_id)
        .where(Analysis.id == analysis_id, Analysis.owner_id == user.id, Analysis.batch_id.is_not(None))
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return row[0], row[1]


@router.get("/analyses/{analysis_id}")
def get_analysis(
    analysis_id: int,
    blind: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(hr_only),
):
    analysis, title = _own_hr_analysis(db, user, analysis_id)
    label = None
    if blind:
        ids = db.scalars(
            select(Analysis.id).where(Analysis.batch_id == analysis.batch_id).order_by(Analysis.id)
        ).all()
        label = f"Candidate {ids.index(analysis.id) + 1}"
    return analysis_detail(analysis, title, blind=blind, label=label)


@router.patch("/analyses/{analysis_id}/decision")
def set_decision(
    analysis_id: int,
    data: DecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(hr_only),
):
    analysis, _ = _own_hr_analysis(db, user, analysis_id)
    analysis.decision = data.decision
    db.commit()
    return {"id": analysis.id, "decision": analysis.decision}
