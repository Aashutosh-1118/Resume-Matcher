import { Navigate } from "react-router-dom";
import { homePath, useAuth } from "../AuthContext";

// Only lets logged-in users in. If a role is given, only that role gets through.
export default function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-screen"><div className="spinner" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={homePath(user)} replace />;
  return children;
}
