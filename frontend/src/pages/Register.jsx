import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorMessage } from "../api";
import { homePath, useAuth } from "../AuthContext";
import { Alert } from "../components/ui";

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "student", invite_code: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePath(user)} replace />;

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const payload = {
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
      };
      if (form.role === "hr") payload.invite_code = form.invite_code;
      const u = await register(payload);
      navigate(homePath(u), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-card card" onSubmit={submit}>
        <h1>Create your account</h1>
        <div className="role-picker" role="radiogroup" aria-label="Account type">
          <button type="button" role="radio" aria-checked={form.role === "student"} className={form.role === "student" ? "role-opt selected" : "role-opt"} onClick={() => setForm({ ...form, role: "student" })}>
            <strong>I'm a student</strong>
            <span>Check my resume against a job</span>
          </button>
          <button type="button" role="radio" aria-checked={form.role === "hr"} className={form.role === "hr" ? "role-opt selected" : "role-opt"} onClick={() => setForm({ ...form, role: "hr" })}>
            <strong>I'm in HR</strong>
            <span>Screen many resumes at once</span>
          </button>
        </div>
        <Alert>{error}</Alert>
        <label>
          Full name
          <input value={form.full_name} onChange={set("full_name")} required maxLength={120} autoComplete="name" />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={set("email")} required autoComplete="email" />
        </label>
        <label>
          Password
          <input type="password" value={form.password} onChange={set("password")} required minLength={8} maxLength={72} autoComplete="new-password" />
          <span className="hint">At least 8 characters.</span>
        </label>
        {form.role === "hr" && (
          <label>
            HR invite code
            <input value={form.invite_code} onChange={set("invite_code")} required autoComplete="off" />
            <span className="hint">Ask the person who runs this app for the code.</span>
          </label>
        )}
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Creating..." : "Create account"}</button>
        <p className="muted small center">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
