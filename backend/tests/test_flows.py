import time

from tests.conftest import JD_TEXT, STRONG, WEAK, auth_headers, make_docx

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _analyze(client, headers, lines=STRONG, jd=JD_TEXT, name="cv.docx"):
    return client.post(
        "/student/analyze",
        headers=headers,
        data={"jd_text": jd},
        files={"resume": (name, make_docx(lines), DOCX)},
    )


# ---------- student ----------

def test_student_analyze_and_history(client, student):
    res = _analyze(client, student)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["score"] == 100.0
    assert body["details"]["verdict"]
    assert body["ats_checks"]

    history = client.get("/student/history", headers=student).json()
    assert len(history) == 1 and history[0]["score"] == 100.0

    one = client.get(f"/student/history/{body['id']}", headers=student)
    assert one.status_code == 200

    assert client.delete(f"/student/history/{body['id']}", headers=student).status_code == 204
    assert client.get("/student/history", headers=student).json() == []


def test_same_jd_is_parsed_only_once(client, student, monkeypatch):
    from app.services import engine
    from tests.conftest import fake_llm

    jd_calls = []

    def spy(messages, max_retries=4):
        if "TASK:JD_PARSE" in messages[0]["content"]:
            jd_calls.append(1)
        return fake_llm(messages)

    monkeypatch.setattr(engine, "_call_llm", spy)
    _analyze(client, student)
    _analyze(client, student, lines=WEAK)
    assert len(jd_calls) == 1


def test_student_cannot_read_other_students_results(client, student):
    body = _analyze(client, student).json()
    other = auth_headers(client, "other@example.com", "student")
    assert client.get(f"/student/history/{body['id']}", headers=other).status_code == 404
    assert client.delete(f"/student/history/{body['id']}", headers=other).status_code == 404


def test_student_input_errors(client, student):
    assert _analyze(client, student, jd="too short").status_code == 422
    bad = client.post(
        "/student/analyze", headers=student, data={"jd_text": JD_TEXT},
        files={"resume": ("cv.pdf", b"definitely not a pdf", "application/pdf")},
    )
    assert bad.status_code == 422
    assert "PDF" in bad.json()["detail"]
    exe = client.post(
        "/student/analyze", headers=student, data={"jd_text": JD_TEXT},
        files={"resume": ("virus.exe", b"MZ....", "application/octet-stream")},
    )
    assert exe.status_code == 422


def test_student_daily_quota(client, student, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "student_daily_limit", 2)
    assert _analyze(client, student).status_code == 200
    assert _analyze(client, student).status_code == 200
    third = _analyze(client, student)
    assert third.status_code == 429
    assert "Daily limit" in third.json()["detail"]


def test_ai_outage_returns_clean_error(client, student, monkeypatch):
    from app.services import engine

    def down(messages, max_retries=4):
        raise engine.EngineError("The AI service is busy right now. Please try again in a minute.")

    monkeypatch.setattr(engine, "_call_llm", down)
    res = _analyze(client, student)
    assert res.status_code == 502
    assert "busy" in res.json()["detail"]


# ---------- HR ----------

def _create_jd(client, hr, text=JD_TEXT, title="Backend role"):
    res = client.post("/hr/jds", headers=hr, data={"jd_text": text, "title": title})
    assert res.status_code == 201, res.text
    return res.json()


def _batch(client, hr, jd_id, files, must_have=""):
    return client.post(
        "/hr/batches", headers=hr, data={"jd_id": str(jd_id), "must_have": must_have},
        files=[("files", f) for f in files],
    )


def _wait_done(client, hr, batch_id):
    for _ in range(50):
        data = client.get(f"/hr/batches/{batch_id}", headers=hr).json()
        if data["status"] in ("done", "failed"):
            return data
        time.sleep(0.1)
    raise AssertionError("batch did not finish")


def test_jd_crud_and_isolation(client, hr):
    jd = _create_jd(client, hr)
    assert jd["parsed"]["required_skills"] == ["Python", "SQL", "FastAPI"]
    assert client.get("/hr/jds", headers=hr).json()[0]["id"] == jd["id"]
    assert "raw_text" in client.get(f"/hr/jds/{jd['id']}", headers=hr).json()

    other = auth_headers(client, "hr2@example.com", "hr")
    assert client.get(f"/hr/jds/{jd['id']}", headers=other).status_code == 404
    assert client.delete(f"/hr/jds/{jd['id']}", headers=other).status_code == 404

    assert client.delete(f"/hr/jds/{jd['id']}", headers=hr).status_code == 204
    assert client.get("/hr/jds", headers=hr).json() == []


def test_full_batch_flow(client, hr):
    jd = _create_jd(client, hr)
    files = [
        ("weak.docx", make_docx(WEAK), DOCX),
        ("strong.docx", make_docx(STRONG), DOCX),
        ("broken.pdf", b"not a pdf", "application/pdf"),
    ]
    res = _batch(client, hr, jd["id"], files, must_have="Python, Kubernetes")
    assert res.status_code == 202, res.text
    batch_id = res.json()["id"]

    data = _wait_done(client, hr, batch_id)
    assert data["status"] == "done"
    assert data["total"] == 3 and data["completed"] == 2 and data["failed"] == 1

    results = data["results"]
    assert [r["candidate_name"] for r in results[:2]] == ["Asha Rao", "Ben Roy"]
    assert results[0]["rank"] == 1 and results[1]["rank"] == 2
    assert results[0]["score"] > results[1]["score"]
    assert results[2]["status"] == "failed" and results[2]["error"]
    assert results[0]["missing_must_have"] == ["Kubernetes"]
    assert data["stats"]["highest"] == results[0]["score"]
    assert sum(b["count"] for b in data["stats"]["buckets"]) == 2


def test_blind_mode_hides_identity(client, hr):
    jd = _create_jd(client, hr)
    batch_id = _batch(client, hr, jd["id"], [("asha_rao_cv.docx", make_docx(STRONG), DOCX)]).json()["id"]
    _wait_done(client, hr, batch_id)

    blind = client.get(f"/hr/batches/{batch_id}?blind=true", headers=hr).json()
    row = blind["results"][0]
    assert row["candidate_name"] == "Candidate 1"
    assert row["candidate_email"] is None
    assert "asha" not in row["filename"].lower()

    export = client.get(f"/hr/batches/{batch_id}/export?blind=true", headers=hr).text
    assert "Asha" not in export and "asha@example.com" not in export

    detail = client.get(f"/hr/analyses/{row['id']}?blind=true", headers=hr).json()
    assert detail["candidate_name"] == "Candidate 1" and detail["parsed_resume"] is None


def test_csv_export_and_formula_injection_guard(client, hr):
    jd = _create_jd(client, hr)
    evil = ["Name: =HYPERLINK(\"http://evil\")", "Email: evil@example.com", "Skills: Python", "Experience years: 1"]
    batch_id = _batch(client, hr, jd["id"], [("evil.docx", make_docx(evil), DOCX)]).json()["id"]
    _wait_done(client, hr, batch_id)

    res = client.get(f"/hr/batches/{batch_id}/export", headers=hr)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.splitlines()
    assert lines[0].startswith("Rank,Name,Email")
    assert "'=HYPERLINK" in res.text
    assert ",=HYPERLINK" not in res.text


def test_decision_marking(client, hr):
    jd = _create_jd(client, hr)
    batch_id = _batch(client, hr, jd["id"], [("a.docx", make_docx(STRONG), DOCX)]).json()["id"]
    row = _wait_done(client, hr, batch_id)["results"][0]

    res = client.patch(f"/hr/analyses/{row['id']}/decision", headers=hr, json={"decision": "shortlisted"})
    assert res.status_code == 200 and res.json()["decision"] == "shortlisted"
    assert client.get(f"/hr/batches/{batch_id}", headers=hr).json()["results"][0]["decision"] == "shortlisted"
    assert client.patch(f"/hr/analyses/{row['id']}/decision", headers=hr, json={"decision": "maybe"}).status_code == 422
    assert client.patch(f"/hr/analyses/{row['id']}/decision", headers=hr, json={"decision": None}).json()["decision"] is None


def test_hr_data_is_private_between_accounts(client, hr):
    jd = _create_jd(client, hr)
    batch_id = _batch(client, hr, jd["id"], [("a.docx", make_docx(STRONG), DOCX)]).json()["id"]
    row = _wait_done(client, hr, batch_id)["results"][0]

    other = auth_headers(client, "hr2@example.com", "hr")
    assert client.get(f"/hr/batches/{batch_id}", headers=other).status_code == 404
    assert client.get(f"/hr/batches/{batch_id}/export", headers=other).status_code == 404
    assert client.get(f"/hr/analyses/{row['id']}", headers=other).status_code == 404
    assert client.patch(f"/hr/analyses/{row['id']}/decision", headers=other, json={"decision": "rejected"}).status_code == 404
    assert client.delete(f"/hr/batches/{batch_id}", headers=other).status_code == 404
    assert _batch(client, other, jd["id"], [("a.docx", make_docx(STRONG), DOCX)]).status_code == 404
    assert client.get("/hr/batches", headers=other).json() == []


def test_batch_limits(client, hr, monkeypatch):
    from app.core.config import settings

    jd = _create_jd(client, hr)
    monkeypatch.setattr(settings, "max_batch_size", 2)
    three = [(f"{i}.docx", make_docx(STRONG), DOCX) for i in range(3)]
    res = _batch(client, hr, jd["id"], three)
    assert res.status_code == 422 and "up to 2" in res.json()["detail"]

    assert _batch(client, hr, jd["id"], [("a.docx", make_docx(STRONG), DOCX)], must_have=",".join(f"s{i}" for i in range(11))).status_code == 422

    monkeypatch.setattr(settings, "hr_daily_limit", 1)
    two = [(f"{i}.docx", make_docx(STRONG), DOCX) for i in range(2)]
    assert _batch(client, hr, jd["id"], two).status_code == 429


def test_one_bad_resume_does_not_stop_the_batch(client, hr, monkeypatch):
    from app.services import engine
    from tests.conftest import fake_llm

    def flaky(messages, max_retries=4):
        if "Ben Roy" in messages[-1]["content"] and "TASK:RESUME_PARSE" in messages[0]["content"]:
            raise engine.EngineError("The AI returned an unreadable answer. Please try again.")
        return fake_llm(messages)

    monkeypatch.setattr(engine, "_call_llm", flaky)
    jd = _create_jd(client, hr)
    batch_id = _batch(client, hr, jd["id"], [("w.docx", make_docx(WEAK), DOCX), ("s.docx", make_docx(STRONG), DOCX)]).json()["id"]
    data = _wait_done(client, hr, batch_id)
    assert data["status"] == "done" and data["completed"] == 1 and data["failed"] == 1
    failed = [r for r in data["results"] if r["status"] == "failed"][0]
    assert "unreadable" in failed["error"]


def test_delete_batch_and_students_cannot_use_hr_routes(client, hr, student):
    jd = _create_jd(client, hr)
    batch_id = _batch(client, hr, jd["id"], [("a.docx", make_docx(STRONG), DOCX)]).json()["id"]
    _wait_done(client, hr, batch_id)
    assert client.delete(f"/hr/batches/{batch_id}", headers=hr).status_code == 204
    assert client.get(f"/hr/batches/{batch_id}", headers=hr).status_code == 404
    assert client.get(f"/hr/batches/{batch_id}", headers=student).status_code == 403


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "db": True}
