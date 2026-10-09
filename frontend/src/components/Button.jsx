import { Loader2 } from "lucide-react";

/** Botón reutilizable. variant: primary | secondary | ghost | danger | link */
export default function Button({
  children, variant = "primary", size = "md", icon: Icon, loading = false, disabled, type = "button", className = "", ...props
}) {
  return (
    <button
      type={type}
      className={`btn btn-${variant} btn-${size} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : Icon && <Icon size={16} aria-hidden="true" />}
      {children && <span>{children}</span>}
    </button>
  );
}
