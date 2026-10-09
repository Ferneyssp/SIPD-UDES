import { Search, X } from "lucide-react";

export default function SearchBar({ value, onChange, placeholder = "Buscar...", label = "Buscar", className = "" }) {
  return (
    <div className={`search-bar ${className}`}>
      <Search size={18} className="search-icon" aria-hidden="true" />
      <input
        type="search"
        className="input"
        aria-label={label}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {value && (
        <button type="button" className="icon-button search-clear" onClick={() => onChange("")} aria-label="Limpiar búsqueda">
          <X size={16} />
        </button>
      )}
    </div>
  );
}
