from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)
    role: Literal["student", "hr"]
    invite_code: str | None = None

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, v: str) -> str:
        # bcrypt only reads the first 72 bytes.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password is too long (72 bytes maximum).")
        if v.strip() != v or not v.strip():
            raise ValueError("Password must not start or end with spaces.")
        return v

    @field_validator("full_name")
    @classmethod
    def _name_clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name is required.")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DecisionIn(BaseModel):
    decision: Literal["shortlisted", "rejected"] | None = None
