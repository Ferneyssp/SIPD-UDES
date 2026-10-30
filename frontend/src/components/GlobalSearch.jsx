import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDebounce } from "../hooks/useDebounce";
import { studentService } from "../services/api";
import { formatProbability, shortProgram } from "../utils/format";
import RiskBadge from "./RiskBadge";

/** Buscador del encabezado: llegar a la ficha de un estudiante en un paso (código E001). */
export default function GlobalSearch() {
  const navigate = useNavigate();
  const [term, setTerm] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const debounced = useDebounce(term.trim(), 250);
  const boxRef = useRef(null);

  useEffect(() => {
    if (debounced.length < 2) {
      setResults([]);
      return undefined;
    }
    let cancelled = false;
    studentService.list({ search: debounced, page_size: 6 })
      .then((data) => { if (!cancelled) { setResults(data.results); setOpen(true); } })
      .catch(() => { if (!cancelled) setResults([]); });
    return () => { cancelled = true; };
  }, [debounced]);

  useEffect(() => {
    const close = (event) => { if (!boxRef.current?.contains(event.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const go = (code) => {
    setOpen(false);
    setTerm("");
    navigate(`/estudiantes/${code}`);
  };

  const submit = (event) => {
    event.preventDefault();
    const exact = results.find((s) => s.anonymous_code === term.trim().toUpperCase());
    if (exact || results.length === 1) go((exact || results[0]).anonymous_code);
    else if (term.trim()) navigate(`/estudiantes?search=${encodeURIComponent(term.trim())}`);
  };

  return (
    <form className="global-search" role="search" onSubmit={submit} ref={boxRef}>
      <Search size={16} aria-hidden="true" className="global-search-icon" />
      <input type="search" value={term} onChange={(e) => setTerm(e.target.value)} onFocus={() => results.length && setOpen(true)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        placeholder="Buscar estudiante (E001)..." aria-label="Buscar estudiante por código" />
      {open && debounced.length >= 2 && (
        <ul className="global-search-results" role="listbox" aria-label="Resultados">
          {results.length === 0 && <li className="text-muted global-search-empty">Sin resultados en su ámbito.</li>}
          {results.map((s) => (
            <li key={s.id} role="option" aria-selected="false">
              <button type="button" onClick={() => go(s.anonymous_code)}>
                <strong>{s.anonymous_code}</strong>
                <span className="text-muted">{shortProgram(s.program)} · Sem. {s.semester}</span>
                <span>{s.current_probability !== null ? formatProbability(s.current_probability) : ""} <RiskBadge level={s.current_risk_level} size="sm" /></span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
