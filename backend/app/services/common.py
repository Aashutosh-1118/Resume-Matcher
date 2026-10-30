"""Helpers shared by the student and HR routers."""
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Analysis, JobDescription, User
from app.services import engine
from app.services.documents import DocumentError, extract_text, read_upload

MIN_JD_CHARS = 50


def resolve_jd_text(jd_text: str | None, jd_file: UploadFile | None) -> str:
    """Take the JD from pasted text or an uploaded file."""
    text = (jd_text or "").strip()
    if not text and jd_file is not None and jd_file.filename:
        name, data = read_upload(jd_file)
        text = extract_text(name, data)
    if len(text) < MIN_JD_CHARS:
        raise HTTPException(
            status_code=422,
            detail="Please provide a job description (paste the text or upload a file with at least a few lines).",
        )
    return text


def get_or_create_jd(db: Session, user: User, text: str, title: str | None = None) -> JobDescription:
    """Reuse an already parsed JD when the same text was submitted before, so we skip one AI call."""
    text_hash = engine.hash_text(text)
    existing = db.scalar(
        select(JobDescription).where(
            JobDescription.owner_id == user.id, JobDescription.text_hash == text_hash
        )
    )
    if existing:
        if title and title.strip() and existing.title != title.strip():
            existing.title = title.strip()[:200]
            db.commit()
        return existing

    job = engine.parse_jd(text)
    jd = JobDescription(
        owner_id=user.id,
        title=(title or job.role or "Untitled role").strip()[:200],
        raw_text=text[: settings.max_resume_chars],
        text_hash=text_hash,
        parsed=job.model_dump(),
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return jd


def start_of_today_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def check_quota(db: Session, user: User, wanted: int = 1) -> None:
    """Daily limit per account, so one user cannot use up the shared AI key."""
    limit = settings.hr_daily_limit if user.role == "hr" else settings.student_daily_limit
    used = db.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.owner_id == user.id, Analysis.created_at >= start_of_today_utc()
        )
    ) or 0
    if used + wanted > limit:
        left = max(0, limit - used)
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached ({limit} analyses per day). You have {left} left today.",
        )


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, (DocumentError, engine.EngineError)):
        return str(exc)
    return "Something went wrong while reading this resume."
