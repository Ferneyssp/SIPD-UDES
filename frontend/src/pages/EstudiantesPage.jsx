import { ArrowDownWideNarrow, ChevronRight, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import DataTable from "../components/DataTable";
import Filter, { FilterBar } from "../components/Filter";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import RiskBadge, { RiskBar } from "../components/RiskBadge";
import SearchBar from "../components/SearchBar";
import StudentFormModal from "../components/StudentFormModal";
import { ROLES } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useDebounce } from "../hooks/useDebounce";
import { useFilters } from "../hooks/useFilters";
import { studentService } from "../services/api";
import { formatDate, formatNumber, shortProgram } from "../utils/format";

const PAGE_SIZE = 10;
const SEMESTERS = Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: `Semestre ${i + 1}` }));

export default function EstudiantesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { config, programs } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const [search, setSearch] = useState(filters.search || "");
  const [showCreate, setShowCreate] = useState(false);
  const debouncedSearch = useDebounce(search);
  const page = Number(filters.page || 1);

  useEffect(() => {
    if ((filters.search || "") !== debouncedSearch) setFilter("search", debouncedSearch);
  }, [debouncedSearch, filters.search, setFilter]);

  const { data, loading, error, reload } = useApi(
    () => studentService.list({ ...filters, page, page_size: PAGE_SIZE }),
    [JSON.stringify(filters)],
    { errorMessage: "Error al cargar los estudiantes." },
  );

  const sortedByRisk = filters.ordering === "-current_probability";
  const columns = [
    { key: "anonymous_code", header: "ID anonimizado", render: (row) => <Link className="link-strong" to={`/estudiantes/${row.anonymous_code}`}>{row.anonymous_code}</Link> },
    { key: "program", header: "Programa", render: (row) => <span title={row.program}>{shortProgram(row.program)}</span> },
    { key: "semester", header: "Semestre", align: "center" },
    { key: "academic_status", header: "Estado académico" },
    { key: "risk", header: "Riesgo actual", render: (row) => <RiskBar probability={row.current_probability} level={row.current_risk_level} compact /> },
    { key: "level", header: "Nivel de riesgo", render: (row) => <RiskBadge level={row.current_risk_level} /> },
    { key: "date", header: "Fecha de predicción", render: (row) => (row.current_prediction_date ? `${formatDate(row.current_prediction_date)} (${row.current_prediction_period})` : "—") },
    {
      key: "action", header: "Acción", align: "right",
      render: (row) => <Link className="link-action" to={`/estudiantes/${row.anonymous_code}`}>Ver perfil <ChevronRight size={16} aria-hidden="true" /></Link>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Gestión de Estudiantes"
        badge={data ? `${formatNumber(data.count)} registros` : null}
        actions={user.role === ROLES.ADMIN && <Button icon={Plus} onClick={() => setShowCreate(true)}>Registrar estudiante</Button>}
      />

      <FilterBar onClear={() => { setSearch(""); clearFilters(); }} hasActive={Object.keys(filters).length > 0}>
        <SearchBar value={search} onChange={setSearch} placeholder="Buscar por código (E001) o programa..." className="grow" />
        <Filter label="Programa" value={filters.program} onChange={(v) => setFilter("program", v)} options={programs.map((p) => ({ value: p.code, label: p.name }))} />
        <Filter label="Semestre" value={filters.semester} onChange={(v) => setFilter("semester", v)} options={SEMESTERS} />
        <Filter label="Riesgo" value={filters.risk_level} onChange={(v) => setFilter("risk_level", v)}
          options={(config?.risk_levels || []).map((l) => ({ value: l.code, label: l.label })).reverse()} />
        <Filter label="Estado" value={filters.academic_status} onChange={(v) => setFilter("academic_status", v)}
          options={config?.academic_statuses || []} />
        <Filter label="Seguimiento" value={filters.followup_status} onChange={(v) => setFilter("followup_status", v)}
          options={config?.followup_statuses || []} />
        <Button variant={sortedByRisk ? "primary" : "secondary"} size="sm" icon={ArrowDownWideNarrow}
          aria-pressed={sortedByRisk}
          onClick={() => setFilter("ordering", sortedByRisk ? "" : "-current_probability")}>
          Mayor riesgo primero
        </Button>
      </FilterBar>

      <Card padded={false}>
        <DataTable
          columns={columns}
          rows={data?.results}
          loading={loading}
          error={error}
          onRetry={reload}
          emptyTitle="No se encontraron estudiantes."
          emptyDescription="Pruebe con otros filtros o términos de búsqueda."
          onRowClick={(row) => navigate(`/estudiantes/${row.anonymous_code}`)}
          caption="Listado de estudiantes"
        />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPageChange={(p) => setFilter("page", String(p))} />}
      </Card>

      <StudentFormModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSaved={(student) => { setShowCreate(false); navigate(`/estudiantes/${student.anonymous_code}`); }}
      />
    </>
  );
}
