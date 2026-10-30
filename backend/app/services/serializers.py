import csv
import io

from app.models import Analysis, Batch


def iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def analysis_summary(a: Analysis, jd_title: str | None = None) -> dict:
    return {
        "id": a.id,
        "jd_id": a.jd_id,
        "jd_title": jd_title,
        "filename": a.filename,
        "status": a.status,
        "score": a.score,
        "candidate_name": a.candidate_name,
        "created_at": iso(a.created_at),
    }


def analysis_detail(
    a: Analysis,
    jd_title: str | None = None,
    blind: bool = False,
    label: str | None = None,
) -> dict:
    """Full result. In blind mode, anything that could identify the candidate is hidden."""
    name = a.candidate_name
    email = a.candidate_email
    filename = a.filename
    resume = a.parsed_resume
    if blind:
        name = label or "Candidate"
        email = None
        filename = (label or "Candidate").lower().replace(" ", "_")
        resume = None
    return {
        "id": a.id,
        "jd_id": a.jd_id,
        "jd_title": jd_title,
        "batch_id": a.batch_id,
        "filename": filename,
        "status": a.status,
        "error": a.error,
        "candidate_name": name,
        "candidate_email": email,
        "score": a.score,
        "details": a.details,
        "parsed_resume": resume,
        "ats_checks": a.ats_checks,
        "flags": a.flags or [],
        "missing_must_have": a.missing_must_have or [],
        "decision": a.decision,
        "created_at": iso(a.created_at),
    }


def batch_summary(b: Batch, jd_title: str | None = None) -> dict:
    return {
        "id": b.id,
        "jd_id": b.jd_id,
        "jd_title": jd_title,
        "status": b.status,
        "total": b.total,
        "completed": b.completed,
        "failed": b.failed,
        "must_have": b.must_have or [],
        "created_at": iso(b.created_at),
        "finished_at": iso(b.finished_at),
    }


def _csv_safe(value) -> str:
    """Stop spreadsheet formula injection: a cell starting with = + - @ is treated as a formula by Excel."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def results_to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Rank", "Name", "Email", "Score (%)", "Matching skills", "Missing skills",
        "Missing must-have", "Decision", "Verdict", "Flags",
    ])
    for i, r in enumerate(rows, start=1):
        d = r.get("details") or {}
        writer.writerow([
            i,
            _csv_safe(r["candidate_name"] or r["filename"]),
            _csv_safe(r["candidate_email"]),
            r["score"],
            _csv_safe(", ".join(d.get("matching_skills", []))),
            _csv_safe(", ".join(d.get("missing_skills", []))),
            _csv_safe(", ".join(r.get("missing_must_have", []))),
            _csv_safe(r.get("decision") or ""),
            _csv_safe(d.get("verdict", "")),
            _csv_safe(" | ".join(r.get("flags", []))),
        ])
    return out.getvalue()
