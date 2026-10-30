import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { errorMessage } from "../api";
import Modal from "../components/Modal";
import ResultView from "../components/ResultView";
import { Alert, Chips, ScoreBar, Spinner } from "../components/ui";

const RUNNING = ["pending", "running"];

export default function HRBatchDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [blind, setBlind] = useState(false);
  const [topN, setTopN] = useState(5);
  const [query, setQuery] = useState("");
  const [hideKnocked, setHideKnocked] = useState(false);
  const [selected, setSelected] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [comparing, setComparing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/hr/batches/${id}`, { params: { blind } });
      setData(res.data);
      setError("");
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [id, blind]);

  useEffect(() => {
    load();
  }, [load]);

  // Keep refreshing while the batch is still being processed.
  const status = data?.status;
  useEffect(() => {
    if (!status || !RUNNING.includes(status)) return undefined;
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [status, load]);

  const results = data?.results || [];
  const done = useMemo(() => results.filter((r) => r.status === "done"), [results]);
  const failed = results.filter((r) => r.status === "failed");
  const hasMustHave = (data?.must_have || []).length > 0;

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return done.filter((r) => {
      if (hideKnocked && (r.missing_must_have || []).length > 0) return false;
      if (!q) return true;
      const hay = [r.candidate_name, r.candidate_email, ...(r.details?.matching_skills || [])].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [done, query, hideKnocked]);

  const setDecision = async (row, decision) => {
    const next = row.decision === decision ? null : decision;
    setData((d) => ({ ...d, results: d.results.map((r) => (r.id === row.id ? { ...r, decision: next } : r)) }));
    try {
      await api.patch(`/hr/analyses/${row.id}/decision`, { decision: next });
    } catch (err) {
      setError(errorMessage(err));
      load();
    }
  };

  const toggleSelect = (rowId) =>
    setSelected((s) => (s.includes(rowId) ? s.filter((x) => x !== rowId) : s.length < 3 ? [...s, rowId] : s));

  const exportCsv = async () => {
    try {
      const res = await api.get(`/hr/batches/${id}/export`, { params: { blind }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `shortlist_batch_${id}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (!data) {
    return error ? <Alert>{error}</Alert> : <Spinner label="Loading..." />;
  }

  const processed = data.completed + data.failed;
  const percent = data.total ? Math.round((processed / data.total) * 100) : 0;
  const running = RUNNING.includes(data.status);
  const maxTop = Math.max(1, done.length);

  return (
    <div>
      <p><Link to="/hr/batches">&larr; Past batches</Link></p>
      <div className="page-head">
        <div>
          <h1>{data.jd_title}</h1>
          <p className="muted">
            {data.total} resume{data.total === 1 ? "" : "s"}
            {hasMustHave ? ` · must have: ${data.must_have.join(", ")}` : ""}
          </p>
        </div>
        <div className="row">
          <label className="switch">
            <input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />
            <span>Blind mode (hide names)</span>
          </label>
          <button className="btn btn-primary" onClick={exportCsv} disabled={done.length === 0}>Download CSV</button>
        </div>
      </div>

      <Alert>{error}</Alert>

      {running && (
        <div className="card">
          <div className="progress-top">
            <strong>Screening in progress</strong>
            <span className="muted">{processed} of {data.total} done</span>
          </div>
          <div className="meter big"><div style={{ width: `${percent}%` }} /></div>
          <p className="muted small">You can leave this page. The results will be here when you come back.</p>
        </div>
      )}

      {data.status === "failed" && <Alert>This batch stopped unexpectedly. Please try again with the same resumes.</Alert>}

      {done.length > 0 && (
        <>
          <div className="grid-stats">
            <div className="card stat"><span className="muted small">Average score</span><strong>{data.stats.average}</strong></div>
            <div className="card stat"><span className="muted small">Highest</span><strong>{data.stats.highest}</strong></div>
            <div className="card stat"><span className="muted small">Lowest</span><strong>{data.stats.lowest}</strong></div>
            <div className="card stat"><span className="muted small">Shortlisted by you</span><strong>{done.filter((r) => r.decision === "shortlisted").length}</strong></div>
          </div>

          <div className="card">
            <h3>Score spread</h3>
            <div style={{ width: "100%", height: 200 }} role="img" aria-label="Bar chart of how many candidates fall in each score range">
              <ResponsiveContainer>
                <BarChart data={data.stats.buckets} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis dataKey="range" stroke="var(--muted)" />
                  <YAxis allowDecimals={false} domain={[0, (max) => Math.max(2, max)]} stroke="var(--muted)" />
                  <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", color: "var(--text)" }} />
                  <Bar dataKey="count" name="Candidates" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="toolbar">
            <input className="search" placeholder="Search name, email or skill" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search candidates" />
            <label className="inline">
              Highlight top
              <input type="range" min={1} max={maxTop} value={Math.min(topN, maxTop)} onChange={(e) => setTopN(Number(e.target.value))} />
              <strong>{Math.min(topN, maxTop)}</strong>
            </label>
            {hasMustHave && (
              <label className="switch">
                <input type="checkbox" checked={hideKnocked} onChange={(e) => setHideKnocked(e.target.checked)} />
                <span>Hide missing must-have</span>
              </label>
            )}
            <button className="btn btn-ghost" disabled={selected.length < 2} onClick={() => setComparing(true)}>
              Compare selected ({selected.length}/3)
            </button>
          </div>

          <div className="card flush">
            <table className="table candidates">
              <thead>
                <tr>
                  <th aria-label="Select" />
                  <th>#</th>
                  <th>Candidate</th>
                  <th>Score</th>
                  <th>Skills matched</th>
                  {hasMustHave && <th>Must-have</th>}
                  <th>Your decision</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const matched = r.details?.matching_skills?.length || 0;
                  const total = r.details?.skill_breakdown?.length || 0;
                  const inTop = r.rank <= Math.min(topN, maxTop);
                  return (
                    <tr key={r.id} className={inTop ? "top-row" : ""}>
                      <td>
                        <input type="checkbox" checked={selected.includes(r.id)} onChange={() => toggleSelect(r.id)} aria-label={`Select ${r.candidate_name || r.filename}`} />
                      </td>
                      <td className="rank">{r.rank}</td>
                      <td>
                        <button className="link-btn" onClick={() => setOpenId(r.id)}>{r.candidate_name || r.filename}</button>
                        {r.candidate_email && <div className="muted small">{r.candidate_email}</div>}
                        {(r.flags || []).length > 0 && <div className="flag-note" title={r.flags.join(" ")}>Needs a manual look</div>}
                      </td>
                      <td style={{ width: 170 }}><ScoreBar score={r.score} /></td>
                      <td className="muted">{matched} / {total}</td>
                      {hasMustHave && (
                        <td>
                          {(r.missing_must_have || []).length === 0
                            ? <span className="text-good">All present</span>
                            : <Chips items={r.missing_must_have} tone="bad" />}
                        </td>
                      )}
                      <td>
                        <div className="decision">
                          <button className={r.decision === "shortlisted" ? "pill on-good" : "pill"} onClick={() => setDecision(r, "shortlisted")} aria-pressed={r.decision === "shortlisted"}>Shortlist</button>
                          <button className={r.decision === "rejected" ? "pill on-bad" : "pill"} onClick={() => setDecision(r, "rejected")} aria-pressed={r.decision === "rejected"}>Reject</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {visible.length === 0 && (
                  <tr><td colSpan={hasMustHave ? 7 : 6} className="muted center">No candidates match these filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {failed.length > 0 && (
        <details className="card">
          <summary>{failed.length} resume{failed.length === 1 ? "" : "s"} could not be processed</summary>
          <ul className="plain-list">
            {failed.map((r) => (
              <li key={r.id}><strong>{r.filename}:</strong> <span className="muted">{r.error}</span></li>
            ))}
          </ul>
        </details>
      )}

      {openId && <CandidateModal id={openId} blind={blind} onClose={() => setOpenId(null)} onDecision={(row, d) => setDecision(row, d)} rows={results} />}
      {comparing && <CompareModal rows={done.filter((r) => selected.includes(r.id))} onClose={() => setComparing(false)} />}
    </div>
  );
}

function CandidateModal({ id, blind, onClose, rows, onDecision }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/hr/analyses/${id}`, { params: { blind } })
      .then((res) => setDetail(res.data))
      .catch((err) => setError(errorMessage(err)));
  }, [id, blind]);

  const row = rows.find((r) => r.id === id);
  const resume = detail?.parsed_resume;

  return (
    <Modal title={detail?.candidate_name || "Candidate"} onClose={onClose} wide>
      <Alert>{error}</Alert>
      {!detail && !error && <Spinner label="Loading..." />}
      {detail && (
        <>
          <div className="row between">
            <span className="muted">{detail.candidate_email || ""}</span>
            {row && (
              <div className="decision">
                <button className={row.decision === "shortlisted" ? "pill on-good" : "pill"} onClick={() => onDecision(row, "shortlisted")}>Shortlist</button>
                <button className={row.decision === "rejected" ? "pill on-bad" : "pill"} onClick={() => onDecision(row, "rejected")}>Reject</button>
              </div>
            )}
          </div>
          <ResultView result={detail} showTips={false} showAts={false} />
          {resume && (
            <div className="card">
              <h3>What was read from the resume</h3>
              {resume.experiences?.length > 0 && (
                <>
                  <h4>Experience</h4>
                  <ul className="plain-list">
                    {resume.experiences.map((e, i) => (
                      <li key={i}><strong>{e.role || "Role"}</strong>{e.company ? ` at ${e.company}` : ""}{e.duration ? ` (${e.duration})` : ""}</li>
                    ))}
                  </ul>
                </>
              )}
              {resume.education?.length > 0 && (<><h4>Education</h4><ul className="plain-list">{resume.education.map((e) => <li key={e}>{e}</li>)}</ul></>)}
              {resume.projects?.length > 0 && (<><h4>Projects</h4><ul className="plain-list">{resume.projects.map((p) => <li key={p}>{p}</li>)}</ul></>)}
            </div>
          )}
        </>
      )}
    </Modal>
  );
}

function CompareModal({ rows, onClose }) {
  const skills = [];
  rows.forEach((r) =>
    (r.details?.skill_breakdown || []).forEach((s) => {
      if (!skills.find((x) => x.skill === s.skill)) skills.push({ skill: s.skill, kind: s.kind });
    })
  );
  const has = (row, skill) => row.details?.skill_breakdown?.find((s) => s.skill === skill)?.present;

  return (
    <Modal title="Compare candidates" onClose={onClose} wide>
      <div className="table-scroll">
        <table className="table compare">
          <thead>
            <tr>
              <th>Skill</th>
              {rows.map((r) => <th key={r.id}>{r.candidate_name || r.filename}</th>)}
            </tr>
            <tr>
              <th>Score</th>
              {rows.map((r) => <th key={r.id}><ScoreBar score={r.score} /></th>)}
            </tr>
          </thead>
          <tbody>
            {skills.map((s) => (
              <tr key={s.skill}>
                <td>{s.skill} <span className="muted small">({s.kind})</span></td>
                {rows.map((r) => (
                  <td key={r.id}>{has(r, s.skill) ? <span className="text-good">Yes</span> : <span className="text-low">No</span>}</td>
                ))}
              </tr>
            ))}
            <tr>
              <td>Experience</td>
              {rows.map((r) => (
                <td key={r.id}>{r.details?.years_experience != null ? `${r.details.years_experience} yrs` : "Unknown"}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
