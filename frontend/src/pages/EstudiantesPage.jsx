import { BellRing, ChevronRight, Sheet, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import DataTable from "../components/DataTable";
import Filter, { FilterBar } from "../components/Filter";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import RiskBadge, { RiskBar, RiskChange } from "../components/RiskBadge";
import SearchBar from "../components/SearchBar";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useDebounce } from "../hooks/useDebounce";
import { useFilters } from "../hooks/useFilters";
import { studentService } from "../services/api";
import { blobErrorToJson, saveBlobResponse } from "../utils/download";
import { getErrorMessage } from "../utils/errors";
import { formatDate, formatNumber, shortProgram } from "../utils/format";

const PAGE_SIZE = 10;
const SEMESTERS = Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: `Semestre ${i + 1}` }));
const ORDERINGS = [
  { value: "-risk_change", label: "Mayor aumento del riesgo" },
  { value: "anonymous_code", label: "Código" },
];
const TRENDS = [{ value: "up", label: "En aumento" }, { value: "down", label: "En descenso" }];

/**
 * Lista de trabajo priorizada (población → filtro → lista → ficha): por defecto de mayor a menor
 * riesgo estimado, con el cambio frente al periodo anterior y las alertas abiertas.
 */
export default function EstudiantesPage() {
  const navigate = useNavigate();
  const { config, programs } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const [search, setSearch] = useState(filters.search || "");
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);
  const debouncedSearch = useDebounce(search);
  const page = Number(filters.page || 1);

  useEffect(() => {
    if ((filters.search || "") !== debouncedSearch) setFilter("search", debouncedSearch);
  }, [debouncedSearch, filters.search, setFilter]);

  const { data, loading, error: loadError, reload } = useApi(
    () => studentService.list({ ...filters, page, page_size: PAGE_SIZE }),
    [JSON.stringify(filters)],
    { errorMessage: "Error al cargar los estudiantes." },
  );

  const { page: _page, ...activeFilters } = filters;
  const exportCsv = async () => {
    setExporting(true);
    setError(null);
    try {
      saveBlobResponse(await studentService.exportCsv(activeFilters), "sipd_estudiantes.csv");
    } catch (err) {
      setError(getErrorMessage(await blobErrorToJson(err), "No se pudo exportar el listado."));
    } finally {
      setExporting(false);
    }
  };

  const optionLabel = (options, value) => options.find((o) => String(o.value) === String(value))?.label || value;
  const chipLabels = {
    search: (v) => `Búsqueda: ${v}`,
    program: (v) => `Programa: ${optionLabel(programs.map((p) => ({ value: p.code, label: p.name })), v)}`,
    semester: (v) => `Semestre ${v}`,
    risk_level: (v) => `Riesgo: ${optionLabel((config?.risk_levels || []).map((l) => ({ value: l.code, label: l.label })), v)}`,
    academic_status: (v) => `Estado: ${v}`,
    followup_status: (v) => `Seguimiento: ${optionLabel(config?.followup_statuses || [], v)}`,
    trend: (v) => `Tendencia: ${optionLabel(TRENDS, v)}`,
    alert: () => "Con alerta abierta",
    ordering: (v) => `Orden: ${optionLabel(ORDERINGS, v)}`,
  };
  const chips = Object.entries(activeFilters).filter(([key, value]) => value && chipLabels[key]);

  const columns = [
    { key: "anonymous_code", header: "ID anonimizado", render: (row) => <Link className="link-strong" to={`/estudiantes/${row.anonymous_code}`}>{row.anonymous_code}</Link> },
    { key: "program", header: "Programa", render: (row) => <span title={row.program}>{shortProgram(row.program)}</span> },
    { key: "semester", header: "Semestre", align: "center" },
    { key: "risk", header: "Riesgo estimado", render: (row) => <RiskBar probability={row.current_probability} level={row.current_risk_level} compact /> },
    { key: "level", header: "Nivel", render: (row) => <RiskBadge level={row.current_risk_level} /> },
    { key: "change", header: "Cambio", render: (row) => <RiskChange points={row.risk_change_points} /> },
    { key: "alert", header: "Alerta", render: (row) => (row.open_alert_status ? <span className="alert-flag"><BellRing size={14} aria-hidden="true" /> Abierta</span> : <span className="text-muted">—</span>) },
    { key: "followup", header: "Seguimiento", render: (row) => row.latest_followup_status_display },
    { key: "date", header: "Predicción", render: (row) => (row.current_prediction_date ? `${formatDate(row.current_prediction_date)} (${row.current_prediction_period})` : "—") },
    {
      key: "action", header: "Acción", align: "right",
      render: (row) => <Link className="link-action" to={`/estudiantes/${row.anonymous_code}`}>Ver ficha <ChevronRight size={16} aria-hidden="true" /></Link>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Estudiantes"
        badge={data ? `${formatNumber(data.count)} registros` : null}
        description="Ordenados de mayor a menor riesgo estimado. Los datos se actualizan con la carga institucional; aquí son de sólo lectura."
        actions={<Button variant="secondary" icon={Sheet} loading={exporting} onClick={exportCsv}>Exportar CSV</Button>}
      />
      {error && <Alert type="error" onClose={() => setError(null)}>{error}</Alert>}

      <FilterBar onClear={() => { setSearch(""); clearFilters(); }} hasActive={chips.length > 0}>
        <SearchBar value={search} onChange={setSearch} placeholder="Buscar por código (E001) o programa..." className="grow" />
        <Filter label="Programa" value={filters.program} onChange={(v) => setFilter("program", v)} options={programs.map((p) => ({ value: p.code, label: p.name }))} />
        <Filter label="Semestre" value={filters.semester} onChange={(v) => setFilter("semester", v)} options={SEMESTERS} />
        <Filter label="Riesgo" value={filters.risk_level} onChange={(v) => setFilter("risk_level", v)}
          options={(config?.risk_levels || []).map((l) => ({ value: l.code, label: l.label })).reverse()} />
        <Filter label="Tendencia" value={filters.trend} onChange={(v) => setFilter("trend", v)} options={TRENDS} allLabel="Todas" />
        <Filter label="Alerta" value={filters.alert} onChange={(v) => setFilter("alert", v)} options={[{ value: "open", label: "Con alerta abierta" }]} />
        <Filter label="Estado" value={filters.academic_status} onChange={(v) => setFilter("academic_status", v)}
          options={config?.academic_statuses || []} />
        <Filter label="Seguimiento" value={filters.followup_status} onChange={(v) => setFilter("followup_status", v)}
          options={config?.followup_statuses || []} />
        <Filter label="Orden" value={filters.ordering} onChange={(v) => setFilter("ordering", v)} options={ORDERINGS} allLabel="Mayor riesgo" />
      </FilterBar>

      {chips.length > 0 && (
        <ul className="filter-chips" aria-label="Filtros activos">
          {chips.map(([key, value]) => (
            <li key={key}>
              <button type="button" className="filter-chip" onClick={() => { if (key === "search") setSearch(""); setFilter(key, ""); }}
                aria-label={`Quitar filtro ${chipLabels[key](value)}`}>
                {chipLabels[key](value)} <X size={13} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <Card padded={false}>
        <DataTable
          columns={columns}
          rows={data?.results}
          loading={loading}
          error={loadError}
          onRetry={reload}
          emptyTitle="No se encontraron estudiantes."
          emptyDescription="Pruebe con otros filtros o términos de búsqueda."
          onRowClick={(row) => navigate(`/estudiantes/${row.anonymous_code}`)}
          caption="Listado de estudiantes"
        />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPageChange={(p) => setFilter("page", String(p))} />}
      </Card>
    </>
  );
}
