import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { Alert, ScoreBar, Spinner, formatDate } from "../components/ui";

export default function StudentHistory() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  const load = () =>
    api
      .get("/student/history")
      .then((res) => setItems(res.data))
      .catch((err) => setError(errorMessage(err)));

  useEffect(() => {
    load();
  }, []);

  const remove = async (id) => {
    if (!window.confirm("Delete this result?")) return;
    try {
      await api.delete(`/student/history/${id}`);
      setItems((list) => list.filter((i) => i.id !== id));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div>
      <h1>Your history</h1>
      <Alert>{error}</Alert>
      {items === null && !error && <Spinner label="Loading..." />}
      {items && items.length === 0 && (
        <div className="card empty">
          <p>No checks yet.</p>
          <Link className="btn btn-primary" to="/student">Check a resume</Link>
        </div>
      )}
      {items && items.length > 0 && (
        <div className="card flush">
          <table className="table">
            <thead>
              <tr><th>Job</th><th>Resume file</th><th>Score</th><th>Date</th><th /></tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <td><Link to={`/student/history/${i.id}`}>{i.jd_title}</Link></td>
                  <td className="muted">{i.filename}</td>
                  <td style={{ width: 160 }}><ScoreBar score={i.score} /></td>
                  <td className="muted">{formatDate(i.created_at)}</td>
                  <td className="right">
                    <button className="btn btn-ghost small-btn" onClick={() => remove(i.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
