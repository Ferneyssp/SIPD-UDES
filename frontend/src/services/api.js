/**
 * Servicios de acceso a la API REST. Los componentes nunca llaman a axios
 * directamente: usan estas funciones.
 */
import apiClient from "./apiClient";

const data = (promise) => promise.then((response) => response.data);

/** Elimina parámetros vacíos para no enviar filtros sin valor. */
export function cleanParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  );
}

export const authService = {
  login: (username, password, remember) => data(apiClient.post("/auth/login/", { username, password, remember: Boolean(remember) })),
  logout: () => data(apiClient.post("/auth/logout/")),
  me: () => data(apiClient.get("/auth/me/")),
  changePassword: (payload) => data(apiClient.post("/auth/change-password/", payload)),
  requestPasswordReset: (email) => data(apiClient.post("/auth/password-reset/", { email })),
  confirmPasswordReset: (payload) => data(apiClient.post("/auth/password-reset/confirm/", payload)),
};

export const catalogService = {
  config: () => data(apiClient.get("/config/")),
  programs: () => data(apiClient.get("/programs/")),
  periods: () => data(apiClient.get("/periods/")),
};

/** Estudiantes: sólo lectura (los datos se actualizan con la carga CSV). */
export const studentService = {
  list: (params) => data(apiClient.get("/students/", { params: cleanParams(params) })),
  get: (code) => data(apiClient.get(`/students/${encodeURIComponent(code)}/`)),
  exportCsv: (params) => apiClient.get("/students/export/", { params: cleanParams(params), responseType: "blob" }),
};

export const alertService = {
  list: (params) => data(apiClient.get("/alerts/", { params: cleanParams(params) })),
  summary: (params) => data(apiClient.get("/alerts/summary/", { params: cleanParams(params) })),
};

export const predictionService = {
  list: (params) => data(apiClient.get("/predictions/", { params: cleanParams(params) })),
  get: (id) => data(apiClient.get(`/predictions/${id}/`)),
  run: (student, academicPeriod) =>
    data(apiClient.post("/predictions/", cleanParams({ student, academic_period: academicPeriod }))),
  runBatch: (academicPeriod, program) =>
    data(apiClient.post("/predictions/run-batch/", cleanParams({ academic_period: academicPeriod, program }))),
  history: (student, includeSuperseded = false) =>
    data(apiClient.get("/predictions/history/", { params: { student, include_superseded: includeSuperseded } })),
  summary: (params) => data(apiClient.get("/predictions/summary/", { params: cleanParams(params) })),
};

export const modelService = {
  list: () => data(apiClient.get("/models/")),
  activate: (id) => data(apiClient.post(`/models/${id}/activate/`)),
  sync: () => data(apiClient.post("/models/sync/")),
};

export const followupService = {
  list: (params) => data(apiClient.get("/followups/", { params: cleanParams(params) })),
  create: (payload) => data(apiClient.post("/followups/", payload)),
  update: (id, payload) => data(apiClient.patch(`/followups/${id}/`, payload)),
  responsibles: (student) => data(apiClient.get("/followups/responsibles/", { params: cleanParams({ student }) })),
};

export const uploadService = {
  list: (params) => data(apiClient.get("/uploads/", { params: cleanParams(params) })),
  validate: (file) => {
    const form = new FormData();
    form.append("file", file);
    return data(apiClient.post("/uploads/", form, { headers: { "Content-Type": "multipart/form-data" } }));
  },
  confirm: (id, runPredictions) => data(apiClient.post(`/uploads/${id}/confirm/`, { run_predictions: runPredictions })),
  discard: (id) => data(apiClient.post(`/uploads/${id}/discard/`)),
  downloadTemplate: () => apiClient.get("/uploads/template/", { responseType: "blob" }),
};

export const userService = {
  list: (params) => data(apiClient.get("/users/", { params: cleanParams(params) })),
  create: (payload) => data(apiClient.post("/users/", payload)),
  update: (id, payload) => data(apiClient.patch(`/users/${id}/`, payload)),
  deactivate: (id) => data(apiClient.delete(`/users/${id}/`)),
  activate: (id) => data(apiClient.post(`/users/${id}/activate/`)),
};

export const trainingService = {
  overview: () => data(apiClient.get("/training/overview/")),
  validateDataset: (file) => {
    const form = new FormData();
    form.append("file", file);
    return data(apiClient.post("/training/datasets/", form, { headers: { "Content-Type": "multipart/form-data" } }));
  },
  start: (payload) => data(apiClient.post("/training/runs/", { ...payload, confirm: true })),
  runs: (params) => data(apiClient.get("/training/runs/", { params: cleanParams(params) })),
  run: (id) => data(apiClient.get(`/training/runs/${id}/`)),
  activeRun: () => data(apiClient.get("/training/runs/active/")),
  cancel: (id) => data(apiClient.post(`/training/runs/${id}/cancel/`)),
  approve: (id, notes) => data(apiClient.post(`/models/${id}/approve/`, { notes })),
  reject: (id, notes) => data(apiClient.post(`/models/${id}/reject/`, { notes })),
  activate: (id) => data(apiClient.post(`/models/${id}/activate/`)),
};

export const notificationService = {
  list: (params) => data(apiClient.get("/notifications/", { params: cleanParams(params) })),
  unreadCount: () => data(apiClient.get("/notifications/unread-count/")),
  markRead: (id) => data(apiClient.post(`/notifications/${id}/read/`)),
  markAllRead: () => data(apiClient.post("/notifications/read-all/")),
};

/** kind: risk. Las descargas devuelven la respuesta completa (blob + cabeceras). */
export const reportService = {
  get: (kind, params) => data(apiClient.get(`/reports/${kind}/`, { params: cleanParams(params) })),
  download: (path, params) => apiClient.get(`/reports/${path}/`, { params: cleanParams(params), responseType: "blob" }),
};
