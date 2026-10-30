export const APP_NAME = import.meta.env.VITE_APP_NAME || "SIPD";
export const INSTITUTION_NAME = import.meta.env.VITE_INSTITUTION_NAME || "Institución de Educación Superior";
export const SYSTEM_TITLE = "Sistema de Predicción y Seguimiento del Riesgo de Deserción";
export const SYSTEM_DESCRIPTION = "Sistema de Predicción y Seguimiento del Riesgo de Deserción Estudiantil";

export const ROLES = {
  ADMIN: "ADMIN",
  COORDINATOR: "COORDINATOR",
};

export const PREDICTION_DISCLAIMER =
  "El riesgo mostrado es una estimación probabilística generada por un modelo de Machine Learning para apoyar " +
  "el acompañamiento académico. No constituye una certeza ni un diagnóstico sobre el estudiante.";
