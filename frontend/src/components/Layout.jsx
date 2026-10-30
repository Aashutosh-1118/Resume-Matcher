import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const links =
    user.role === "hr"
      ? [
          { to: "/hr", label: "Job descriptions", end: true },
          { to: "/hr/batches/new", label: "Screen resumes" },
          { to: "/hr/batches", label: "Past batches", end: true },
        ]
      : [
          { to: "/student", label: "Check my resume", end: true },
          { to: "/student/history", label: "History" },
        ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <span className="brand">Resume Matcher</span>
          <nav className="nav">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="topbar-right">
            <NavLink to="/account" className="user-chip" title="Account settings">
              <span className="role-badge">{user.role === "hr" ? "HR" : "Student"}</span>
              <span className="user-name">{user.full_name}</span>
            </NavLink>
            <button
              className="btn btn-ghost"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </div>
  );
}
