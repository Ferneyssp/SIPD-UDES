import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { authService } from "../services/api";
import { onSessionExpired } from "../services/apiClient";
import { tokenStorage } from "../services/tokenStorage";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => (tokenStorage.getAccess() ? tokenStorage.getUser() : null));
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

  // Revalida el perfil al cargar la aplicación (rol o estado pudieron cambiar).
  useEffect(() => {
    if (!tokenStorage.getAccess()) return;
    authService
      .me()
      .then((profile) => {
        tokenStorage.saveUser(profile);
        setUser(profile);
      })
      .catch(() => {});
  }, []);

  const login = useCallback(async (username, password, remember) => {
    const response = await authService.login(username, password);
    tokenStorage.save(response, remember);
    setSessionExpired(false);
    setUser(response.user);
    return response.user;
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokenStorage.getRefresh();
    try {
      if (refresh) await authService.logout(refresh);
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
    () => ({ user, isAuthenticated: Boolean(user), login, logout, logoutLocal, refreshProfile, sessionExpired }),
    [user, login, logout, logoutLocal, refreshProfile, sessionExpired],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
