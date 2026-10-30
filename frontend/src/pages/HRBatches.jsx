import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api";
import { Alert, Spinner, formatDate } from "../components/ui";

export default function HRBatches() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/hr/batches")
      .then((res) => setItems(res.data))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const remove = async (b) => {
    if (!window.confirm("Delete this batch and its results?")) return;
    try {
      await api.delete(`/hr/batches/${b.id}`);
      setItems((list) => list.filter((i) => i.id !== b.id));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div>
      <h1>Past batches</h1>
      <Alert>{error}</Alert>
      {items === null && !error && <Spinner label="Loading..." />}
      {items && items.length === 0 && (
        <div className="card empty">
          <p>No batches yet.</p>
          <Link className="btn btn-primary" to="/hr/batches/new">Screen resumes</Link>
        </div>
      )}
      {items && items.length > 0 && (
        <div className="card flush">
          <table className="table">
            <thead>
              <tr><th>Job</th><th>Resumes</th><th>Status</th><th>Date</th><th /></tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.id}>
                  <td><Link to={`/hr/batches/${b.id}`}>{b.jd_title}</Link></td>
                  <td>{b.completed + b.failed} / {b.total}{b.failed > 0 ? <span className="muted small"> ({b.failed} failed)</span> : null}</td>
                  <td><span className={`status status-${b.status}`}>{b.status}</span></td>
                  <td className="muted">{formatDate(b.created_at)}</td>
                  <td className="right"><button className="btn btn-ghost small-btn" onClick={() => remove(b)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
