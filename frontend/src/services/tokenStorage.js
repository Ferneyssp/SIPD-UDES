/**
 * Almacenamiento de tokens JWT.
 * - "Recordar sesión" => localStorage (persiste al cerrar el navegador).
 * - Sin recordar      => sessionStorage (se borra al cerrar la pestaña).
 */
const ACCESS_KEY = "sipd.access";
const REFRESH_KEY = "sipd.refresh";
const USER_KEY = "sipd.user";

function safeStorage(kind) {
  try {
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

function activeStorage() {
  const local = safeStorage("local");
  if (local?.getItem(REFRESH_KEY)) return local;
  return safeStorage("session");
}

export const tokenStorage = {
  save({ access, refresh, user }, remember) {
    this.clear();
    const storage = safeStorage(remember ? "local" : "session");
    if (!storage) return;
    storage.setItem(ACCESS_KEY, access);
    storage.setItem(REFRESH_KEY, refresh);
    if (user) storage.setItem(USER_KEY, JSON.stringify(user));
  },
  updateTokens({ access, refresh }) {
    const storage = activeStorage();
    if (!storage) return;
    if (access) storage.setItem(ACCESS_KEY, access);
    if (refresh) storage.setItem(REFRESH_KEY, refresh);
  },
  saveUser(user) {
    activeStorage()?.setItem(USER_KEY, JSON.stringify(user));
  },
  getAccess: () => activeStorage()?.getItem(ACCESS_KEY) || null,
  getRefresh: () => activeStorage()?.getItem(REFRESH_KEY) || null,
  getUser() {
    try {
      const raw = activeStorage()?.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },
  clear() {
    for (const storage of [safeStorage("local"), safeStorage("session")]) {
      storage?.removeItem(ACCESS_KEY);
      storage?.removeItem(REFRESH_KEY);
      storage?.removeItem(USER_KEY);
    }
  },
};
