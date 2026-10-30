"""The ORIGINAL scoring method from the Streamlit version, kept only as a baseline.

The model is asked to invent the final percentage itself, and no temperature is
set, so the provider default (more random) applies. Running this next to the new
engine gives honest before/after numbers.
"""
import json

from app.core.config import settings
from app.services import engine


def legacy_score(job: engine.JobD, resume: engine.Resume) -> float:
    prompt = f"""You are an HR recruiter / ATS system.
Compare the candidate's resume with the job description.

JOB DESCRIPTION:
{job.model_dump_json(indent=2)}

CANDIDATE RESUME:
{resume.model_dump_json(indent=2)}

Return JSON: {{"score": number, "details": {{"matching_skills": [], "missing_skills": [], "experience_requirement_met": true, "verdict": ""}}}}
Only consider concrete technical skills. Ignore soft skills.
"score" must be a number from 0 to 100 representing a percentage."""
    response = engine._get_client().chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    score = float(json.loads(response.choices[0].message.content)["score"])
    if 0 < score <= 1:
        score *= 100
    return score
