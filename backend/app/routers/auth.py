import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ratelimit import FailureLimiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Analysis, Batch, JobDescription, User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

login_limiter = FailureLimiter(settings.login_max_attempts, settings.login_window_seconds)

# Hashed once at startup so a login for an unknown email takes the same time
# as one for a real email (stops account guessing by timing).
_DUMMY_HASH = hash_password("not-a-real-password")


def _token_response(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if data.role == "hr":
        supplied = (data.invite_code or "").encode("utf-8")
        expected = settings.hr_invite_code.encode("utf-8")
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=403, detail="Invalid HR invite code.")

    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    key = f"{request.client.host if request.client else 'unknown'}:{email}"
    login_limiter.check(key)

    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(data.password, user.hashed_password if user else _DUMMY_HASH)
    if not user or not ok:
        login_limiter.hit(key)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    login_limiter.reset(key)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.delete("/me", status_code=204)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete the account and everything saved under it."""
    db.execute(delete(Analysis).where(Analysis.owner_id == user.id))
    db.execute(delete(Batch).where(Batch.owner_id == user.id))
    db.execute(delete(JobDescription).where(JobDescription.owner_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
