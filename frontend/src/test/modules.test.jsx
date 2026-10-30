import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { NAVIGATION, canAccessItem } from "../config/navigation";
import { AuthProvider } from "../context/AuthContext";
import { ConfigProvider } from "../context/ConfigContext";
import { ADMIN, CONFIG, PERIODS, COORDINATOR, PROGRAMS, loginAs } from "./helpers";

vi.mock("../services/api", () => ({
  cleanParams: (p) => p,
  authService: { login: vi.fn(), logout: vi.fn(), me: vi.fn(), changePassword: vi.fn() },
  catalogService: { config: vi.fn(), programs: vi.fn(), periods: vi.fn() },
  predictionService: { summary: vi.fn() },
  trainingService: {
    overview: vi.fn(), validateDataset: vi.fn(), useReferenceDataset: vi.fn(), start: vi.fn(), runs: vi.fn(), run: vi.fn(),
    cancel: vi.fn(), approve: vi.fn(), reject: vi.fn(), activate: vi.fn(), rollback: vi.fn(), activations: vi.fn(),
  },
  notificationService: { list: vi.fn(), unreadCount: vi.fn(), markRead: vi.fn(), markAllRead: vi.fn() },
  reportService: { get: vi.fn(), download: vi.fn() },
}));

const api = await import("../services/api");

const TRAINING_CONFIG = {
  enabled: true, executor: "thread", disabled_reason: null,
  algorithms: [{ value: "logistic_regression", label: "Regresión Logística" }, { value: "random_forest", label: "Random Forest" }],
  selection_metrics: ["f1", "recall", "roc_auc", "precision"], default_selection_metric: "f1",
  fixed_parameters: { threshold: 0.3, test_fraction: 0.25, random_state: 42, stratified: true },
  dataset: { required_columns: ["program_code", "gpa", "dropout"], optional_columns: ["motivation_level"], target_column: "dropout",
    min_rows: 100, min_rows_per_class: 10, max_rows: 50000, max_mb: 5, reference_available: false },
  acceptance_min_metrics: {},
};
const ACTIVE_MODEL = {
  id: 1, name: "Regresión Logística", algorithm: "logistic_regression", version: "20261011161613", active: true,
  metrics: { accuracy: 0.84, precision: 0.69, recall: 0.75, f1: 0.72, roc_auc: 0.88 }, approval_status: "NO_REQUERIDA",
  approval_status_display: "Registrado sin flujo de aprobación", trained_at: "2026-10-11T21:16:13Z", training_run: null,
};
const OVERVIEW = { config: TRAINING_CONFIG, active_model: ACTIVE_MODEL, versions: [ACTIVE_MODEL], active_run: null, last_run: null };
const VALID_DATASET = {
  id: 5, filename: "historico.csv", rows: 400, status: "VALIDO", is_synthetic: false,
  report: { rows: 400, errors: [], warnings: [{ code: "MISSING_VALUES", column: "previous_gpa", message: "12 valores vacíos", count: 12 }],
    summary: { class_counts: { 0: 300, 1: 100 } } },
};
const COMPLETED_RUN = {
  id: 9, status: "COMPLETADO", status_display: "Completado", stage_message: "Entrenamiento completado: 1 versiones evaluadas.",
  events: [{ status: "PENDIENTE", at: "2026-10-28T10:00:00Z", message: "Solicitud registrada." }],
  algorithms: ["logistic_regression"], selection_metric: "f1", threshold: 0.3, version: "20261028100000", error_message: "",
  requested_by: "admin", dataset: { filename: "historico.csv", rows: 400, is_synthetic: false },
  created_at: "2026-10-28T10:00:00Z", started_at: "2026-10-28T10:00:01Z", finished_at: "2026-10-28T10:00:30Z", is_finished: true,
  versions: [{
    id: 2, name: "Regresión Logística", algorithm: "logistic_regression", version: "20261028100000", selected: true, active: false,
    approval_status: "PENDIENTE", approval_status_display: "Pendiente de aprobación",
    metrics: { accuracy: 0.8, precision: 0.6, recall: 0.7, f1: 0.65, roc_auc: 0.85, test_size: 100, threshold: 0.3,
      confusion_matrix: { tn: 60, fp: 15, fn: 8, tp: 17 } },
    acceptance: { passed: true, metric_minimums_configured: false, checks: [{ code: "metrics", label: "Métricas calculadas", passed: true, detail: "ok" }] },
  }],
  comparisons: { 2: { reference: { id: 1, label: "Regresión Logística v20261011161613", active: true }, comparable: false,
    warnings: ["Se entrenaron y evaluaron con datasets distintos: las métricas no son directamente comparables."],
    rows: [{ metric: "f1", reference: 0.72, new: 0.65, difference: -0.07 }] } },
};
const RISK_REPORT = {
  generated_at: "2026-10-28T10:00:00Z", filters: { period: "2026-2" }, scope_restricted: false, thresholds: { low: 0.3, medium: 0.6 },
  totals: { students: 10, levels: [{ code: "ALTO", label: "Alto", count: 2, pct: 20 }, { code: "MEDIO", label: "Medio", count: 3, pct: 30 },
    { code: "BAJO", label: "Bajo", count: 5, pct: 50 }] },
  by_program: [{ program: "Ingeniería de Sistemas", total: 10, ALTO: 2, ALTO_pct: 20, MEDIO: 3, MEDIO_pct: 30, BAJO: 5, BAJO_pct: 50 }],
  by_semester: [], models: [{ model: "Regresión Logística", version: "1", predictions: 10, is_synthetic: false }],
  source: "Predicciones vigentes.", notices: ["El nivel de riesgo es una estimación."],
};

function renderApp(route) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider><ConfigProvider><App /></ConfigProvider></AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.catalogService.config.mockResolvedValue(CONFIG);
  api.catalogService.programs.mockResolvedValue(PROGRAMS);
  api.catalogService.periods.mockResolvedValue(PERIODS);
  api.authService.me.mockImplementation(() => Promise.resolve(JSON.parse(sessionStorage.getItem("sipd.user"))));
  api.notificationService.unreadCount.mockResolvedValue({ unread: 0 });
  api.trainingService.overview.mockResolvedValue(OVERVIEW);
  api.trainingService.runs.mockResolvedValue({ count: 0, results: [] });
  api.trainingService.activations.mockResolvedValue({ results: [], rollback_candidates: [] });
  api.reportService.get.mockResolvedValue(RISK_REPORT);
});

describe("Navegación de los nuevos módulos", () => {
  it("Reentrenamiento sólo es visible para el administrador; Reportes y Notificaciones para todos", () => {
    const forCoordinator = NAVIGATION.filter((i) => canAccessItem(i, COORDINATOR)).map((i) => i.label);
    const forAdmin = NAVIGATION.filter((i) => canAccessItem(i, ADMIN)).map((i) => i.label);
    expect(forAdmin).toEqual(expect.arrayContaining(["Reentrenamiento", "Reportes", "Notificaciones"]));
    expect(forCoordinator).toEqual(expect.arrayContaining(["Reportes", "Notificaciones"]));
    expect(forCoordinator).not.toContain("Reentrenamiento");
  });

  it("un coordinador que entra directamente a /reentrenamiento ve el aviso de permisos", async () => {
    loginAs(COORDINATOR);
    renderApp("/reentrenamiento");
    expect(await screen.findByText(/no tiene permisos/i)).toBeInTheDocument();
    expect(api.trainingService.overview).not.toHaveBeenCalled();
  });
});

describe("Campana de notificaciones", () => {
  it("muestra el contador y la vista rápida, y permite marcar todas como leídas", async () => {
    api.notificationService.unreadCount.mockResolvedValue({ unread: 3 });
    api.notificationService.list.mockResolvedValue({
      unread: 3, results: [{ id: 1, title: "Reentrenamiento #9 completado", message: "Versión lista", level: "SUCCESS", is_read: false,
        created_at: "2026-10-28T10:00:00Z", link: "/reentrenamiento?run=9" }],
    });
    api.notificationService.markAllRead.mockResolvedValue({ updated: 3, unread: 0 });
    loginAs(COORDINATOR);
    renderApp("/notificaciones-inexistente");
    const bell = await screen.findByRole("button", { name: "Notificaciones: 3 sin leer" });
    await userEvent.click(bell);
    expect(await screen.findByText("Reentrenamiento #9 completado")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /marcar todas como leídas/i }));
    expect(api.notificationService.markAllRead).toHaveBeenCalled();
    expect(await screen.findByRole("button", { name: "Notificaciones" })).toBeInTheDocument();
  });

  it("el centro de notificaciones muestra estado vacío", async () => {
    api.notificationService.list.mockResolvedValue({ count: 0, unread: 0, results: [], categories: [], types: [] });
    loginAs(ADMIN);
    renderApp("/notificaciones");
    expect(await screen.findByText("No hay notificaciones para los filtros seleccionados.")).toBeInTheDocument();
  });
});

describe("Reentrenamiento", () => {
  it("muestra el estado de los modelos", async () => {
    loginAs(ADMIN);
    renderApp("/reentrenamiento");
    expect(await screen.findByRole("heading", { name: /Reentrenamiento de modelos/ })).toBeInTheDocument();
    expect(screen.getByText("Estado de los modelos")).toBeInTheDocument();
    expect(screen.getAllByText("Activo").length).toBeGreaterThan(0);
  });

  it("rechaza archivos que no son CSV sin llamar al backend", async () => {
    loginAs(ADMIN);
    const { container } = renderApp("/reentrenamiento");
    await screen.findByText("Nuevo reentrenamiento");
    const input = container.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [new File(["x"], "datos.xlsx")] } });
    expect(await screen.findByText(/Sólo se permiten archivos con extensión .csv/)).toBeInTheDocument();
    expect(api.trainingService.validateDataset).not.toHaveBeenCalled();
  });

  it("muestra los errores de validación devueltos por el backend", async () => {
    api.trainingService.validateDataset.mockRejectedValue({ response: { status: 422, data: {
      id: 6, filename: "malo.csv", rows: 0, status: "RECHAZADO", report: { rows: 0, warnings: [], summary: {},
        errors: [{ code: "MISSING_COLUMNS", column: "-", message: "Faltan columnas obligatorias: dropout.", rows: [], count: 1 }] } } } });
    loginAs(ADMIN);
    const { container } = renderApp("/reentrenamiento");
    await screen.findByText("Nuevo reentrenamiento");
    fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [new File(["a,b"], "malo.csv")] } });
    await userEvent.click(screen.getByRole("button", { name: /validar archivo/i }));
    expect(await screen.findByText("Faltan columnas obligatorias: dropout.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revisar y entrenar/i })).not.toBeInTheDocument();
  });

  it("valida, pide confirmación con resumen e inicia el entrenamiento real", async () => {
    api.trainingService.validateDataset.mockResolvedValue(VALID_DATASET);
    api.trainingService.start.mockResolvedValue({ id: 9 });
    api.trainingService.run.mockResolvedValue(COMPLETED_RUN);
    loginAs(ADMIN);
    const { container } = renderApp("/reentrenamiento");
    await screen.findByText("Nuevo reentrenamiento");
    fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [new File(["a"], "historico.csv")] } });
    await userEvent.click(screen.getByRole("button", { name: /validar archivo/i }));
    expect(await screen.findByText("Dataset válido.")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Random Forest"));  // se deja sólo Regresión Logística
    await userEvent.click(screen.getByRole("button", { name: /revisar y entrenar/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/historico.csv/)).toBeInTheDocument();
    expect(within(dialog).getByText(/pendientes de aprobación/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Iniciar entrenamiento" }));
    expect(api.trainingService.start).toHaveBeenCalledWith({ dataset: 5, algorithms: ["logistic_regression"], selection_metric: "f1" });
    expect(await screen.findByText(/Entrenamiento #9/)).toBeInTheDocument();
    expect(await screen.findByText("Entrenamiento completado.")).toBeInTheDocument();
    expect(screen.getByText(/datasets distintos/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aprobar" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Activar" })).not.toBeInTheDocument();
  });

  it("presenta un entrenamiento en curso con su etapa real y sin porcentaje inventado", async () => {
    api.trainingService.run.mockResolvedValue({ ...COMPLETED_RUN, status: "ENTRENANDO", status_display: "Entrenando",
      stage_message: "Entrenando Random Forest (2 de 3).", is_finished: false, finished_at: null, versions: [] });
    loginAs(ADMIN);
    renderApp("/reentrenamiento?run=9");
    expect(await screen.findByText("Entrenando Random Forest (2 de 3).")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("muestra un entrenamiento fallido sin activar versiones", async () => {
    api.trainingService.run.mockResolvedValue({ ...COMPLETED_RUN, status: "FALLIDO", status_display: "Fallido",
      error_message: "Etapa preparando datos: error.", versions: [] });
    loginAs(ADMIN);
    renderApp("/reentrenamiento?run=9");
    expect(await screen.findByText("El entrenamiento falló.")).toBeInTheDocument();
    expect(screen.getByText(/el modelo activo sigue siendo el anterior/)).toBeInTheDocument();
  });
});

describe("Reportes", () => {
  it("muestra indicadores reales y exporta CSV con los filtros aplicados", async () => {
    api.reportService.download.mockResolvedValue({ data: new Blob(["a"]), headers: { "content-disposition": 'attachment; filename="r.csv"' } });
    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    loginAs(ADMIN);
    renderApp("/reportes");
    expect(await screen.findByText("Estudiantes analizados")).toBeInTheDocument();
    expect(screen.getAllByText("20,0 %").length).toBeGreaterThan(0);
    expect(api.reportService.get).toHaveBeenCalledWith("risk", expect.objectContaining({ period: "2026-2" }));
    fireEvent.change(screen.getByLabelText("Programa"), { target: { value: "SIS" } });
    await waitFor(() => expect(api.reportService.get).toHaveBeenLastCalledWith("risk", expect.objectContaining({ program: "SIS" })));
    await userEvent.click(screen.getByRole("button", { name: /exportar csv/i }));
    expect(api.reportService.download).toHaveBeenCalledWith("risk/csv", expect.objectContaining({ program: "SIS", period: "2026-2" }));
  });

  it("informa cuando no hay datos en lugar de fabricarlos", async () => {
    api.reportService.get.mockResolvedValue({ ...RISK_REPORT, totals: { students: 0, levels: RISK_REPORT.totals.levels.map((l) => ({ ...l, count: 0, pct: 0 })) } });
    loginAs(ADMIN);
    renderApp("/reportes");
    expect(await screen.findByText(/El reporte no contiene datos/)).toBeInTheDocument();
  });

  it("el coordinador no ve el reporte de actividad ni el CSV individual", async () => {
    loginAs(COORDINATOR);
    renderApp("/reportes");
    await screen.findByText("Estudiantes analizados");
    expect(screen.queryByRole("tab", { name: "Actividad administrativa" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /csv individual/i })).not.toBeInTheDocument();
  });

  it("muestra el mensaje del backend si falla una descarga", async () => {
    api.reportService.download.mockRejectedValue({ response: { status: 403, data: new Blob([JSON.stringify({ detail: "Sin permiso." })]) } });
    loginAs(ADMIN);
    renderApp("/reportes");
    await screen.findByText("Estudiantes analizados");
    await userEvent.click(screen.getByRole("button", { name: /generar pdf/i }));
    expect(await screen.findByText("Sin permiso.")).toBeInTheDocument();
  });
});

describe("Reentrenamiento: diseño simplificado", () => {
  it("muestra el nuevo entrenamiento al inicio, sin dataset de referencia ni selector de métrica", async () => {
    api.trainingService.validateDataset.mockResolvedValue(VALID_DATASET);
    loginAs(ADMIN);
    const { container } = renderApp("/reentrenamiento");
    const newTraining = await screen.findByText("Nuevo reentrenamiento");
    const status = screen.getByText("Estado de los modelos");
    expect(newTraining.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByRole("button", { name: /dataset de referencia/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Activaciones y recuperación de versiones")).not.toBeInTheDocument();
    for (const header of ["F1 (mejor)", "Activación", "Error"]) expect(screen.queryByRole("columnheader", { name: header })).not.toBeInTheDocument();
    fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [new File(["a"], "historico.csv")] } });
    await userEvent.click(screen.getByRole("button", { name: /validar archivo/i }));
    await screen.findByText("Dataset válido.");
    expect(screen.queryByLabelText(/métrica para recomendar/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/sintétic/i)).not.toBeInTheDocument();
  });

  it("presenta cada modelo como flashcard con la comparación y el detalle al voltearla", async () => {
    api.trainingService.run.mockResolvedValue(COMPLETED_RUN);
    loginAs(ADMIN);
    renderApp("/reentrenamiento?run=9");
    const card = await screen.findByRole("article", { name: /Regresión Logística v20261028100000/ });
    const front = within(card);
    expect(front.queryByText(/recomendado/i)).not.toBeInTheDocument();
    expect(front.getByText("0,650")).toBeInTheDocument(); // F1 nuevo
    expect(front.getByText("0,720")).toBeInTheDocument(); // F1 del modelo activo
    expect(front.getByText("-0,070")).toBeInTheDocument(); // diferencia
    expect(front.getByText(/comparación orientativa/)).toBeInTheDocument();
    await userEvent.click(front.getByRole("button", { name: /ver detalle/i }));
    expect(card).toHaveClass("flipped");
    expect(front.getByLabelText("Matriz de confusión del conjunto de prueba")).toBeInTheDocument();
    expect(front.getByText(/datasets distintos/)).toBeInTheDocument();
    await userEvent.click(front.getByRole("button", { name: /volver/i }));
    expect(card).not.toHaveClass("flipped");
  });

  it("el reporte de actividad administrativa ya no existe", async () => {
    loginAs(ADMIN);
    renderApp("/reportes");
    await screen.findByText("Estudiantes analizados");
    expect(screen.queryByRole("tab", { name: /actividad/i })).not.toBeInTheDocument();
  });
});
