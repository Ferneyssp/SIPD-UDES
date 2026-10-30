import { Menu } from "lucide-react";
import { Link } from "react-router-dom";
import { SYSTEM_TITLE } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { initials } from "../utils/format";
import GlobalSearch from "./GlobalSearch";
import NotificationBell from "./NotificationBell";

export default function Topbar({ subtitle, onToggleMenu }) {
  const { user } = useAuth();
  return (
    <header className="topbar">
      <button type="button" className="icon-button menu-toggle" onClick={onToggleMenu} aria-label="Abrir menú">
        <Menu size={22} />
      </button>
      <div className="topbar-title">
        <p className="topbar-system">{SYSTEM_TITLE}</p>
        {subtitle && <p className="topbar-subtitle">{subtitle}</p>}
      </div>
      <GlobalSearch />
      <NotificationBell />
      <Link to="/perfil" className="topbar-user" aria-label="Ver perfil">
        <span className="avatar" aria-hidden="true">{initials(user)}</span>
        <span className="topbar-user-text">
          <span className="topbar-user-name">{[user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username}</span>
          <span className="topbar-user-role">{user?.role_display}</span>
        </span>
      </Link>
    </header>
  );
}
