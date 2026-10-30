from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from tests.conftest import JD_TEXT, STRONG, auth_headers, make_docx, register


def test_password_hash_roundtrip():
    h = hash_password("Passw0rd!x")
    assert h != "Passw0rd!x"
    assert verify_password("Passw0rd!x", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_token_roundtrip_and_tamper():
    token = create_access_token(5, "hr")
    payload = decode_access_token(token)
    assert payload["sub"] == "5" and payload["role"] == "hr"
    assert decode_access_token(token + "x") is None
    assert decode_access_token("garbage") is None


def test_register_and_login(client):
    res = register(client)
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "student"

    res = client.post("/auth/login", json={"email": "STUDENT@example.com", "password": "Passw0rd!x"})
    assert res.status_code == 200
    token = res.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "student@example.com"


def test_duplicate_email_rejected(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_weak_or_bad_input_rejected(client):
    assert register(client, password="short").status_code == 422
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, password="a" * 80).status_code == 422


def test_hr_needs_invite_code(client):
    assert register(client, role="hr").status_code == 403
    assert register(client, role="hr", invite="wrong").status_code == 403
    assert register(client, role="hr", invite="hr-test-code").status_code == 201


def test_wrong_password_and_unknown_user(client):
    register(client)
    assert client.post("/auth/login", json={"email": "student@example.com", "password": "nope-nope"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"}).status_code == 401


def test_login_lockout_after_repeated_failures(client):
    register(client)
    bad = {"email": "student@example.com", "password": "wrong-password"}
    for _ in range(8):
        assert client.post("/auth/login", json=bad).status_code == 401
    assert client.post("/auth/login", json=bad).status_code == 429
    # Even the right password is blocked while locked.
    good = {"email": "student@example.com", "password": "Passw0rd!x"}
    assert client.post("/auth/login", json=good).status_code == 429


def test_protected_routes_need_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/student/history").status_code == 401
    assert client.get("/hr/jds").status_code == 401
    assert client.get("/hr/jds", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_roles_are_separated(client, student, hr):
    assert client.get("/hr/jds", headers=student).status_code == 403
    assert client.get("/student/history", headers=hr).status_code == 403


def test_delete_account_removes_data(client):
    headers = auth_headers(client, "gone@example.com", "student")
    res = client.post(
        "/student/analyze",
        headers=headers,
        data={"jd_text": JD_TEXT},
        files={"resume": ("cv.docx", make_docx(STRONG), "application/octet-stream")},
    )
    assert res.status_code == 200, res.text
    assert client.delete("/auth/me", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/login", json={"email": "gone@example.com", "password": "Passw0rd!x"}).status_code == 401
