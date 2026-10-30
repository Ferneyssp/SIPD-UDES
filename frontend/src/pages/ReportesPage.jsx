import { AlertTriangle, FileDown, FileText, Sheet, Users } from "lucide-react";
import { useState } from "react";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card, { StatCard } from "../components/Card";
import DataTable from "../components/DataTable";
import ErrorMessage from "../components/ErrorMessage";
import Filter, { FilterBar } from "../components/Filter";
import Loading from "../components/Loading";
import PageHeader from "../components/PageHeader";
import { RiskByProgramChart, RiskDistributionChart } from "../components/RiskCharts";
import { ROLES } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../hooks/useFilters";
import { reportService } from "../services/api";
import { blobErrorToJson, saveBlobResponse } from "../utils/download";
import { getErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber, formatPercent } from "../utils/format";

const FILTER_KEYS = ["period", "program", "semester", "date_from", "date_to"];

function DateFilter({ label, name, filters, setFilter }) {
  return (
    <label className="filter">
      <span className="filter-label">{label}:</span>
      <input type="date" className="filter-select" value={filters[name] || ""} onChange={(e) => setFilter(name, e.target.value)} aria-label={`Fecha ${label.toLowerCase()}`} />
    </label>
  );
}

function Notices({ report }) {
  return (
    <div className="report-notices">
      <p className="text-muted small"><strong>Fuente:</strong> {report.source} Generado: {formatDateTime(report.generated_at)}</p>
      {report.notices.map((notice) => <p key={notice} className="disclaimer"><AlertTriangle size={14} aria-hidden="true" /> {notice}</p>)}
    </div>
  );
}

const LEVEL_COLUMNS = [["ALTO", "Alto"], ["MEDIO", "Medio"], ["BAJO", "Bajo"]];

/** Columnas separadas para cantidad y porcentaje: más legibles y alineadas que "8 (18,2 %)". */
function groupColumns(label, key, format = (value) => value) {
  return [
    { key, header: label, render: (r) => format(r[key]) },
    { key: "total", header: "Estudiantes", align: "right" },
    ...LEVEL_COLUMNS.flatMap(([code, name]) => [
      { key: code, header: name, align: "right" },
      { key: `${code}_pct`, header: `% ${name.toLowerCase()}`, align: "right", className: "text-muted", render: (r) => formatPercent(r[`${code}_pct`]) },
    ]),
  ];
}

function RiskReport({ report }) {
  const levels = Object.fromEntries(report.totals.levels.map((l) => [l.code, l]));
  const total = report.totals.students;
  if (!total) {
    return <Card><Alert type="info">No hay predicciones vigentes para los filtros seleccionados. El reporte no contiene datos.</Alert><Notices report={report} /></Card>;
  }
  const programCount = report.by_program.length;
  return (
    <div className="report-body">
      <div className="stats-grid four report-stats">
        <StatCard label="Estudiantes analizados" value={formatNumber(total)} icon={Users} tone="info"
          caption={`Periodo ${report.filters.period || "—"} · ${programCount} programa(s)`} />
        <StatCard label="Riesgo alto" value={formatNumber(levels.ALTO.count)} detail={formatPercent(levels.ALTO.pct)} tone="high" caption="Atención prioritaria" />
        <StatCard label="Riesgo medio" value={formatNumber(levels.MEDIO.count)} detail={formatPercent(levels.MEDIO.pct)} tone="medium" caption="Bajo monitoreo" />
        <StatCard label="Riesgo bajo" value={formatNumber(levels.BAJO.count)} detail={formatPercent(levels.BAJO.pct)} tone="low" caption="Situación estable" />
      </div>
      <div className="grid-2 report-charts">
        <Card title="Distribución por nivel de riesgo estimado" subtitle="Estudiantes según su predicción vigente">
          <RiskDistributionChart totals={{ high: levels.ALTO.count, medium: levels.MEDIO.count, low: levels.BAJO.count }} />
        </Card>
        <Card title="Distribución por programa académico" subtitle="Estudiantes por nivel en cada programa">
          <RiskByProgramChart rows={report.by_program} />
        </Card>
      </div>
      <Card title="Riesgo por programa académico" padded={false}>
        <DataTable caption="Riesgo por programa" rowKey="program" rows={report.by_program} columns={groupColumns("Programa", "program")} />
      </Card>
      <Card title="Riesgo por semestre" padded={false}>
        <DataTable caption="Riesgo por semestre" rowKey="semester" rows={report.by_semester}
          columns={groupColumns("Semestre", "semester", (value) => `Semestre ${value}`)} emptyTitle="Sin información de semestre." />
      </Card>
      <Card title="Fuente y modelo utilizado" className="report-source">
        <dl className="info-list two-cols">
          {report.models.map((m) => (
            <div key={`${m.model}-${m.version}`}><dt>{m.model} · v{m.version}</dt><dd>{formatNumber(m.predictions)} predicciones</dd></div>
          ))}
        </dl>
        <Notices report={report} />
      </Card>
    </div>
  );
}

/** Reporte de riesgo estudiantil (único tipo de reporte), con exportación PDF y CSV. */
export default function ReportesPage() {
  const { user } = useAuth();
  const isAdmin = user.role === ROLES.ADMIN;
  const { periods, programs, config } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const params = Object.fromEntries(FILTER_KEYS.map((k) => [k, filters[k]]));
  if (!params.period && config?.current_period) params.period = config.current_period;
  const report = useApi(() => reportService.get("risk", params), [JSON.stringify(params)], { errorMessage: "No se pudo generar el reporte." });
  const [downloading, setDownloading] = useState(null);
  const [error, setError] = useState(null);

  const download = async (path, name) => {
    setDownloading(path);
    setError(null);
    try {
      saveBlobResponse(await reportService.download(path, params), name);
    } catch (err) {
      setError(getErrorMessage(await blobErrorToJson(err), "No se pudo descargar el archivo."));
    } finally {
      setDownloading(null);
    }
  };

  return (
    <>
      <PageHeader title="Reporte de riesgo estudiantil" description="Información calculada a partir de los registros del sistema. Los niveles de riesgo son estimaciones."
        actions={
          <>
            <Button variant="secondary" icon={FileText} loading={downloading === "risk/pdf"} onClick={() => download("risk/pdf", "sipd_riesgo.pdf")}>Generar PDF</Button>
            <Button variant="secondary" icon={Sheet} loading={downloading === "risk/csv"} onClick={() => download("risk/csv", "sipd_riesgo.csv")}>Exportar CSV</Button>
            {isAdmin && (
              <Button variant="ghost" icon={FileDown} loading={downloading === "risk/students/csv"} onClick={() => download("risk/students/csv", "sipd_riesgo_individual.csv")}
                title="Listado individual con códigos seudonimizados (sólo Administrador)">CSV individual</Button>
            )}
          </>
        } />

      <FilterBar onClear={clearFilters} hasActive={FILTER_KEYS.some((k) => filters[k])}>
        <Filter label="Periodo" value={params.period} allLabel="Seleccione" onChange={(v) => setFilter("period", v)} options={periods.map((p) => ({ value: p.code, label: p.code }))} />
        <Filter label="Programa" value={filters.program} onChange={(v) => setFilter("program", v)} options={programs.map((p) => ({ value: p.code, label: p.name }))} />
        <Filter label="Semestre" value={filters.semester} onChange={(v) => setFilter("semester", v)} options={Array.from({ length: 12 }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }))} />
        <DateFilter label="Desde" name="date_from" filters={filters} setFilter={setFilter} />
        <DateFilter label="Hasta" name="date_to" filters={filters} setFilter={setFilter} />
      </FilterBar>

      {error && <Alert type="error" onClose={() => setError(null)}>{error}</Alert>}
      {report.error && <ErrorMessage message={report.error} onRetry={report.reload} />}
      {report.loading && !report.data && <Loading message="Generando reporte..." />}
      {report.data && !report.error && (
        <div className={`report-body ${report.loading ? "is-refreshing" : ""}`}>
          {report.data.scope_restricted && <Alert type="info">El reporte incluye sólo los programas asignados a su usuario.</Alert>}
          <RiskReport report={report.data} />
        </div>
      )}
    </>
  );
}
