import { useCallback, useEffect, useRef, useState } from "react";
import { getErrorMessage } from "../utils/errors";

/**
 * Ejecuta una función asíncrona y expone los estados loading / error / data.
 * Se vuelve a ejecutar cuando cambian las dependencias. Ignora respuestas
 * obsoletas (si el usuario cambia los filtros rápidamente).
 */
export function useApi(fetcher, deps = [], { enabled = true, errorMessage } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);
  const requestId = useRef(0);

  const execute = useCallback(async () => {
    const current = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (current === requestId.current) setData(result);
      return result;
    } catch (err) {
      if (current === requestId.current) setError(getErrorMessage(err, errorMessage));
      return null;
    } finally {
      if (current === requestId.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (enabled) execute();
    else setLoading(false);
  }, [execute, enabled]);

  return { data, loading, error, reload: execute, setData };
}
