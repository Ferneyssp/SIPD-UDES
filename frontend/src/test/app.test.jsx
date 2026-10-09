import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import RiskBadge, { RiskBar } from "../components/RiskBadge";
import { AuthProvider } from "../context/AuthContext";
import { ConfigProvider } from "../context/ConfigContext";
import { NAVIGATION, canAccessItem } from "../config/navigation";
import { ADMIN, CONFIG, PERIODS, PROFESSOR, PROGRAMS, loginAs } from "./helpers";

vi.mock("../services/api", () => ({
  cleanParams: (p) => p,
  authService: { login: vi.fn(), logout: vi.fn(), me: vi.fn(), changePassword: vi.fn() },
  catalogService: { config: vi.fn(), programs: vi.fn(), periods: vi.fn() },
  studentService: { list: vi.fn(), get: vi.fn() },
  predictionService: { summary: vi.fn(), list: vi.fn(), trend: vi.fn(), history: vi.fn(), get: vi.fn() },
  modelService: { list: vi.fn() },
  followupService: { list: vi.fn(), responsibles: vi.fn() },
  uploadService: { list: vi.fn() },
  userService: { list: vi.fn() },
}));

const api = await import("../services/api");

const STUDENT = {
  id: 1, anonymous_code: "E001", program: "Ingeniería de Sistemas", program_code: "SIS", semester: 6,
  academic_status: "Activo", current_probability: 0.82, current_risk_level: "ALTO", current_risk_level_display: "Alto",
  current_prediction_date: "2026-08-26T10:00:00Z", current_prediction_period: "2026-2", current_prediction_id: 9,
  latest_followup_status: null, latest_followup_status_display: "Sin seguimiento",
};
const SUMMARY = {
  period: "2026-2",
  totals: { students: 10, high: 2, medium: 3, low: 5, without_prediction: 0, high_pct: 20, medium_pct: 30, low_pct: 50, predictions: 10 },
  by_program: [{ program: "Ingeniería de Sistemas", ALTO: 2, MEDIO: 3, BAJO: 5 }],
  attention_total: 1,
  attention: [STUDENT],
  model: { available: true, is_synthetic: false, name: "Random Forest" },
  scope_restricted: false,
};

function renderApp(route) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <ConfigProvider>
          <App />
        </ConfigProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.catalogService.config.mockResolvedValue(CONFIG);
  api.catalogService.programs.mockResolvedValue(PROGRAMS);
  api.catalogService.periods.mockResolvedValue(PERIODS);
  api.authService.me.mockImplementation(() => Promise.resolve(JSON.parse(sessionStorage.getItem("sipd.user"))));
  api.predictionService.summary.mockResolvedValue(SUMMARY);
  api.studentService.list.mockResolvedValue({ count: 1, results: [STUDENT] });
});

describe("Login", () => {
  it("muestra el formulario y permite mostrar la contraseña", async () => {
    renderApp("/login");
    expect(screen.getByRole("button", { name: /iniciar sesión/i })).toBeInTheDocument();
    const password = screen.getByLabelText("Contraseña");
    expect(password).toHaveAttribute("type", "password");
    await userEvent.click(screen.getByRole("button", { name: /mostrar contraseña/i }));
    expect(password).toHaveAttribute("type", "text");
  });

  it("muestra 'Credenciales incorrectas.' cuando falla el login", async () => {
    api.authService.login.mockRejectedValue({ response: { status: 401, data: { detail: "Credenciales incorrectas." } } });
    renderApp("/login");
    await userEvent.type(screen.getByLabelText(/usuario o correo/i), "admin");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mala");
    await userEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));
    expect(await screen.findByText("Credenciales incorrectas.")).toBeInTheDocument();
  });

  it("redirige a Inicio tras un login exitoso", async () => {
    api.authService.login.mockResolvedValue({ access: "a", refresh: "r", user: ADMIN });
    renderApp("/login");
    await userEvent.type(screen.getByLabelText(/usuario o correo/i), "admin");
    await userEvent.type(screen.getByLabelText("Contraseña"), "SipdDemo2026*");
    await userEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));
    expect(await screen.findByRole("heading", { name: /^Inicio/ })).toBeInTheDocument();
  });
});

describe("Protección de rutas", () => {
  it("sin sesión redirige al login", async () => {
    renderApp("/estudiantes");
    expect(await screen.findByRole("button", { name: /iniciar sesión/i })).toBeInTheDocument();
  });

  it("un profesor no puede acceder a Usuarios ni a Carga de datos", async () => {
    loginAs(PROFESSOR);
    renderApp("/usuarios");
    expect(await screen.findByText(/no tiene permisos/i)).toBeInTheDocument();
  });

  it("la ruta raíz lleva a Inicio", async () => {
    loginAs(ADMIN);
    renderApp("/");
    expect(await screen.findByRole("heading", { name: /^Inicio/ })).toBeInTheDocument();
  });
});

describe("Navegación", () => {
  it("usa 'Inicio' y no incluye Dashboard ni Estadísticas", () => {
    const labels = NAVIGATION.map((item) => item.label);
    expect(labels[0]).toBe("Inicio");
    expect(labels).not.toContain("Dashboard");
    expect(labels).not.toContain("Estadísticas");
    expect(NAVIGATION.some((item) => item.path.includes("estadisticas") || item.path.includes("dashboard"))).toBe(false);
  });

  it("oculta Usuarios y Carga de datos al profesor", () => {
    const visible = NAVIGATION.filter((item) => canAccessItem(item, PROFESSOR)).map((i) => i.label);
    expect(visible).not.toContain("Usuarios");
    expect(visible).not.toContain("Carga de datos");
    expect(NAVIGATION.filter((item) => canAccessItem(item, ADMIN)).map((i) => i.label)).toContain("Usuarios");
  });

  it("la ruta /estadisticas no existe", async () => {
    loginAs(ADMIN);
    renderApp("/estadisticas");
    expect(await screen.findByText(/la página solicitada no existe/i)).toBeInTheDocument();
  });
});

describe("Inicio", () => {
  it("renderiza tarjetas y la tabla de estudiantes que requieren atención", async () => {
    loginAs(ADMIN);
    renderApp("/inicio");
    expect(await screen.findByText("Total de estudiantes")).toBeInTheDocument();
    expect(screen.getByText("Predicciones realizadas")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Estudiantes que requieren atención/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "E001" })).toBeInTheDocument();
    expect(screen.queryByText(/dashboard/i)).not.toBeInTheDocument();
  });

  it("muestra un mensaje de error si falla la carga", async () => {
    api.predictionService.summary.mockRejectedValue({ response: { status: 500, data: {} } });
    loginAs(ADMIN);
    renderApp("/inicio");
    expect(await screen.findByText("Error interno del servidor.")).toBeInTheDocument();
  });
});

describe("Estudiantes", () => {
  it("muestra la tabla y aplica filtros", async () => {
    loginAs(ADMIN);
    renderApp("/estudiantes");
    expect(await screen.findByText("E001")).toBeInTheDocument();
    expect(screen.getByText("82,0 %")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Riesgo"), { target: { value: "ALTO" } });
    await waitFor(() =>
      expect(api.studentService.list).toHaveBeenLastCalledWith(expect.objectContaining({ risk_level: "ALTO" })),
    );
  });

  it("muestra estado vacío cuando no hay resultados", async () => {
    api.studentService.list.mockResolvedValue({ count: 0, results: [] });
    loginAs(ADMIN);
    renderApp("/estudiantes");
    expect(await screen.findByText("No se encontraron estudiantes.")).toBeInTheDocument();
  });
});

describe("Visualización de riesgo", () => {
  it("el nivel siempre incluye texto, no sólo color", () => {
    render(<RiskBadge level="ALTO" />);
    expect(screen.getByText("Alto")).toBeInTheDocument();
  });

  it("la barra de riesgo expone el porcentaje de forma accesible", () => {
    render(<RiskBar probability={0.4567} level="MEDIO" />);
    expect(screen.getByText("45,7 %")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-label", expect.stringContaining("Medio"));
  });

  it("sin predicción muestra un texto explícito", () => {
    render(<RiskBadge level={null} />);
    expect(screen.getByText("Sin predicción")).toBeInTheDocument();
  });
});
