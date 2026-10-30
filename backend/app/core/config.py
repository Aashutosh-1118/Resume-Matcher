from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required
    database_url: str
    jwt_secret: str
    hr_invite_code: str

    # AI
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    llm_seed: int = 42

    # Auth
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    login_max_attempts: int = 8
    login_window_seconds: int = 900

    # Web
    cors_origins: str = "http://localhost:5173"

    # Limits
    max_batch_size: int = 10
    max_upload_mb: int = 5
    max_resume_chars: int = 15000
    max_pdf_pages: int = 15
    batch_workers: int = 3
    student_daily_limit: int = 20
    hr_daily_limit: int = 200

    @field_validator("jwt_secret")
    @classmethod
    def _secret_long_enough(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("JWT_SECRET must be at least 16 characters long")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
