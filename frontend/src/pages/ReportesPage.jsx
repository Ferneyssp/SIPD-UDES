import { AlertTriangle, BarChart3, FileDown, FileText, ShieldCheck, Sheet, Users } from "lucide-react";
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
import StatusBadge from "../components/StatusBadge";
import { APPROVAL_CLASS, METRICS, RUN_STATUS_CLASS, formatMetric } from "../components/TrainingRunDetail";
import { ROLES } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../hooks/useFilters";
import { reportService } from "../services/api";
import { blobErrorToJson, saveBlobResponse } from "../utils/download";
import { getErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber, formatPercent } from "../utils/format";

const TABS = [
  { value: "riesgo", label: "Riesgo estudiantil", kind: "risk" },
  { value: "modelos", label: "Evaluación de modelos", kind: "models" },
  { value: "actividad", label: "Actividad administrativa", kind: "activity", adminOnly: true },
];
const FILTER_KEYS = { risk: ["period", "program", "semester", "date_from", "date_to"], models: ["algorithm"], activity: ["date_from", "date_to"] };

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

function groupColumns(label, key) {
  return [
    { key, header: label },
    { key: "total", header: "Estudiantes", align: "right" },
    { key: "ALTO", header: "Alto", align: "right", render: (r) => `${r.ALTO} (${formatPercent(r.ALTO_pct)})` },
    { key: "MEDIO", header: "Medio", align: "right", render: (r) => `${r.MEDIO} (${formatPercent(r.MEDIO_pct)})` },
    { key: "BAJO", header: "Bajo", align: "right", render: (r) => `${r.BAJO} (${formatPercent(r.BAJO_pct)})` },
  ];
}

function RiskReport({ report }) {
  const levels = Object.fromEntries(report.totals.levels.map((l) => [l.code, l]));
  const total = report.totals.students;
  if (!total) {
    return <Card><Alert type="info">No hay predicciones vigentes para los filtros seleccionados. El reporte no contiene datos.</Alert><Notices report={report} /></Card>;
  }
  return (
    <>
      <div className="stats-grid four">
        <StatCard label="Estudiantes analizados" value={formatNumber(total)} icon={Users} tone="info" caption={`Periodo ${report.filters.period || "—"}`} />
        <StatCard label="Riesgo alto" value={formatNumber(levels.ALTO.count)} detail={formatPercent(levels.ALTO.pct)} tone="high" />
        <StatCard label="Riesgo medio" value={formatNumber(levels.MEDIO.count)} detail={formatPercent(levels.MEDIO.pct)} tone="medium" />
        <StatCard label="Riesgo bajo" value={formatNumber(levels.BAJO.count)} detail={formatPercent(levels.BAJO.pct)} tone="low" />
      </div>
      <div className="grid-2">
        <Card title="Distribución por nivel de riesgo estimado">
          <RiskDistributionChart totals={{ high: levels.ALTO.count, medium: levels.MEDIO.count, low: levels.BAJO.count }} />
        </Card>
        <Card title="Distribución por programa académico">
          <RiskByProgramChart rows={report.by_program} />
        </Card>
      </div>
      <div className="grid-2">
        <Card title="Por programa" padded={false}>
          <DataTable caption="Riesgo por programa" rowKey="program" rows={report.by_program} columns={groupColumns("Programa", "program")} />
        </Card>
        <Card title="Por semestre" padded={false}>
          <DataTable caption="Riesgo por semestre" rowKey="semester" rows={report.by_semester} columns={groupColumns("Semestre", "semester")}
            emptyTitle="Sin información de semestre." />
        </Card>
      </div>
      <Card title="Versión del modelo utilizado" padded={false}>
        <DataTable caption="Modelos utilizados" rowKey={(m) => `${m.model}-${m.version}`} rows={report.models}
          columns={[
            { key: "model", header: "Modelo" }, { key: "version", header: "Versión" },
            { key: "predictions", header: "Predicciones", align: "right" },
            { key: "is_synthetic", header: "Datos de entrenamiento", render: (m) => (m.is_synthetic ? <StatusBadge className="status-warning" label="Sintéticos" /> : "No marcados como sintéticos") },
          ]} />
        <div className="card-inner"><Notices report={report} /></div>
      </Card>
    </>
  );
}

function ModelReport({ report }) {
  if (!report.versions.length) return <Card><Alert type="info">No hay versiones de modelo registradas.</Alert></Card>;
  return (
    <Card title="Rendimiento de las versiones entrenadas" padded={false}
      subtitle="Métricas del conjunto de prueba de cada entrenamiento. Compare sólo versiones del mismo grupo de evaluación.">
      <DataTable caption="Evaluación de modelos" rows={report.versions}
        columns={[
          { key: "name", header: "Modelo", render: (v) => <><strong>{v.name}</strong><br /><small className="text-muted">v{v.version}</small></> },
          { key: "trained_at", header: "Entrenado", render: (v) => formatDateTime(v.trained_at) },
          { key: "sizes", header: "Registros (entren. / prueba)", render: (v) => `${formatNumber(v.dataset_rows)} (${v.train_size ?? "—"} / ${v.test_size ?? "—"})` },
          ...METRICS.map(([key, label]) => ({ key, header: label, align: "right", render: (v) => formatMetric(v.metrics[key]) })),
          { key: "cm", header: "VN/FP/FN/VP", render: (v) => (v.confusion_matrix ? ["tn", "fp", "fn", "tp"].map((k) => v.confusion_matrix[k]).join(" / ") : "No calculado") },
          { key: "group", header: "Grupo eval.", render: (v) => v.comparison_group || "—" },
          { key: "approval", header: "Aprobación", render: (v) => <StatusBadge className={APPROVAL_CLASS[v.approval_status]} label={v.approval_status_display} /> },
          { key: "active", header: "Activo", render: (v) => (v.active ? <StatusBadge className="status-success" label="Activo" /> : "—") },
        ]} />
      <div className="card-inner"><Notices report={report} /></div>
    </Card>
  );
}

function ActivityReport({ report }) {
  const { training } = report;
  return (
    <>
      <div className="stats-grid four">
        <StatCard label="Reentrenamientos" value={formatNumber(training.total)} icon={BarChart3} tone="info" />
        <StatCard label="Completados" value={formatNumber(training.completed)} tone="low" />
        <StatCard label="Fallidos" value={formatNumber(training.failed)} tone="high" />
        <StatCard label="Cambios de modelo activo" value={formatNumber(report.activations.length)} icon={ShieldCheck} tone="neutral" />
      </div>
      <div className="grid-2">
        <Card title="Acciones registradas" padded={false}>
          <DataTable caption="Acciones de auditoría" rowKey="action" rows={report.audit_counts}
            columns={[{ key: "label", header: "Acción" }, { key: "count", header: "Cantidad", align: "right" }]} />
        </Card>
        <Card title="Activaciones y recuperaciones" padded={false}>
          <DataTable caption="Activaciones" rowKey={(a) => a.created_at + a.new} rows={report.activations} emptyTitle="Sin cambios registrados."
            columns={[
              { key: "created_at", header: "Fecha", render: (a) => formatDateTime(a.created_at) },
              { key: "action_display", header: "Acción" }, { key: "new", header: "Nueva versión" },
              { key: "performed_by", header: "Usuario" },
            ]} />
        </Card>
      </div>
      <Card title="Historial de reentrenamientos" padded={false}>
        <DataTable caption="Reentrenamientos" rows={training.runs} emptyTitle="No hay reentrenamientos en el periodo."
          columns={[
            { key: "id", header: "#" },
            { key: "created_at", header: "Inicio", render: (r) => formatDateTime(r.created_at) },
            { key: "finished_at", header: "Fin", render: (r) => formatDateTime(r.finished_at) },
            { key: "requested_by", header: "Responsable" },
            { key: "dataset", header: "Datos", render: (r) => `${r.dataset} (${formatNumber(r.rows)})` },
            { key: "status", header: "Estado", render: (r) => <StatusBadge className={RUN_STATUS_CLASS[r.status]} label={r.status_display} /> },
            { key: "error", header: "Error", className: "cell-wrap", render: (r) => r.error || "—" },
          ]} />
        <div className="card-inner"><Notices report={report} /></div>
      </Card>
    </>
  );
}

export default function ReportesPage() {
  const { user } = useAuth();
  const isAdmin = user.role === ROLES.ADMIN;
  const { periods, programs, config } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const tabs = TABS.filter((t) => !t.adminOnly || isAdmin);
  const tab = tabs.find((t) => t.value === filters.tipo) || tabs[0];
  const params = Object.fromEntries(FILTER_KEYS[tab.kind].map((k) => [k, filters[k]]));
  if (tab.kind === "risk" && !params.period && config?.current_period) params.period = config.current_period;
  const report = useApi(() => reportService.get(tab.kind, params), [tab.kind, JSON.stringify(params)], { errorMessage: "No se pudo generar el reporte." });
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

  const selectTab = (value) => {
    clearFilters();
    if (value !== tabs[0].value) setFilter("tipo", value);
  };

  return (
    <>
      <PageHeader title="Reportes" description="Información calculada a partir de los registros del sistema. Los niveles de riesgo son estimaciones."
        actions={
          <>
            <Button variant="secondary" icon={FileText} loading={downloading === `${tab.kind}/pdf`} onClick={() => download(`${tab.kind}/pdf`, `sipd_${tab.kind}.pdf`)}>Generar PDF</Button>
            <Button variant="secondary" icon={Sheet} loading={downloading === `${tab.kind}/csv`} onClick={() => download(`${tab.kind}/csv`, `sipd_${tab.kind}.csv`)}>Exportar CSV</Button>
            {tab.kind === "risk" && isAdmin && (
              <Button variant="ghost" icon={FileDown} loading={downloading === "risk/students/csv"} onClick={() => download("risk/students/csv", "sipd_riesgo_individual.csv")}
                title="Listado individual con códigos seudonimizados (sólo Administrador)">CSV individual</Button>
            )}
          </>
        } />

      <div className="tabs" role="tablist" aria-label="Tipo de reporte">
        {tabs.map((t) => (
          <button key={t.value} type="button" role="tab" aria-selected={t.value === tab.value} className={`tab ${t.value === tab.value ? "active" : ""}`}
            onClick={() => selectTab(t.value)}>{t.label}</button>
        ))}
      </div>

      <FilterBar onClear={() => selectTab(tab.value)} hasActive={FILTER_KEYS[tab.kind].some((k) => filters[k])}>
        {tab.kind === "risk" && (
          <>
            <Filter label="Periodo" value={params.period} allLabel="Seleccione" onChange={(v) => setFilter("period", v)} options={periods.map((p) => ({ value: p.code, label: p.code }))} />
            <Filter label="Programa" value={filters.program} onChange={(v) => setFilter("program", v)} options={programs.map((p) => ({ value: p.code, label: p.name }))} />
            <Filter label="Semestre" value={filters.semester} onChange={(v) => setFilter("semester", v)} options={Array.from({ length: 12 }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }))} />
          </>
        )}
        {tab.kind === "models" && (
          <Filter label="Algoritmo" value={filters.algorithm} onChange={(v) => setFilter("algorithm", v)}
            options={[{ value: "logistic_regression", label: "Regresión Logística" }, { value: "random_forest", label: "Random Forest" }, { value: "xgboost", label: "XGBoost" }]} />
        )}
        {tab.kind !== "models" && (
          <>
            <DateFilter label="Desde" name="date_from" filters={filters} setFilter={setFilter} />
            <DateFilter label="Hasta" name="date_to" filters={filters} setFilter={setFilter} />
          </>
        )}
      </FilterBar>

      {error && <Alert type="error" onClose={() => setError(null)}>{error}</Alert>}
      {report.error && <ErrorMessage message={report.error} onRetry={report.reload} />}
      {report.loading && !report.data && <Loading message="Generando reporte..." />}
      {report.data && !report.error && (
        <div className={report.loading ? "is-refreshing" : ""}>
          {report.data.scope_restricted && <Alert type="info">El reporte incluye sólo los programas asignados a su usuario.</Alert>}
          {tab.kind === "risk" && report.data.totals && <RiskReport report={report.data} />}
          {tab.kind === "models" && report.data.versions && <ModelReport report={report.data} />}
          {tab.kind === "activity" && report.data.training && <ActivityReport report={report.data} />}
        </div>
      )}
    </>
  );
}
