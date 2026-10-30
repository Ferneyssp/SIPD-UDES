import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";

/** Diálogo modal accesible (cierra con Escape y con clic en el fondo). */
export default function Modal({ open, title, onClose, children, footer, size = "md" }) {
  const titleId = useId();
  const dialogRef = useRef(null);
  // onClose suele ser una función nueva en cada render: se guarda en una ref para que el efecto
  // de foco se ejecute sólo al abrir (si no, el foco saltaría al primer control en cada tecla).
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => event.key === "Escape" && onCloseRef.current?.();
    document.addEventListener("keydown", onKey);
    const previous = document.activeElement;
    const dialog = dialogRef.current;
    (dialog?.querySelector(".modal-body input, .modal-body select, .modal-body textarea")
      || dialog?.querySelector("input, select, textarea, button"))?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose?.()}>
      <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId} ref={dialogRef}>
        <header className="modal-header">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </div>
    </div>
  );
}
