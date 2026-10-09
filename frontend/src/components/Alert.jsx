import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

const ICONS = { success: CheckCircle2, warning: AlertTriangle, error: AlertTriangle, info: Info };

/** Mensaje contextual. type: success | warning | error | info */
export default function Alert({ type = "info", children, onClose, title }) {
  const Icon = ICONS[type];
  return (
    <div className={`alert alert-${type}`} role={type === "error" ? "alert" : "status"}>
      <Icon size={20} aria-hidden="true" />
      <div className="alert-text">
        {title && <strong>{title} </strong>}
        {children}
      </div>
      {onClose && (
        <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar mensaje">
          <X size={16} />
        </button>
      )}
    </div>
  );
}
