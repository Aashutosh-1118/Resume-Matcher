import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { Alert } from "../components/ui";

export default function Account() {
  const { user, deleteAccount } = useAuth();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");

  const remove = async () => {
    try {
      await deleteAccount();
      navigate("/login", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div className="narrow">
      <h1>Account</h1>
      <div className="card">
        <dl className="kv">
          <dt>Name</dt><dd>{user.full_name}</dd>
          <dt>Email</dt><dd>{user.email}</dd>
          <dt>Account type</dt><dd>{user.role === "hr" ? "HR" : "Student"}</dd>
        </dl>
      </div>
      <div className="card">
        <h3>Your data</h3>
        <p className="muted">
          Uploaded resume files are not kept. Only the analysis results are saved, so you can see them again later.
          Deleting your account removes your login and everything saved under it, and this cannot be undone.
        </p>
        <Alert>{error}</Alert>
        {!confirming ? (
          <button className="btn btn-danger" onClick={() => setConfirming(true)}>Delete my account and data</button>
        ) : (
          <div className="row">
            <button className="btn btn-danger" onClick={remove}>Yes, delete everything</button>
            <button className="btn btn-ghost" onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}
