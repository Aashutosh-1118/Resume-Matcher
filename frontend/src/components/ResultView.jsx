import { Alert, Chips, ScoreRing } from "./ui";

const PART_LABELS = {
  required: "Required skills",
  preferred: "Preferred skills",
  experience: "Experience",
};

// Shows one full analysis result. Used by the student page, history, and the HR candidate popup.
export default function ResultView({ result, showTips = true, showAts = true }) {
  const d = result.details || {};
  const breakdown = d.score_breakdown || {};
  const expMet = d.experience_requirement_met;

  return (
    <div className="result">
      {(result.flags || []).map((f) => (
        <Alert key={f} kind="warn">{f}</Alert>
      ))}

      <div className="result-head card">
        <ScoreRing score={result.score} />
        <div className="result-head-text">
          <h2>{result.candidate_name || result.filename}</h2>
          <p className="muted">
            {result.jd_title ? `Matched against: ${result.jd_title}` : null}
          </p>
          {d.verdict && <p className="verdict">{d.verdict}</p>}
          <p className="muted small">
            Experience requirement:{" "}
            {expMet === true && <strong className="text-good">met</strong>}
            {expMet === false && <strong className="text-low">not met</strong>}
            {expMet == null && "not scored"}
            {d.min_experience ? ` (needs ${d.min_experience}+ yrs` : ""}
            {d.min_experience && d.years_experience != null ? `, found ${d.years_experience})` : d.min_experience ? ")" : ""}
          </p>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h3>How the score is built</h3>
          {Object.keys(breakdown).length === 0 && <p className="muted">No breakdown available.</p>}
          {Object.entries(breakdown).map(([key, part]) => (
            <div key={key} className="breakdown-row">
              <div className="breakdown-top">
                <span>{PART_LABELS[key] || key}</span>
                <span className="muted small">
                  {Math.round(part.ratio * 100)}% matched, worth {Math.round(part.weight * 100)}% of the score
                </span>
              </div>
              <div className="meter"><div style={{ width: `${part.ratio * 100}%` }} /></div>
            </div>
          ))}
          <p className="muted small">
            The AI only checks each skill against the resume. The percentage itself is calculated by fixed rules, so the same resume gets the same score.
          </p>
        </div>

        <div className="card">
          <h3>Skills</h3>
          <h4>Matching</h4>
          <Chips items={d.matching_skills} tone="good" empty="No required skills found" />
          <h4>Missing</h4>
          <Chips items={d.missing_skills} tone="bad" empty="Nothing missing" />
          {(result.missing_must_have || []).length > 0 && (
            <>
              <h4>Missing must-have</h4>
              <Chips items={result.missing_must_have} tone="bad" />
            </>
          )}
        </div>
      </div>

      {(d.skill_breakdown || []).length > 0 && (
        <details className="card">
          <summary>Evidence for each skill</summary>
          <table className="table compact">
            <thead>
              <tr><th>Skill</th><th>Type</th><th>Found</th><th>Where in the resume</th></tr>
            </thead>
            <tbody>
              {d.skill_breakdown.map((s) => (
                <tr key={s.skill}>
                  <td>{s.skill}</td>
                  <td className="muted">{s.kind}</td>
                  <td>{s.present ? <span className="text-good">Yes</span> : <span className="text-low">No</span>}</td>
                  <td className="muted">{s.evidence || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}

      {showTips && (d.tips || []).length > 0 && (
        <div className="card">
          <h3>How to improve this resume for this job</h3>
          <ul className="plain-list">
            {d.tips.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </div>
      )}

      {showAts && (result.ats_checks || []).length > 0 && (
        <div className="card">
          <h3>Resume format checks</h3>
          <ul className="plain-list ats-list">
            {result.ats_checks.map((c) => (
              <li key={c.check}>
                <span className={c.ok ? "tick ok" : "tick bad"} aria-hidden="true">{c.ok ? "✓" : "!"}</span>
                <span><strong>{c.check}.</strong> <span className="muted">{c.message}</span></span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
