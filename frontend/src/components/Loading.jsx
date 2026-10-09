import { Loader2 } from "lucide-react";

export default function Loading({ message = "Cargando información...", fullPage = false }) {
  return (
    <div className={`loading ${fullPage ? "loading-full" : ""}`} role="status" aria-live="polite">
      <Loader2 className="spin" size={28} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
