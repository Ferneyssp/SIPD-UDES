/** Convierte un error de axios en un mensaje comprensible en español. */
export function getErrorMessage(error, fallback = "Ocurrió un error inesperado.") {
  if (!error) return fallback;
  if (!error.response) {
    if (error.code === "ECONNABORTED") return "La solicitud tardó demasiado. Intente nuevamente.";
    return error.message === "Sin refresh token" ? "Sesión expirada." : "No fue posible conectar con el servidor.";
  }
  const { status, data } = error.response;
  if (status === 401) return data?.detail || "Sesión expirada.";
  if (status === 403) return data?.detail || "No tiene permisos para realizar esta acción.";
  if (status === 404) return "El recurso solicitado no existe o no tiene acceso a él.";
  if (status === 429) return "Demasiados intentos. Espere un momento e intente de nuevo.";
  if (status >= 500) return data?.detail || "Error interno del servidor.";
  if (data?.errors && typeof data.errors === "object") {
    const messages = Object.entries(data.errors).map(([field, value]) => {
      const text = Array.isArray(value) ? value.join(" ") : String(value);
      return field === "non_field_errors" ? text : `${field}: ${text}`;
    });
    return messages.join(" · ");
  }
  return data?.detail || fallback;
}

/** Errores por campo para mostrarlos junto a cada input. */
export function getFieldErrors(error) {
  const errors = error?.response?.data?.errors;
  if (!errors || typeof errors !== "object") return {};
  return Object.fromEntries(
    Object.entries(errors).map(([field, value]) => [field, Array.isArray(value) ? value.join(" ") : String(value)]),
  );
}
