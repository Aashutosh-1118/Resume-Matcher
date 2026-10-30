from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import Base, SessionLocal, engine as db_engine
from app.routers import auth, hr, student
from app.services.documents import DocumentError
from app.services.engine import EngineError


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=db_engine)
    yield


app = FastAPI(title="Resume Matcher API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DocumentError)
async def document_error_handler(_: Request, exc: DocumentError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(EngineError)
async def engine_error_handler(_: Request, exc: EngineError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


app.include_router(auth.router)
app.include_router(student.router)
app.include_router(hr.router)


@app.get("/health")
def health():
    db_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
