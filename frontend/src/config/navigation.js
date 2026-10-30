import { Activity, BarChart3, Bell, BellRing, BrainCog, ClipboardList, FileBarChart2, History, Home, UploadCloud, UserCircle, Users, UserCog } from "lucide-react";
import { ROLES } from "./appConfig";

const ALL = [ROLES.ADMIN, ROLES.COORDINATOR];

/**
 * Menú lateral agrupado por tarea (como Connect / Advise / Report en Civitas):
 * Analizar → Atender → Administrar. El módulo principal es "Inicio".
 * `canAccess` recibe el usuario y decide la visibilidad según su rol.
 */
export const NAV_GROUPS = ["Analizar", "Atender", "Administrar", "Cuenta"];

export const NAVIGATION = [
  { path: "/inicio", label: "Inicio", icon: Home, roles: ALL, group: "Analizar" },
  { path: "/estudiantes", label: "Estudiantes", icon: Users, roles: ALL, group: "Analizar" },
  { path: "/predicciones", label: "Predicciones", icon: BarChart3, roles: [ROLES.ADMIN], group: "Analizar" },
  { path: "/historial", label: "Historial", icon: History, roles: ALL, group: "Analizar" },
  { path: "/reportes", label: "Reportes", icon: FileBarChart2, roles: ALL, group: "Analizar" },
  { path: "/alertas", label: "Alertas", icon: BellRing, roles: ALL, group: "Atender" },
  { path: "/seguimiento", label: "Seguimiento", icon: Activity, roles: ALL, group: "Atender" },
  { path: "/carga-datos", label: "Carga de datos", icon: UploadCloud, roles: [ROLES.ADMIN], group: "Administrar" },
  { path: "/reentrenamiento", label: "Reentrenamiento", icon: BrainCog, roles: [ROLES.ADMIN], group: "Administrar" },
  {
    path: "/usuarios",
    label: "Usuarios",
    icon: UserCog,
    roles: [ROLES.ADMIN],
    group: "Administrar",
    canAccess: (user) => Boolean(user?.can_manage_users_effective),
  },
  { path: "/notificaciones", label: "Notificaciones", icon: Bell, roles: ALL, group: "Cuenta" },
  { path: "/perfil", label: "Perfil", icon: UserCircle, roles: ALL, group: "Cuenta" },
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
  "/reportes": { subtitle: "Reporte de riesgo estimado con exportación PDF y CSV" },
  "/reentrenamiento": { subtitle: "Reentrenamiento, evaluación, aprobación y activación de los modelos de Machine Learning" },
  "/alertas": { subtitle: "Alertas tempranas: estudiantes con riesgo estimado alto o en aumento que requieren atención" },
  "/notificaciones": { subtitle: "Avisos de los procesos del sistema" },
  "/usuarios": { subtitle: "Administración de usuarios y roles del sistema" },
  "/perfil": { subtitle: "Información de la cuenta y seguridad" },
};

export const DEFAULT_ICON = ClipboardList;
