import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { authService } from "../services/api";
import { onSessionExpired, refreshAccessToken } from "../services/apiClient";
import { tokenStorage } from "../services/tokenStorage";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => (tokenStorage.getAccess() ? tokenStorage.getUser() : null));
  // Tras recargar la página no hay access token en memoria: se restaura con la cookie HttpOnly.
  const [initializing, setInitializing] = useState(() => !tokenStorage.getAccess() && tokenStorage.hasSession());
  const [sessionExpired, setSessionExpired] = useState(false);

  const logoutLocal = useCallback(() => {
    tokenStorage.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    onSessionExpired(() => {
      setSessionExpired(true);
      setUser(null);
    });
  }, []);

  // Restaura la sesión (si hace falta) y revalida el perfil: el rol o el estado pudieron cambiar.
  useEffect(() => {
    if (!tokenStorage.getAccess() && !tokenStorage.hasSession()) return;
    let cancelled = false;
    (async () => {
      try {
        if (!tokenStorage.getAccess()) await refreshAccessToken();
        const profile = await authService.me();
        if (cancelled) return;
        tokenStorage.saveUser(profile);
        setUser(profile);
      } catch {
        if (!cancelled && !tokenStorage.getAccess()) {
          tokenStorage.clear();
          setUser(null);
        }
      } finally {
        if (!cancelled) setInitializing(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (username, password, remember) => {
    const response = await authService.login(username, password, remember);
    tokenStorage.save(response, remember);
    setSessionExpired(false);
    setUser(response.user);
    return response.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      // Aunque falle la llamada, la sesión local se cierra.
    }
    logoutLocal();
  }, [logoutLocal]);

  const refreshProfile = useCallback(async () => {
    const profile = await authService.me();
    tokenStorage.saveUser(profile);
    setUser(profile);
    return profile;
  }, []);

  const value = useMemo(
    () => ({ user, isAuthenticated: Boolean(user), initializing, login, logout, logoutLocal, refreshProfile, sessionExpired }),
    [user, initializing, login, logout, logoutLocal, refreshProfile, sessionExpired],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
