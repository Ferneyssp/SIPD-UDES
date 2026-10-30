import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import EmptyState from "./EmptyState";
import Loading from "./Loading";
import { ShieldAlert } from "lucide-react";

/**
 * Protege rutas: exige sesión y, opcionalmente, un rol o permiso.
 * roles: lista de roles permitidos. check: función (user) => boolean.
 */
export default function ProtectedRoute({ children, roles, check }) {
  const { user, sessionExpired, initializing } = useAuth();
  const location = useLocation();
  if (initializing) return <Loading message="Restaurando la sesión..." fullPage />;
  if (!user) {
    const reason = sessionExpired ? "?expired=1" : "";
    return <Navigate to={`/login${reason}`} replace state={{ from: location.pathname + location.search }} />;
  }
  const allowed = check ? check(user) : !roles || roles.includes(user.role);
  if (!allowed) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="No tiene permisos para acceder a esta sección."
        description="Si considera que es un error, contacte al administrador del sistema."
      />
    );
  }
  return children;
}
