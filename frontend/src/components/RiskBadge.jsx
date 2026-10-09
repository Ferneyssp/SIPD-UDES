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
