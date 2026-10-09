const dateFormatter = new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: "2-digit", year: "numeric" });
const dateTimeFormatter = new Intl.DateTimeFormat("es-CO", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
});
const numberFormatter = new Intl.NumberFormat("es-CO");

export function formatDate(value) {
  if (!value) return "—";
  const date = typeof value === "string" && value.length === 10 ? new Date(`${value}T12:00:00`) : new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormatter.format(date);
}

export function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormatter.format(date);
}

export function formatNumber(value) {
  return value === null || value === undefined ? "—" : numberFormatter.format(value);
}

/** 0.8234 -> "82,3 %" */
export function formatProbability(probability, digits = 1) {
  if (probability === null || probability === undefined) return "—";
  return `${(probability * 100).toFixed(digits).replace(".", ",")} %`;
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(digits).replace(".", ",")} %`;
}

export function formatFeatureValue(value) {
  if (value === null || value === undefined) return "Sin dato";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(".", ",");
  return String(value);
}

export function initials(user) {
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username || "?";
  return name.split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase();
}

/** "Ingeniería de Sistemas" -> "Ing. de Sistemas" (tablas compactas). */
export function shortProgram(name) {
  return name ? name.replace(/^Ingeniería/, "Ing.") : "—";
}
