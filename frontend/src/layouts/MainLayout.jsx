import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import ErrorMessage from "../components/ErrorMessage";
import { PAGE_META } from "../config/navigation";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";

export default function MainLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { logout } = useAuth();
  const { error: configError, reload } = useConfig();
  const location = useLocation();
  const navigate = useNavigate();
  const section = "/" + (location.pathname.split("/")[1] || "inicio");

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} onLogout={handleLogout} />
      {menuOpen && <div className="sidebar-backdrop" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
      <div className="app-main">
        <Topbar subtitle={PAGE_META[section]?.subtitle} onToggleMenu={() => setMenuOpen((open) => !open)} />
        <main className="app-content" id="contenido">
          {configError && <ErrorMessage message={configError} onRetry={reload} />}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
