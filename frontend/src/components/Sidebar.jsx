import { LogOut } from "lucide-react";
import { NavLink } from "react-router-dom";
import { APP_NAME, INSTITUTION_NAME } from "../config/appConfig";
import { canAccessItem, NAV_GROUPS, NAVIGATION } from "../config/navigation";
import { useAuth } from "../context/AuthContext";

export default function Sidebar({ open, onNavigate, onLogout }) {
  const { user } = useAuth();
  const items = NAVIGATION.filter((item) => canAccessItem(item, user));

  return (
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Menú principal">
      <div className="sidebar-brand">
        <span className="brand-logo" aria-hidden="true">
          <img src="/escudo-udes.png" alt="" width="40" height="40" />
        </span>
        <div>
          <p className="brand-name">{APP_NAME}</p>
          <p className="brand-institution">{INSTITUTION_NAME}</p>
        </div>
      </div>
      <nav className="sidebar-nav">
        {NAV_GROUPS.map((group) => {
          const groupItems = items.filter((item) => item.group === group);
          if (!groupItems.length) return null;
          return (
            <div key={group} className="nav-group" role="group" aria-label={group}>
              <p className="nav-group-title">{group}</p>
              {groupItems.map(({ path, label, icon: Icon }) => (
                <NavLink key={path} to={path} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} onClick={onNavigate}>
                  <Icon size={20} aria-hidden="true" />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>
      <button type="button" className="nav-item nav-logout" onClick={onLogout}>
        <LogOut size={20} aria-hidden="true" />
        <span>Cerrar sesión</span>
      </button>
    </aside>
  );
}
