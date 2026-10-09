import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Filtros sincronizados con la URL (?program=SIS&page=2), para que un filtro
 * pueda compartirse o conservarse al navegar hacia atrás.
 */
export function useFilters(defaults = {}) {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(() => {
    const values = { ...defaults };
    for (const [key, value] of searchParams.entries()) values[key] = value;
    return values;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const setFilter = useCallback(
    (key, value) => {
      setSearchParams((previous) => {
        const next = new URLSearchParams(previous);
        if (value === "" || value === null || value === undefined) next.delete(key);
        else next.set(key, value);
        if (key !== "page") next.delete("page");
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  const clearFilters = useCallback(() => setSearchParams({}, { replace: true }), [setSearchParams]);

  return { filters, setFilter, clearFilters };
}
