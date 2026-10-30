import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { errorMessage } from "../api";
import ResultView from "../components/ResultView";
import { Alert, Spinner, formatDate } from "../components/ui";

export default function StudentResult() {
  const { id } = useParams();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/student/history/${id}`)
      .then((res) => setResult(res.data))
      .catch((err) => setError(errorMessage(err)));
  }, [id]);

  return (
    <div>
      <p><Link to="/student/history">&larr; Back to history</Link></p>
      <Alert>{error}</Alert>
      {!result && !error && <Spinner label="Loading..." />}
      {result && (
        <>
          <p className="muted">Checked on {formatDate(result.created_at)}</p>
          <ResultView result={result} />
        </>
      )}
    </div>
  );
}
