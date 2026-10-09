import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { catalogService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { useAuth } from "./AuthContext";

const ConfigContext = createContext(null);

const EMPTY = {
  config: null,
  programs: [],
  periods: [],
};

/** Catálogos del sistema (umbrales, programas, periodos, estados) obtenidos del backend. */
export function ConfigProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [config, programs, periods] = await Promise.all([
        catalogService.config(),
        catalogService.programs(),
        catalogService.periods(),
      ]);
      setState({ config, programs, periods });
    } catch (err) {
      setError(getErrorMessage(err, "No se pudo cargar la configuración del sistema."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) load();
    else setState(EMPTY);
  }, [isAuthenticated, load]);

  const value = useMemo(() => ({ ...state, loading, error, reload: load }), [state, loading, error, load]);
  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useConfig() {
  const context = useContext(ConfigContext);
  if (!context) throw new Error("useConfig debe usarse dentro de ConfigProvider");
  return context;
}
