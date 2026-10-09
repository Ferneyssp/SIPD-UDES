import { FilterX } from "lucide-react";
import Button from "./Button";

/** Filtro compacto: "Programa: [Todos ▾]" (estilo de la barra de filtros). */
export default function Filter({ label, value, onChange, options, allLabel = "Todos" }) {
  return (
    <label className="filter">
      <span className="filter-label">{label}:</span>
      <select className="filter-select" value={value ?? ""} onChange={(event) => onChange(event.target.value)} aria-label={label}>
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

/** Contenedor de filtros con botón para limpiar. */
export function FilterBar({ children, onClear, hasActive }) {
  return (
    <div className="filter-bar card">
      {children}
      {onClear && hasActive && (
        <Button variant="ghost" size="sm" icon={FilterX} onClick={onClear}>Limpiar filtros</Button>
      )}
    </div>
  );
}
