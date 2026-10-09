import { Activity, BarChart3, ClipboardList, History, Home, UploadCloud, UserCircle, Users, UserCog } from "lucide-react";
import { ROLES } from "./appConfig";

const ALL = [ROLES.ADMIN, ROLES.COORDINATOR, ROLES.PROFESSOR];

/**
 * Menú lateral. El módulo principal es "Inicio".
 * No existe módulo "Estadísticas": el resumen se integra en Inicio.
 * `canAccess` recibe el usuario y decide la visibilidad según su rol.
 */
export const NAVIGATION = [
  { path: "/inicio", label: "Inicio", icon: Home, roles: ALL },
  { path: "/estudiantes", label: "Estudiantes", icon: Users, roles: ALL },
  { path: "/predicciones", label: "Predicciones", icon: BarChart3, roles: ALL },
  { path: "/historial", label: "Historial", icon: History, roles: ALL },
  { path: "/seguimiento", label: "Seguimiento", icon: Activity, roles: ALL },
  { path: "/carga-datos", label: "Carga de datos", icon: UploadCloud, roles: [ROLES.ADMIN] },
  {
    path: "/usuarios",
    label: "Usuarios",
    icon: UserCog,
    roles: [ROLES.ADMIN],
    canAccess: (user) => Boolean(user?.can_manage_users_effective),
  },
  { path: "/perfil", label: "Perfil", icon: UserCircle, roles: ALL },
];

export function canAccessItem(item, user) {
  if (!user) return false;
  if (item.canAccess) return item.canAccess(user);
  return item.roles.includes(user.role);
}

export const PAGE_META = {
  "/inicio": { subtitle: "Vista general del riesgo estimado y estudiantes que requieren atención" },
  "/estudiantes": { subtitle: "Búsqueda, filtros y detalle individual de estudiantes" },
  "/predicciones": { subtitle: "Predicciones generadas por los modelos de Machine Learning" },
  "/historial": { subtitle: "Evolución del riesgo estimado a través de los periodos académicos" },
  "/seguimiento": { subtitle: "Registro, control y acompañamiento de estudiantes identificados para seguimiento" },
  "/carga-datos": { subtitle: "Carga y validación de información académica en formato CSV" },
  "/usuarios": { subtitle: "Administración de usuarios y roles del sistema" },
  "/perfil": { subtitle: "Información de la cuenta y seguridad" },
};

export const DEFAULT_ICON = ClipboardList;
