import { useEffect, useRef, useState } from "react";
import api, { errorMessage } from "../api";
import ResultView from "../components/ResultView";
import { Alert, Spinner } from "../components/ui";

const STEPS = [
  "Reading the job description...",
  "Reading your resume...",
  "Checking each skill...",
  "Working out your score...",
];

export default function StudentAnalyze() {
  const [jdMode, setJdMode] = useState("paste");
  const [jdText, setJdText] = useState("");
  const [jdFile, setJdFile] = useState(null);
  const [jdTitle, setJdTitle] = useState("");
  const [resume, setResume] = useState(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const resultRef = useRef(null);

  // Rotate the progress message while we wait, so the page does not look frozen.
  useEffect(() => {
    if (!busy) return undefined;
    setStep(0);
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 4000);
    return () => clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    if (result && resultRef.current) resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  const ready = resume && (jdMode === "paste" ? jdText.trim().length >= 50 : jdFile);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("resume", resume);
      if (jdMode === "paste") form.append("jd_text", jdText);
      else form.append("jd_file", jdFile);
      if (jdTitle.trim()) form.append("jd_title", jdTitle.trim());
      const { data } = await api.post("/student/analyze", form);
      setResult(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Check your resume against a job</h1>
      <p className="muted lead">
        Add the job description and your resume. You will get a match score, the skills you have and the ones you are missing, and tips to improve.
      </p>

      <form className="card form-grid" onSubmit={submit}>
        <div>
          <div className="seg" role="tablist" aria-label="How to add the job description">
            <button type="button" role="tab" aria-selected={jdMode === "paste"} className={jdMode === "paste" ? "seg-btn active" : "seg-btn"} onClick={() => setJdMode("paste")}>Paste text</button>
            <button type="button" role="tab" aria-selected={jdMode === "file"} className={jdMode === "file" ? "seg-btn active" : "seg-btn"} onClick={() => setJdMode("file")}>Upload file</button>
          </div>
          {jdMode === "paste" ? (
            <label>
              Job description
              <textarea rows={10} value={jdText} onChange={(e) => setJdText(e.target.value)} placeholder="Paste the full job description here" />
              <span className="hint">{jdText.trim().length < 50 ? "Add at least a few lines." : "Looks good."}</span>
            </label>
          ) : (
            <label>
              Job description file (PDF, DOCX or TXT)
              <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setJdFile(e.target.files[0] || null)} />
            </label>
          )}
          <label>
            Job title (optional)
            <input value={jdTitle} onChange={(e) => setJdTitle(e.target.value)} maxLength={200} placeholder="For example: Backend Engineer at Acme" />
          </label>
        </div>

        <div>
          <label>
            Your resume (PDF or DOCX, up to 5 MB)
            <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setResume(e.target.files[0] || null)} />
          </label>
          <p className="muted small">
            Your file is read and then discarded. Only the results are saved to your history.
          </p>
          <button className="btn btn-primary" disabled={!ready || busy}>{busy ? "Analyzing..." : "Analyze my resume"}</button>
        </div>
      </form>

      {busy && <Spinner label={STEPS[step]} />}
      <Alert>{error}</Alert>

      {result && (
        <div ref={resultRef} className="scroll-target">
          <ResultView result={result} />
        </div>
      )}
    </div>
  );
}
