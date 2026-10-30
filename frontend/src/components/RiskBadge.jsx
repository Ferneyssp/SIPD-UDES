import { Info } from "lucide-react";
import { useState } from "react";
import { riskInfo } from "../utils/risk";

/**
 * Nivel de riesgo. El color NUNCA es la única señal: siempre incluye el texto
 * del nivel ("Alto", "Medio", "Bajo") y una forma distinta por nivel.
 */
export default function RiskBadge({ level, size = "md" }) {
  const info = riskInfo(level);
  return (
    <span className={`badge risk-badge ${info.className} badge-${size}`}>
      <span className="risk-dot" aria-hidden="true" />
      {info.label}
    </span>
  );
}

/** Barra de probabilidad con porcentaje en texto. */
export function RiskBar({ probability, level, compact = false }) {
  if (probability === null || probability === undefined) return <span className="text-muted">Sin predicción</span>;
  const info = riskInfo(level);
  const percentage = Math.round(probability * 1000) / 10;
  return (
    <div className={`risk-bar ${compact ? "compact" : ""}`}>
      <span className={`risk-bar-value ${info.className}-text`}>{percentage.toFixed(1).replace(".", ",")} %</span>
      <span
        className="risk-bar-track"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
        aria-label={`Riesgo estimado ${percentage} por ciento, nivel ${info.label}`}
      >
        <span className={`risk-bar-fill ${info.className}-bg`} style={{ width: `${percentage}%` }} />
      </span>
    </div>
  );
}

/**
 * Cambio del riesgo estimado frente a la predicción del periodo anterior, en puntos porcentuales.
 * Se muestra con símbolo y texto, no sólo con color.
 */
export function RiskChange({ points }) {
  if (points === null || points === undefined) return <span className="text-muted">Sin predicción anterior</span>;
  const text = `${Math.abs(points).toFixed(1).replace(".", ",")} pts`;
  if (points > 0) return <span className="risk-change up" title="Aumentó frente al periodo anterior">▲ +{text}</span>;
  if (points < 0) return <span className="risk-change down" title="Disminuyó frente al periodo anterior">▼ −{text}</span>;
  return <span className="risk-change same">= {text}</span>;
}

/** Icono ℹ que muestra los rangos vigentes de cada nivel (leídos del backend). */
export function RiskRangesInfo({ levels }) {
  const [open, setOpen] = useState(false);
  if (!levels?.length) return null;
  const pct = (value) => `${Math.round(value * 100)} %`;
  return (
    <span className="ranges-info">
      <button type="button" className="icon-button ranges-button" aria-expanded={open} aria-label="Ver rangos de los niveles de riesgo"
        onClick={() => setOpen((value) => !value)}>
        <Info size={15} aria-hidden="true" />
      </button>
      {open && (
        <span className="ranges-popover" role="note">
          {[...levels].reverse().map((level) => (
            <span key={level.code}><strong>{level.label}:</strong> {pct(level.min)} – {level.code === "ALTO" ? "100 %" : `< ${pct(level.max)}`}</span>
          ))}
          <small>Umbrales definidos por la institución. Son estimaciones del modelo.</small>
        </span>
      )}
    </span>
  );
}
