import { BellRing, ChevronRight, UserCheck } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import Card, { StatCard } from "../components/Card";
import DataTable from "../components/DataTable";
import Filter, { FilterBar } from "../components/Filter";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import { RiskChange } from "../components/RiskBadge";
import StatusBadge from "../components/StatusBadge";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../hooks/useFilters";
import { alertService } from "../services/api";
import { formatDateTime, formatNumber, formatProbability, shortProgram } from "../utils/format";

const PAGE_SIZE = 15;
export const ALERT_STATUS_CLASS = { ABIERTA: "status-danger", EN_ATENCION: "status-warning", CERRADA: "status-muted" };
// Sin estado en la URL se muestran las pendientes (abiertas y en atención).
const STATUS_OPTIONS = [
  { value: "ABIERTA", label: "Abiertas" }, { value: "EN_ATENCION", label: "En atención" },
  { value: "CERRADA", label: "Cerradas" }, { value: "all", label: "Todas" },
];
const PRIORITY_CLASS = { ALTA: "risk-high", MEDIA: "risk-medium" };

function AlertList() {
  const navigate = useNavigate();
  const { programs, periods } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const page = Number(filters.page || 1);
  const summary = useApi(() => alertService.summary(), []);
  const { data, loading, error, reload } = useApi(
    () => alertService.list({ ...filters, status: filters.status || "pending", page, page_size: PAGE_SIZE }), [JSON.stringify(filters)],
    { errorMessage: "Error al cargar las alertas." },
  );
  const columns = [
    { key: "priority", header: "Prioridad", render: (a) => <span className={`badge ${PRIORITY_CLASS[a.priority]}`}>{a.priority_display}</span> },
    { key: "created_at", header: "Fecha", render: (a) => formatDateTime(a.created_at) },
    { key: "student_code", header: "Estudiante", render: (a) => <Link className="link-strong" to={`/estudiantes/${a.student_code}`} onClick={(e) => e.stopPropagation()}>{a.student_code}</Link> },
    { key: "program", header: "Programa", render: (a) => shortProgram(a.program) },
    { key: "reason_display", header: "Motivo", className: "cell-wrap" },
    { key: "probability", header: "Riesgo", render: (a) => formatProbability(a.probability) },
    { key: "change", header: "Cambio", render: (a) => <RiskChange points={a.change_points} /> },
    { key: "assigned_to_name", header: "Responsable", render: (a) => a.assigned_to_name || <span className="text-muted">Sin asignar</span> },
    { key: "status", header: "Estado", render: (a) => <StatusBadge className={ALERT_STATUS_CLASS[a.status]} label={a.status_display} /> },
    { key: "open", header: "", align: "right", render: (a) => <Link className="link-action" to={manageAlertPath(a.student_code)} onClick={(e) => e.stopPropagation()}>Gestionar <ChevronRight size={16} aria-hidden="true" /></Link> },
  ];
  const counts = summary.data;
  return (
    <>
      <PageHeader title="Alertas tempranas" badge={data ? `${formatNumber(data.count)} alertas` : null}
        description="Se generan al registrar predicciones: nivel de riesgo estimado Alto o aumento frente al periodo anterior. Se gestionan registrando el seguimiento del estudiante: la alerta pasa a 'En atención' y se cierra cuando el seguimiento se marca Atendido o Cerrado." />
      {counts && (
        <div className="stats-grid four">
          <StatCard label="Abiertas" value={formatNumber(counts.open)} tone="high" icon={BellRing} to="/alertas?status=ABIERTA" />
          <StatCard label="En atención" value={formatNumber(counts.in_progress)} tone="medium" to="/alertas?status=EN_ATENCION" />
          <StatCard label="Sin responsable" value={formatNumber(counts.unassigned)} tone="info" to="/alertas?assigned=none" />
          <StatCard label="Asignadas a mí" value={formatNumber(counts.mine)} tone="neutral" icon={UserCheck} to="/alertas?assigned=me" />
        </div>
      )}
      <FilterBar onClear={clearFilters} hasActive={Object.keys(filters).some((k) => k !== "page")}>
        <Filter label="Estado" value={filters.status} onChange={(v) => setFilter("status", v)} options={STATUS_OPTIONS} allLabel="Pendientes" />
        <Filter label="Prioridad" value={filters.priority} onChange={(v) => setFilter("priority", v)} options={[{ value: "ALTA", label: "Alta" }, { value: "MEDIA", label: "Media" }]} />
        <Filter label="Responsable" value={filters.assigned} onChange={(v) => setFilter("assigned", v)} options={[{ value: "me", label: "Asignadas a mí" }, { value: "none", label: "Sin asignar" }]} />
        <Filter label="Programa" value={filters.program} onChange={(v) => setFilter("program", v)} options={programs.map((p) => ({ value: p.code, label: p.name }))} />
        <Filter label="Periodo" value={filters.period} onChange={(v) => setFilter("period", v)} options={periods.map((p) => ({ value: p.code, label: p.code }))} />
      </FilterBar>
      <Card padded={false}>
        <DataTable columns={columns} rows={data?.results} loading={loading} error={error} onRetry={reload}
          emptyTitle="No hay alertas para los filtros seleccionados." caption="Alertas tempranas" onRowClick={(a) => navigate(manageAlertPath(a.student_code))} />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPageChange={(p) => setFilter("page", String(p))} />}
      </Card>
    </>
  );
}

/** Las alertas se gestionan registrando el seguimiento del estudiante (abre el formulario ya filtrado). */
export function manageAlertPath(studentCode) {
  return `/seguimiento?student=${encodeURIComponent(studentCode)}&nuevo=1`;
}

export default function AlertasPage() {
  return <AlertList />;
}
