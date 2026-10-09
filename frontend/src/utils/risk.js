/**
 * Presentación visual de los niveles de riesgo.
 *
 * IMPORTANTE: aquí NO se definen umbrales. La clasificación la hace el backend
 * (config/risk.py) y los umbrales se consultan en /api/config/. Este archivo
 * sólo asigna texto y estilo a cada código de nivel.
 */
export const RISK_LEVELS = {
  ALTO: { code: "ALTO", label: "Alto", className: "risk-high", color: "var(--risk-high)" },
  MEDIO: { code: "MEDIO", label: "Medio", className: "risk-medium", color: "var(--risk-medium)" },
  BAJO: { code: "BAJO", label: "Bajo", className: "risk-low", color: "var(--risk-low)" },
};

/** Colores de las gráficas (Recharts necesita valores concretos, no variables CSS). */
export const RISK_CHART_COLORS = { ALTO: "#d64545", MEDIO: "#e89a2c", BAJO: "#3f9d5a" };

export const RISK_ORDER = ["ALTO", "MEDIO", "BAJO"];

export function riskInfo(code) {
  return RISK_LEVELS[code] || { code: null, label: "Sin predicción", className: "risk-none", color: "var(--text-muted)" };
}

export const FOLLOWUP_STATUS_CLASS = {
  PENDIENTE: "status-neutral",
  EN_SEGUIMIENTO: "status-warning",
  ATENDIDO: "status-info",
  CERRADO: "status-success",
  SIN_SEGUIMIENTO: "status-muted",
};
