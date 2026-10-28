import { Bell, CheckCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { notificationService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { formatDateTime } from "../utils/format";
import Loading from "./Loading";

const POLL_MS = 60000;
export const LEVEL_CLASS = { SUCCESS: "status-success", WARNING: "status-warning", ERROR: "status-danger", INFO: "status-info" };

/** Campana de la barra superior: contador de no leídas (consulta periódica) y vista rápida de las recientes. */
export default function NotificationBell() {
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const containerRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();

  const refreshCount = useCallback(async () => {
    try {
      setUnread((await notificationService.unreadCount()).unread);
    } catch {
      // El contador es informativo: un fallo puntual no debe interrumpir la navegación.
    }
  }, []);

  useEffect(() => {
    refreshCount();
    const timer = setInterval(refreshCount, POLL_MS);
    window.addEventListener("focus", refreshCount);
    window.addEventListener("sipd:notifications-changed", refreshCount);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", refreshCount);
      window.removeEventListener("sipd:notifications-changed", refreshCount);
    };
  }, [refreshCount]);

  useEffect(() => { setOpen(false); }, [location.pathname]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => {
      if (event.key === "Escape" || (event.type === "mousedown" && !containerRef.current?.contains(event.target))) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (!next) return;
    setError(null);
    try {
      const response = await notificationService.list({ page_size: 6 });
      setItems(response.results);
      setUnread(response.unread);
    } catch (err) {
      setError(getErrorMessage(err, "No se pudieron cargar las notificaciones."));
    }
  };

  const openItem = async (item) => {
    if (!item.is_read) {
      try {
        await notificationService.markRead(item.id);
        setUnread((value) => Math.max(0, value - 1));
      } catch {
        // Si falla, la notificación sigue sin leer; la navegación continúa.
      }
    }
    setOpen(false);
    navigate(item.link || "/notificaciones");
  };

  const markAll = async () => {
    try {
      await notificationService.markAllRead();
      setUnread(0);
      setItems((current) => current?.map((item) => ({ ...item, is_read: true })));
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const label = unread ? `Notificaciones: ${unread} sin leer` : "Notificaciones";
  return (
    <div className="notification-bell" ref={containerRef}>
      <button type="button" className="icon-button bell-button" onClick={toggle} aria-label={label} aria-expanded={open} aria-haspopup="true">
        <Bell size={22} aria-hidden="true" />
        {unread > 0 && <span className="bell-count" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notificaciones recientes">
          <header className="bell-panel-header">
            <strong>Notificaciones</strong>
            {unread > 0 && (
              <button type="button" className="btn btn-link btn-sm" onClick={markAll}>
                <CheckCheck size={14} aria-hidden="true" /> <span>Marcar todas como leídas</span>
              </button>
            )}
          </header>
          {error && <p className="bell-empty" role="alert">{error}</p>}
          {!error && items === null && <Loading message="Cargando..." />}
          {!error && items?.length === 0 && <p className="bell-empty">No tiene notificaciones.</p>}
          {!error && items?.length > 0 && (
            <ul className="bell-list">
              {items.map((item) => (
                <li key={item.id}>
                  <button type="button" className={`bell-item ${item.is_read ? "" : "unread"}`} onClick={() => openItem(item)}>
                    <span className={`bell-dot ${LEVEL_CLASS[item.level]}`} aria-hidden="true" />
                    <span className="bell-item-text">
                      <span className="bell-item-title">{item.title}</span>
                      {item.message && <span className="bell-item-message">{item.message}</span>}
                      <span className="bell-item-date">{formatDateTime(item.created_at)}{item.is_read ? "" : " · Sin leer"}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <footer className="bell-panel-footer">
            <Link to="/notificaciones">Ver centro de notificaciones</Link>
          </footer>
        </div>
      )}
    </div>
  );
}
