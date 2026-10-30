import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { Alert, Chips, Spinner, formatDate } from "../components/ui";

export default function HRJobs() {
  const [jds, setJds] = useState(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () =>
    api
      .get("/hr/jds")
      .then((res) => setJds(res.data))
      .catch((err) => setError(errorMessage(err)));

  useEffect(() => {
    load();
  }, []);

  const ready = mode === "paste" ? text.trim().length >= 50 : Boolean(file);

  const create = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const form = new FormData();
      if (mode === "paste") form.append("jd_text", text);
      else form.append("jd_file", file);
      if (title.trim()) form.append("title", title.trim());
      await api.post("/hr/jds", form);
      setText("");
      setFile(null);
      setTitle("");
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (jd) => {
    if (!window.confirm(`Delete "${jd.title}" and all screening results for it?`)) return;
    try {
      await api.delete(`/hr/jds/${jd.id}`);
      setJds((list) => list.filter((j) => j.id !== jd.id));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div>
      <h1>Job descriptions</h1>
      <p className="muted lead">Save a job description once, then screen as many batches of resumes against it as you like.</p>

      <form className="card form-grid" onSubmit={create}>
        <div>
          <div className="seg">
            <button type="button" className={mode === "paste" ? "seg-btn active" : "seg-btn"} onClick={() => setMode("paste")}>Paste text</button>
            <button type="button" className={mode === "file" ? "seg-btn active" : "seg-btn"} onClick={() => setMode("file")}>Upload file</button>
          </div>
          {mode === "paste" ? (
            <label>
              Job description
              <textarea rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the full job description" />
            </label>
          ) : (
            <label>
              File (PDF, DOCX or TXT)
              <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setFile(e.target.files[0] || null)} />
            </label>
          )}
        </div>
        <div>
          <label>
            Title (optional)
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="Leave empty to use the role found in the text" />
          </label>
          <button className="btn btn-primary" disabled={!ready || busy}>{busy ? "Reading the job description..." : "Save job description"}</button>
        </div>
      </form>

      <Alert>{error}</Alert>
      {jds === null && !error && <Spinner label="Loading..." />}
      {jds && jds.length === 0 && <div className="card empty"><p>No job descriptions yet. Add your first one above.</p></div>}

      <div className="stack">
        {(jds || []).map((jd) => (
          <div key={jd.id} className="card jd-card">
            <div className="jd-card-head">
              <div>
                <h3>{jd.title}</h3>
                <p className="muted small">
                  Added {formatDate(jd.created_at)}
                  {jd.parsed.minimum_experience ? ` · ${jd.parsed.minimum_experience}+ years experience` : ""}
                </p>
              </div>
              <div className="row">
                <Link className="btn btn-primary" to={`/hr/batches/new?jd=${jd.id}`}>Screen resumes</Link>
                <button className="btn btn-ghost" onClick={() => remove(jd)}>Delete</button>
              </div>
            </div>
            <h4>Required skills</h4>
            <Chips items={jd.parsed.required_skills} tone="neutral" empty="None found" />
            {jd.parsed.preferred_skills.length > 0 && (
              <>
                <h4>Preferred skills</h4>
                <Chips items={jd.parsed.preferred_skills} tone="soft" />
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
