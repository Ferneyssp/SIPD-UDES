import { AlertTriangle, RefreshCw } from "lucide-react";
import Button from "./Button";

export default function ErrorMessage({ message = "Ocurrió un error.", onRetry, compact = false }) {
  return (
    <div className={`alert alert-error ${compact ? "compact" : ""}`} role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <span className="alert-text">{message}</span>
      {onRetry && <Button variant="secondary" size="sm" icon={RefreshCw} onClick={onRetry}>Reintentar</Button>}
    </div>
  );
}
