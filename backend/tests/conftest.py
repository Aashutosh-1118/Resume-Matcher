import io
import json
import os
import re

# Settings must exist before the app is imported.
# Tests run on in-memory SQLite by default. Set TEST_DATABASE_URL to run them on MySQL instead.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret"
os.environ["HR_INVITE_CODE"] = "hr-test-code"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["HR_DAILY_LIMIT"] = "200"
os.environ["STUDENT_DAILY_LIMIT"] = "20"

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.db.session import Base, engine as db_engine
from app.main import app
from app.routers.auth import login_limiter
from app.services import engine


def _csv_after(prefix: str, text: str) -> list[str]:
    for line in text.splitlines():
        if line.lower().startswith(prefix.lower()):
            return [p.strip() for p in line.split(":", 1)[1].split(",") if p.strip()]
    return []


def fake_llm(messages, max_retries=4):
    """A stand-in for Groq. It reads simple 'Key: value' lines so tests control the outcome."""
    system = messages[0]["content"]
    user = messages[1]["content"]

    if "TASK:JD_PARSE" in system:
        years = re.search(r"experience:\s*([\d.]+)", user, re.IGNORECASE)
        return json.dumps({
            "role": "Backend Engineer",
            "required_skills": _csv_after("required", user),
            "preferred_skills": _csv_after("preferred", user),
            "minimum_experience": float(years.group(1)) if years else None,
            "education_requirements": [],
            "responsibilities": [],
        })

    if "TASK:RESUME_PARSE" in system:
        name = _csv_after("name", user)
        email = _csv_after("email", user)
        years = re.search(r"years:\s*([\d.]+)", user, re.IGNORECASE)
        return json.dumps({
            "name": name[0] if name else None,
            "email": email[0] if email else None,
            "phone": None,
            "total_experience_years": float(years.group(1)) if years else None,
            "skills": _csv_after("skills", user),
            "experiences": [{"company": "Acme", "role": "Dev", "description": user[:300], "skills_used": []}],
            "education": [],
            "projects": [],
            "certifications": [],
        })

    if "TASK:SKILL_ASSESS" in system:
        wanted = json.loads(re.search(r"SKILLS_TO_CHECK = (\[.*\])", user).group(1))
        body = user.split("<resume>", 1)[1].lower()
        skills = [
            {"skill": s, "present": s.lower() in body, "evidence": s if s.lower() in body else ""}
            for s in wanted
        ]
        return json.dumps({"skills": skills, "verdict": "Reasonable fit for the role.", "tips": ["Add measurable results."]})

    raise AssertionError("Unexpected prompt sent to the LLM")


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(engine, "_call_llm", fake_llm)
    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)
    login_limiter.clear_all()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def make_docx(lines: list[str]) -> bytes:
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf(lines: list[str]) -> bytes:
    """A tiny hand-built one-page PDF, enough to test real PDF text extraction."""
    content = "BT /F1 12 Tf 50 750 Td 14 TL\n" + "\n".join(f"({l}) Tj T*" for l in lines) + "\nET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF".encode()
    return out


def register(client, email="student@example.com", role="student", password="Passw0rd!x", invite=None, name="Test User"):
    body = {"email": email, "password": password, "full_name": name, "role": role}
    if invite:
        body["invite_code"] = invite
    return client.post("/auth/register", json=body)


def auth_headers(client, email="student@example.com", role="student"):
    invite = "hr-test-code" if role == "hr" else None
    res = register(client, email=email, role=role, invite=invite)
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture()
def student(client):
    return auth_headers(client, "student@example.com", "student")


@pytest.fixture()
def hr(client):
    return auth_headers(client, "hr@example.com", "hr")


JD_TEXT = (
    "Backend Engineer at Acme. We build APIs for logistics customers every day.\n"
    "Required: Python, SQL, FastAPI\n"
    "Preferred: Docker, AWS\n"
    "Minimum experience: 2\n"
)

STRONG = [
    "Name: Asha Rao", "Email: asha@example.com",
    "Skills: Python, SQL, FastAPI, Docker, AWS",
    "I built APIs with Python, SQL and FastAPI, deployed with Docker on AWS.",
    "Experience years: 3",
]
WEAK = [
    "Name: Ben Roy", "Email: ben@example.com",
    "Skills: Excel, Word",
    "I handled data entry with Excel.",
    "Experience years: 0.5",
]
