import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { homePath, useAuth } from "./AuthContext";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Account from "./pages/Account";
import HRBatches from "./pages/HRBatches";
import HRBatchNew from "./pages/HRBatchNew";
import HRJobs from "./pages/HRJobs";
import Login from "./pages/Login";
import Register from "./pages/Register";
import StudentAnalyze from "./pages/StudentAnalyze";
import StudentHistory from "./pages/StudentHistory";
import StudentResult from "./pages/StudentResult";

// The results page pulls in the charts library, so load it only when needed.
const HRBatchDetail = lazy(() => import("./pages/HRBatchDetail"));

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-screen"><div className="spinner" /></div>;
  return <Navigate to={homePath(user)} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<ProtectedRoute role="student"><Layout /></ProtectedRoute>}>
        <Route path="/student" element={<StudentAnalyze />} />
        <Route path="/student/history" element={<StudentHistory />} />
        <Route path="/student/history/:id" element={<StudentResult />} />
      </Route>

      <Route element={<ProtectedRoute role="hr"><Layout /></ProtectedRoute>}>
        <Route path="/hr" element={<HRJobs />} />
        <Route path="/hr/batches" element={<HRBatches />} />
        <Route path="/hr/batches/new" element={<HRBatchNew />} />
        <Route
          path="/hr/batches/:id"
          element={
            <Suspense fallback={<div className="center-screen"><div className="spinner" /></div>}>
              <HRBatchDetail />
            </Suspense>
          }
        />
      </Route>

      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/account" element={<Account />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
