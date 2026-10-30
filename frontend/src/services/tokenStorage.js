/**
 * Sesión en el navegador.
 * - El refresh token NO se guarda aquí: viaja en una cookie HttpOnly que JavaScript no puede leer.
 * - El access token (vida corta) vive sólo en memoria: se pierde al recargar y se renueva con la cookie.
 * - Sólo el perfil (sin secretos) se guarda para restaurar la interfaz: localStorage con "Recordar
 *   sesión" y sessionStorage sin él.
 */
const USER_KEY = "sipd.user";
let accessToken = null;

function safeStorage(kind) {
  try {
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

function activeStorage() {
  const local = safeStorage("local");
  if (local?.getItem(USER_KEY)) return local;
  return safeStorage("session");
}

export const tokenStorage = {
  save({ access, user }, remember) {
    this.clear();
    accessToken = access || null;
    if (user) safeStorage(remember ? "local" : "session")?.setItem(USER_KEY, JSON.stringify(user));
  },
  updateTokens({ access }) {
    if (access) accessToken = access;
  },
  saveUser(user) {
    activeStorage()?.setItem(USER_KEY, JSON.stringify(user));
  },
  getAccess: () => accessToken,
  /** Hay una sesión que puede restaurarse con la cookie (perfil guardado). */
  hasSession() {
    return Boolean(this.getUser());
  },
  getUser() {
    try {
      const raw = activeStorage()?.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },
  clear() {
    accessToken = null;
    for (const storage of [safeStorage("local"), safeStorage("session")]) {
      storage?.removeItem(USER_KEY);
      storage?.removeItem("sipd.access"); // claves de versiones anteriores
      storage?.removeItem("sipd.refresh");
    }
  },
};
