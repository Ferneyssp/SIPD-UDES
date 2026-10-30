import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ROLES } from "../config/appConfig";
import { NAV_GROUPS, NAVIGATION, canAccessItem } from "../config/navigation";
import { AuthProvider } from "../context/AuthContext";
import { ConfigProvider } from "../context/ConfigContext";
import { tokenStorage } from "../services/tokenStorage";
import { ADMIN, CONFIG, COORDINATOR, PERIODS, PROGRAMS, loginAs } from "./helpers";

vi.mock("../services/api", () => ({
  cleanParams: (p) => p,
  authService: { login: vi.fn(), logout: vi.fn(), me: vi.fn(), changePassword: vi.fn(), requestPasswordReset: vi.fn(), confirmPasswordReset: vi.fn() },
  catalogService: { config: vi.fn(), programs: vi.fn(), periods: vi.fn() },
  studentService: { list: vi.fn(), get: vi.fn(), exportCsv: vi.fn() },
  predictionService: { summary: vi.fn(), get: vi.fn(), history: vi.fn(), run: vi.fn(), list: vi.fn() },
  followupService: { list: vi.fn(), responsibles: vi.fn() },
  alertService: { list: vi.fn(), get: vi.fn(), summary: vi.fn(), assign: vi.fn(), comment: vi.fn(), start: vi.fn(), close: vi.fn() },
  notificationService: { unreadCount: vi.fn(), list: vi.fn() },
  modelService: { list: vi.fn(), activate: vi.fn(), sync: vi.fn() },
  userService: { list: vi.fn() },
}));

const api = await import("../services/api");

const STUDENT = {
  id: 1, anonymous_code: "E001", program: "Ingeniería de Sistemas", program_code: "SIS", semester: 6, academic_status: "Activo",
  current_probability: 0.82, current_risk_level: "ALTO", current_prediction_date: "2026-08-26T10:00:00Z",
  current_prediction_period: "2026-2", current_prediction_id: 9, latest_followup_status: null,
  latest_followup_status_display: "Sin seguimiento", previous_probability: 0.6, risk_change_points: 22.0, open_alert_status: "ABIERTA",
  current_period: "2026-2", academic_records: [],
};
const PREDICTION = {
  id: 9, model_name: "Regresión Logística", model_version_label: "1", input_features: {},
  explanation: [
    { feature: "attendance_percentage", label: "Asistencia (%)", value: 60, direction: "asociada a mayor riesgo estimado" },
    { feature: "gpa", label: "Promedio del periodo", value: 3.9, direction: "asociada a menor riesgo estimado" },
  ],
};
const ALERT = {
  id: 4, student_code: "E001", program: "Ingeniería de Sistemas", academic_period: "2026-2", reason: "NIVEL_ALTO",
  reason_display: "Nivel de riesgo estimado Alto", priority: "ALTA", priority_display: "Alta", probability: 0.82,
  previous_probability: 0.6, change_points: 22, status: "ABIERTA", status_display: "Abierta", assigned_to: null,
  assigned_to_name: null, closed_by_name: null, closing_observation: "", created_at: "2026-10-28T10:00:00Z", comments: [],
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
  api.catalogService.config.mockResolvedValue({ ...CONFIG, roles: [{ value: "ADMIN", label: "Administrador" }, { value: "COORDINATOR", label: "Coordinador académico" }] });
  api.catalogService.programs.mockResolvedValue(PROGRAMS);
  api.catalogService.periods.mockResolvedValue(PERIODS);
  api.authService.me.mockImplementation(() => Promise.resolve(tokenStorage.getUser()));
  api.notificationService.unreadCount.mockResolvedValue({ unread: 0 });
  api.studentService.list.mockResolvedValue({ count: 1, results: [STUDENT] });
  api.studentService.get.mockResolvedValue(STUDENT);
  api.predictionService.get.mockResolvedValue(PREDICTION);
  api.predictionService.history.mockResolvedValue({ timeline: [] });
  api.followupService.list.mockResolvedValue({ count: 0, results: [] });
  api.followupService.responsibles.mockResolvedValue([{ id: 2, name: "Coordinación", role: "Coordinador académico" }]);
  api.alertService.list.mockResolvedValue({ count: 1, results: [ALERT] });
  api.alertService.get.mockResolvedValue(ALERT);
  api.alertService.summary.mockResolvedValue({ open: 1, in_progress: 0, closed: 0, unassigned: 1, mine: 0, recent: [ALERT] });
});

describe("Roles", () => {
  it("sólo existen Administrador y Coordinador", () => {
    expect(Object.values(ROLES).sort()).toEqual(["ADMIN", "COORDINATOR"]);
  });

  it("el menú se agrupa por tarea y el coordinador no ve la administración", () => {
    expect(NAV_GROUPS).toEqual(["Analizar", "Atender", "Administrar", "Cuenta"]);
    const coordinator = NAVIGATION.filter((i) => canAccessItem(i, COORDINATOR));
    expect(coordinator.some((i) => i.group === "Administrar")).toBe(false);
    expect(coordinator.map((i) => i.label)).toEqual(expect.arrayContaining(["Alertas", "Seguimiento", "Estudiantes"]));
    expect(NAVIGATION.filter((i) => canAccessItem(i, ADMIN)).map((i) => i.label)).not.toContain("Auditoría");
    expect(coordinator.map((i) => i.label)).not.toContain("Predicciones");
    expect(NAVIGATION.filter((i) => canAccessItem(i, ADMIN)).map((i) => i.label)).toContain("Predicciones");
  });
});

describe("Sesión", () => {
  it("el access token no se guarda en el almacenamiento del navegador y el refresh token no existe en JS", () => {
    tokenStorage.save({ access: "token-secreto", refresh: "refresh-secreto", user: ADMIN }, true);
    const stored = JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage });
    expect(stored).not.toContain("token-secreto");
    expect(stored).not.toContain("refresh-secreto");
    expect(tokenStorage.getAccess()).toBe("token-secreto");
    expect(tokenStorage.getUser().username).toBe("admin");
    tokenStorage.clear();
    expect(tokenStorage.getAccess()).toBeNull();
  });
});

describe("Ficha del estudiante", () => {
  it("es de sólo lectura y muestra cambio, rangos, factores separados y alertas", async () => {
    loginAs(ADMIN);
    renderApp("/estudiantes/E001");
    expect(await screen.findByRole("heading", { name: /Estudiante E001/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ejecutar predicción/i })).not.toBeInTheDocument();
    expect(screen.getAllByText("▲ +22,0 pts").length).toBeGreaterThan(0);
    expect(screen.getByText(/no es una certeza/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /rangos de los niveles/i }));
    expect(screen.getByRole("note")).toHaveTextContent("Alto:");
    expect(await screen.findByText(/Asociadas a mayor riesgo estimado/)).toBeInTheDocument();
    expect(screen.getByText(/Asociadas a menor riesgo estimado/)).toBeInTheDocument();
    expect(await screen.findByText("Nivel de riesgo estimado Alto")).toBeInTheDocument();
  });
});

describe("Listado de estudiantes", () => {
  it("no permite registrar estudiantes, muestra el cambio y exporta con los filtros activos", async () => {
    api.studentService.exportCsv.mockResolvedValue({ data: new Blob(["a"]), headers: {} });
    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    loginAs(ADMIN);
    renderApp("/estudiantes");
    expect(await screen.findAllByText("E001")).not.toHaveLength(0);
    expect(screen.queryByRole("button", { name: /registrar estudiante/i })).not.toBeInTheDocument();
    expect(screen.getByText("▲ +22,0 pts")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Tendencia"), { target: { value: "up" } });
    const chip = await screen.findByRole("button", { name: /quitar filtro tendencia/i });
    await userEvent.click(screen.getByRole("button", { name: /exportar csv/i }));
    expect(api.studentService.exportCsv).toHaveBeenCalledWith(expect.objectContaining({ trend: "up" }));
    await userEvent.click(chip);
    await waitFor(() => expect(api.studentService.list).toHaveBeenLastCalledWith(expect.not.objectContaining({ trend: "up" })));
  });
});

describe("Alertas tempranas", () => {
  it("lista las pendientes por defecto", async () => {
    loginAs(COORDINATOR);
    renderApp("/alertas");
    expect(await screen.findByRole("heading", { name: /Alertas tempranas/ })).toBeInTheDocument();
    expect(api.alertService.list).toHaveBeenCalledWith(expect.objectContaining({ status: "pending" }));
    expect(await screen.findByText("Nivel de riesgo estimado Alto")).toBeInTheDocument();
  });

  it("Gestionar lleva al seguimiento con el formulario abierto para el estudiante", async () => {
    loginAs(COORDINATOR);
    renderApp("/alertas");
    const link = await screen.findByRole("link", { name: /^gestionar/i });
    expect(link).toHaveAttribute("href", "/seguimiento?student=E001&nuevo=1");
    await userEvent.click(link);
    const dialog = await screen.findByRole("dialog", { name: /registrar nueva intervención/i });
    expect(within(dialog).getByLabelText(/estudiante \(código\)/i)).toHaveValue("E001");
    await waitFor(() => expect(api.followupService.responsibles).toHaveBeenCalledWith("E001"));
  });

  it("el administrador no figura como responsable por defecto", async () => {
    loginAs(ADMIN);
    renderApp("/seguimiento?student=E001&nuevo=1");
    const dialog = await screen.findByRole("dialog", { name: /registrar nueva intervención/i });
    const select = within(dialog).getByLabelText(/responsable/i);
    expect(select).toHaveValue("");
    expect(within(select).queryByText(/Administrador/)).not.toBeInTheDocument();
  });
});

describe("Inicio accionable", () => {
  it("las tarjetas abren el listado filtrado y se muestran alertas recientes", async () => {
    api.predictionService.summary.mockResolvedValue({
      period: "2026-2", totals: { students: 10, high: 2, medium: 3, low: 5, without_prediction: 0, high_pct: 20, medium_pct: 30, low_pct: 50, predictions: 10 },
      by_program: [{ program: "Ingeniería de Sistemas", ALTO: 2, MEDIO: 3, BAJO: 5 }], attention_total: 1, attention: [STUDENT],
      model: { available: true }, scope_restricted: true,
    });
    loginAs(COORDINATOR);
    renderApp("/inicio");
    const levelFilter = await screen.findByLabelText("Nivel de riesgo");
    expect(levelFilter).toHaveValue("");
    expect([...levelFilter.options].map((o) => o.text)).toEqual(["Todos", "Alto", "Medio", "Bajo"]);
    expect(api.predictionService.summary).toHaveBeenCalledWith(expect.not.objectContaining({ risk_level: expect.anything() }));
    fireEvent.change(levelFilter, { target: { value: "ALTO" } });
    await waitFor(() => expect(api.predictionService.summary).toHaveBeenLastCalledWith(expect.objectContaining({ risk_level: "ALTO" })));
    const high = await screen.findByRole("link", { name: /Riesgo alto: 2/ });
    expect(high).toHaveAttribute("href", "/estudiantes?risk_level=ALTO");
    expect(await screen.findByText("Alertas tempranas recientes")).toBeInTheDocument();
  });
});

const FOLLOWUP = {
  id: 7, student: "E001", program: "Ingeniería de Sistemas", follow_up_date: "2026-10-20", intervention_type: "TUTORIA",
  intervention_type_display: "Tutoría académica", observation: "Plan de refuerzo acordado.", user: 2, user_name: "Coordinación",
  status: "EN_SEGUIMIENTO", status_display: "En seguimiento",
};

describe("Historial y seguimiento", () => {
  it("el perfil muestra el historial de seguimiento sin Editar y permite registrar", async () => {
    api.followupService.list.mockResolvedValue({ count: 1, results: [FOLLOWUP] });
    loginAs(COORDINATOR);
    renderApp("/estudiantes/E001");
    const card = (await screen.findByRole("heading", { name: "Historial de seguimiento" })).closest("section");
    expect(await within(card).findByText("Plan de refuerzo acordado.")).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
    expect(within(card).getByRole("button", { name: /registrar seguimiento/i })).toBeInTheDocument();
  });

  it("Historial muestra el seguimiento del estudiante y ya no la evolución institucional", async () => {
    api.predictionService.history.mockResolvedValue({
      student: { id: 1, anonymous_code: "E001", program: "Ingeniería de Sistemas", semester: 6 }, timeline: [],
    });
    api.followupService.list.mockResolvedValue({ count: 1, results: [FOLLOWUP] });
    loginAs(COORDINATOR);
    renderApp("/historial?student=E001");
    expect(await screen.findByRole("heading", { name: "Historial de seguimiento" })).toBeInTheDocument();
    expect(screen.queryByText(/Evolución institucional/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
  });

  it("Seguimiento pide sólo el último registro de cada estudiante y permite editarlo", async () => {
    api.followupService.list.mockResolvedValue({ count: 1, results: [FOLLOWUP] });
    loginAs(COORDINATOR);
    renderApp("/seguimiento");
    expect(await screen.findByText("Plan de refuerzo acordado.")).toBeInTheDocument();
    expect(api.followupService.list).toHaveBeenCalledWith(expect.objectContaining({ latest: "true" }));
    expect(screen.getByRole("button", { name: /editar/i })).toBeInTheDocument();
  });
});

describe("Modelos disponibles", () => {
  const version = (id, algorithm, name, ver, f1, active = false, trained = "2026-10-01T10:00:00Z") => ({
    id, algorithm, name, version: ver, active, trained_at: trained,
    metrics: { accuracy: 0.8, precision: 0.6, recall: 0.7, f1, roc_auc: 0.85, threshold: 0.3 },
  });

  it("muestra una fila por algoritmo con selector de versión", async () => {
    api.predictionService.list.mockResolvedValue({ count: 0, results: [] });
    api.modelService.list.mockResolvedValue([
      version(1, "logistic_regression", "Regresión Logística", "A", 0.72, true, "2026-10-01T10:00:00Z"),
      version(2, "logistic_regression", "Regresión Logística", "B", 0.55, false, "2026-10-20T10:00:00Z"),
      version(3, "random_forest", "Random Forest", "A", 0.64),
      version(4, "xgboost", "XGBoost", "A", 0.67),
    ]);
    loginAs(ADMIN);
    renderApp("/predicciones");
    const select = await screen.findByLabelText("Versión de Regresión Logística");
    const table = select.closest("table");
    expect(within(table).getAllByRole("row")).toHaveLength(4); // encabezado + 3 algoritmos
    expect(select).toHaveValue("1"); // por defecto, la versión activa
    expect(within(table).getByText("0,720")).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "2" } });
    expect(within(table).getByText("0,550")).toBeInTheDocument();
    expect(within(select.closest("tr")).getByRole("button", { name: "Activar" })).toBeInTheDocument();
  });
});

describe("Contraseña", () => {
  it("el inicio de sesión confirma que la contraseña se actualizó y ofrece recuperarla", async () => {
    renderApp("/login?aviso=contrasena-actualizada");
    expect(await screen.findByText("Contraseña actualizada correctamente. Inicie sesión con su nueva contraseña.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "¿Olvidó su contraseña?" })).toHaveAttribute("href", "/recuperar-contrasena");
    expect(screen.getByAltText(/Escudo de la Universidad de Santander/)).toBeInTheDocument();
  });

  it("cambiar la contraseña desde el perfil lleva al login con el aviso de éxito", async () => {
    api.authService.changePassword.mockResolvedValue({ detail: "ok" });
    loginAs(COORDINATOR);
    renderApp("/perfil");
    await userEvent.type(await screen.findByLabelText(/contraseña actual/i), "Actual#2026xx");
    await userEvent.type(screen.getByLabelText(/^nueva contraseña/i), "Nueva#2026xxx");
    await userEvent.type(screen.getByLabelText(/confirmar/i), "Nueva#2026xxx");
    await userEvent.click(screen.getByRole("button", { name: /cambiar contraseña|actualizar contraseña|guardar/i }));
    expect(await screen.findByText(/Contraseña actualizada correctamente/)).toBeInTheDocument();
  });

  it("solicitar recuperación muestra la respuesta genérica", async () => {
    api.authService.requestPasswordReset.mockResolvedValue({ detail: "Si el correo pertenece a una cuenta activa, recibirá un enlace." });
    renderApp("/recuperar-contrasena");
    await userEvent.type(await screen.findByLabelText("Correo institucional"), "sis@udes.edu.co");
    await userEvent.click(screen.getByRole("button", { name: "Enviar enlace" }));
    expect(api.authService.requestPasswordReset).toHaveBeenCalledWith("sis@udes.edu.co");
    expect(await screen.findByText(/recibirá un enlace/)).toBeInTheDocument();
  });

  it("restablecer con un enlace vencido explica el error y permite pedir otro", async () => {
    api.authService.confirmPasswordReset.mockRejectedValue({ response: { status: 400, data: {
      detail: "El enlace no es válido o ya expiró. Solicite uno nuevo.", errors: { token: ["El enlace no es válido o ya expiró."] } } } });
    renderApp("/restablecer-contrasena/MQ/abc-123");
    await userEvent.type(await screen.findByLabelText("Nueva contraseña"), "Nueva#2026xxx");
    await userEvent.type(screen.getByLabelText("Confirmar contraseña"), "Nueva#2026xxx");
    await userEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));
    expect(api.authService.confirmPasswordReset).toHaveBeenCalledWith({ uid: "MQ", token: "abc-123", new_password: "Nueva#2026xxx", confirm_password: "Nueva#2026xxx" });
    expect(await screen.findByText(/ya expiró/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Solicitar un nuevo enlace" })).toBeInTheDocument();
  });
});
