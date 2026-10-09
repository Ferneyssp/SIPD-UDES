import { useId } from "react";

/** Campo de texto con etiqueta, ícono opcional y mensaje de error. */
export default function Input({ label, error, hint, icon: Icon, className = "", trailing, as = "input", ...props }) {
  const generatedId = useId();
  const id = props.id || generatedId;
  const Component = as;
  return (
    <div className={`field ${className}`}>
      {label && <label htmlFor={id} className="field-label">{label}</label>}
      <div className={`input-wrap ${Icon ? "has-icon" : ""} ${error ? "has-error" : ""}`}>
        {Icon && <Icon className="input-icon" size={18} aria-hidden="true" />}
        <Component
          id={id}
          className="input"
          aria-invalid={Boolean(error) || undefined}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          {...props}
        />
        {trailing}
      </div>
      {hint && !error && <p id={`${id}-hint`} className="field-hint">{hint}</p>}
      {error && <p id={`${id}-error`} className="field-error" role="alert">{error}</p>}
    </div>
  );
}
