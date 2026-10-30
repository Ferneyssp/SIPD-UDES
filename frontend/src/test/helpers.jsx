import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { ConfigProvider } from "../context/ConfigContext";
import { tokenStorage } from "../services/tokenStorage";

export const ADMIN = {
  id: 1, username: "admin", email: "admin@sipd.demo", first_name: "Admin", last_name: "Demo",
  role: "ADMIN", role_display: "Administrador", is_active: true, programs: [], can_manage_users_effective: true,
};
/** Coordinador de un solo programa (ámbito restringido). */
export const COORDINATOR = {
  ...ADMIN, id: 2, username: "coordinador", role: "COORDINATOR", role_display: "Coordinador académico",
  can_manage_users_effective: false, programs: [{ id: 1, code: "SIS", name: "Ingeniería de Sistemas" }],
};

export const CONFIG = {
  risk_thresholds: { low: 0.3, medium: 0.6 },
  risk_levels: [
    { code: "BAJO", label: "Bajo", min: 0, max: 0.3 },
    { code: "MEDIO", label: "Medio", min: 0.3, max: 0.6 },
    { code: "ALTO", label: "Alto", min: 0.6, max: 1 },
  ],
  gpa_range: { min: 0, max: 5 },
  current_period: "2026-2",
  roles: [], academic_statuses: [{ value: "Activo", label: "Activo" }],
  followup_statuses: [{ value: "PENDIENTE", label: "Pendiente" }],
  intervention_types: [], feature_labels: {}, upload_max_mb: 5,
};
export const PROGRAMS = [{ id: 1, code: "SIS", name: "Ingeniería de Sistemas" }];
export const PERIODS = [{ id: 1, code: "2026-2" }];

export function loginAs(user) {
  tokenStorage.save({ access: "token", refresh: "refresh", user }, false);
}

export function renderWithProviders(ui, { route = "/", path = "*" } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <ConfigProvider>
          <Routes>
            <Route path="/login" element={<div>Página de login</div>} />
            <Route path={path} element={ui} />
          </Routes>
        </ConfigProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}
