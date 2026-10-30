from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_role
from app.models import Analysis, JobDescription, User
from app.services import engine
from app.services.common import check_quota, get_or_create_jd, resolve_jd_text
from app.services.documents import extract_text, read_upload
from app.services.serializers import analysis_detail, analysis_summary

router = APIRouter(prefix="/student", tags=["student"])

student_only = require_role("student")


@router.post("/analyze")
def analyze(
    resume: UploadFile = File(...),
    jd_text: str | None = Form(None),
    jd_file: UploadFile | None = File(None),
    jd_title: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(student_only),
):
    """Score one resume against one job description (runs right away, takes a few seconds)."""
    check_quota(db, user)

    name, data = read_upload(resume)
    resume_text = extract_text(name, data)
    jd_source = resolve_jd_text(jd_text, jd_file)
    jd = get_or_create_jd(db, user, jd_source, jd_title)

    job = engine.JobD.model_validate(jd.parsed)
    result = engine.analyze_resume_text(job, resume_text, name)

    row = Analysis(
        owner_id=user.id,
        jd_id=jd.id,
        batch_id=None,
        filename=name,
        status="done",
        candidate_name=result["candidate"]["name"],
        candidate_email=result["candidate"]["email"],
        score=result["score"],
        details=result["details"],
        parsed_resume=result["parsed_resume"],
        ats_checks=result["ats_checks"],
        flags=result["flags"],
        missing_must_have=[],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return analysis_detail(row, jd.title)


@router.get("/history")
def history(db: Session = Depends(get_db), user: User = Depends(student_only)):
    rows = db.execute(
        select(Analysis, JobDescription.title)
        .join(JobDescription, JobDescription.id == Analysis.jd_id)
        .where(Analysis.owner_id == user.id, Analysis.batch_id.is_(None))
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(100)
    ).all()
    return [analysis_summary(a, title) for a, title in rows]


def _own_analysis(db: Session, user: User, analysis_id: int) -> tuple[Analysis, str]:
    row = db.execute(
        select(Analysis, JobDescription.title)
        .join(JobDescription, JobDescription.id == Analysis.jd_id)
        .where(Analysis.id == analysis_id, Analysis.owner_id == user.id, Analysis.batch_id.is_(None))
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return row[0], row[1]


@router.get("/history/{analysis_id}")
def history_item(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(student_only)):
    analysis, title = _own_analysis(db, user, analysis_id)
    return analysis_detail(analysis, title)


@router.delete("/history/{analysis_id}", status_code=204)
def delete_history_item(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(student_only)):
    analysis, _ = _own_analysis(db, user, analysis_id)
    db.delete(analysis)
    db.commit()
