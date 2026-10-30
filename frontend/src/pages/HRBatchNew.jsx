import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api, { errorMessage } from "../api";
import { Alert, Spinner } from "../components/ui";

const MAX_FILES = 10;
const OK_EXT = [".pdf", ".docx", ".txt"];

export default function HRBatchNew() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [jds, setJds] = useState(null);
  const [jdId, setJdId] = useState(params.get("jd") || "");
  const [mustHave, setMustHave] = useState("");
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    api
      .get("/hr/jds")
      .then((res) => {
        setJds(res.data);
        if (!jdId && res.data.length > 0) setJdId(String(res.data[0].id));
      })
      .catch((err) => setError(errorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addFiles = (list) => {
    const incoming = Array.from(list);
    const good = incoming.filter((f) => OK_EXT.some((ext) => f.name.toLowerCase().endsWith(ext)));
    const skipped = incoming.length - good.length;

    const names = new Set(files.map((f) => f.name + f.size));
    const fresh = good.filter((f) => !names.has(f.name + f.size));
    const merged = [...files, ...fresh];

    setFiles(merged.slice(0, MAX_FILES));
    if (skipped > 0) setError(`${skipped} file(s) skipped. Only PDF, DOCX and TXT files are supported.`);
    else if (merged.length > MAX_FILES) setError(`Only the first ${MAX_FILES} resumes are used.`);
    else setError("");
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const form = new FormData();
      form.append("jd_id", jdId);
      form.append("must_have", mustHave);
      files.forEach((f) => form.append("files", f));
      const { data } = await api.post("/hr/batches", form);
      navigate(`/hr/batches/${data.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  if (jds === null && !error) return <Spinner label="Loading..." />;

  if (jds && jds.length === 0) {
    return (
      <div className="card empty">
        <p>Add a job description first, then come back to screen resumes.</p>
        <Link className="btn btn-primary" to="/hr">Add job description</Link>
      </div>
    );
  }

  return (
    <div className="narrow">
      <h1>Screen resumes</h1>
      <form className="card" onSubmit={submit}>
        <label>
          Job description
          <select value={jdId} onChange={(e) => setJdId(e.target.value)} required>
            {(jds || []).map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
        </label>

        <label>
          Must-have skills (optional)
          <input value={mustHave} onChange={(e) => setMustHave(e.target.value)} placeholder="For example: Python, MySQL" />
          <span className="hint">Separate with commas. Candidates missing any of these are flagged, and you can hide them with one click.</span>
        </label>

        <div
          className={dragging ? "dropzone dragging" : "dropzone"}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        >
          <strong>Drop resumes here or click to choose</strong>
          <span className="muted small">PDF, DOCX or TXT, up to {MAX_FILES} files, 5 MB each</span>
          <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.txt" hidden onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
        </div>

        {files.length > 0 && (
          <ul className="file-list">
            {files.map((f, i) => (
              <li key={f.name + f.size}>
                <span>{f.name}</span>
                <span className="muted small">{Math.max(1, Math.round(f.size / 1024))} KB</span>
                <button type="button" className="btn btn-ghost small-btn" onClick={() => setFiles(files.filter((_, idx) => idx !== i))}>Remove</button>
              </li>
            ))}
          </ul>
        )}

        <Alert>{error}</Alert>
        <button className="btn btn-primary" disabled={busy || files.length === 0 || !jdId}>
          {busy ? "Uploading..." : `Start screening ${files.length || ""} resume${files.length === 1 ? "" : "s"}`}
        </button>
        <p className="muted small">Uploaded files are processed and then discarded. Only the analysis results are saved.</p>
      </form>
    </div>
  );
}
