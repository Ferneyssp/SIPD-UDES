import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import { ROLES } from "./config/appConfig";
import MainLayout from "./layouts/MainLayout";
import CargaDatosPage from "./pages/CargaDatosPage";
import EstudianteDetallePage from "./pages/EstudianteDetallePage";
import EstudiantesPage from "./pages/EstudiantesPage";
import HistorialPage from "./pages/HistorialPage";
import InicioPage from "./pages/InicioPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import PerfilPage from "./pages/PerfilPage";
import PrediccionesPage from "./pages/PrediccionesPage";
import SeguimientoPage from "./pages/SeguimientoPage";
import UsuariosPage from "./pages/UsuariosPage";

/**
 * Rutas de la aplicación. El módulo principal es /inicio.
 * No existen rutas /dashboard ni /estadisticas.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/inicio" replace />} />
        <Route path="/inicio" element={<InicioPage />} />
        <Route path="/estudiantes" element={<EstudiantesPage />} />
        <Route path="/estudiantes/:code" element={<EstudianteDetallePage />} />
        <Route path="/predicciones" element={<PrediccionesPage />} />
        <Route path="/historial" element={<HistorialPage />} />
        <Route path="/seguimiento" element={<SeguimientoPage />} />
        <Route
          path="/carga-datos"
          element={<ProtectedRoute roles={[ROLES.ADMIN]}><CargaDatosPage /></ProtectedRoute>}
        />
        <Route
          path="/usuarios"
          element={<ProtectedRoute check={(user) => user.can_manage_users_effective}><UsuariosPage /></ProtectedRoute>}
        />
        <Route path="/perfil" element={<PerfilPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
