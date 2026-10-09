import { useId } from "react";

/**
 * Select reutilizable. options: [{ value, label }]
 * placeholder: texto de la opción vacía ("Todos...") — si se omite no se agrega.
 */
export default function Select({ label, options = [], placeholder, error, inline = false, className = "", ...props }) {
  const generatedId = useId();
  const id = props.id || generatedId;
  return (
    <div className={`field ${inline ? "field-inline" : ""} ${className}`}>
      {label && <label htmlFor={id} className="field-label">{label}</label>}
      <select id={id} className={`input select ${error ? "has-error" : ""}`} aria-invalid={Boolean(error) || undefined} {...props}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  );
}
