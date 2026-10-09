import { AlertTriangle, BrainCircuit, CheckCircle2, ChevronRight, MinusCircle, Users } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import Alert from "../components/Alert";
import Card, { StatCard } from "../components/Card";
import DataTable from "../components/DataTable";
import ErrorMessage from "../components/ErrorMessage";
import Filter, { FilterBar } from "../components/Filter";
import Loading from "../components/Loading";
import PageHeader from "../components/PageHeader";
import RiskBadge, { RiskBar } from "../components/RiskBadge";
import { RiskByProgramChart, RiskDistributionChart } from "../components/RiskCharts";
import StatusBadge from "../components/StatusBadge";
import { PREDICTION_DISCLAIMER } from "../config/appConfig";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../hooks/useFilters";
import { predictionService } from "../services/api";
import { formatDate, formatNumber, formatPercent, shortProgram } from "../utils/format";

const SEMESTERS = Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: `Semestre ${i + 1}` }));

export default function InicioPage() {
  const navigate = useNavigate();
  const { config, programs, periods } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const { data, loading, error, reload } = useApi(
    () => predictionService.summary(filters),
    [JSON.stringify(filters)],
    { errorMessage: "Error al cargar la información de Inicio." },
  );

  const levelOptions = (config?.risk_levels || []).map((level) => ({ value: level.code, label: level.label })).reverse();
  const attentionLevel = levelOptions.find((option) => option.value === filters.risk_level)?.label || "Alto";

  const columns = [
    { key: "anonymous_code", header: "Identificador", render: (row) => <Link className="link-strong" to={`/estudiantes/${row.anonymous_code}`}>{row.anonymous_code}</Link> },
    { key: "program", header: "Programa", render: (row) => <span title={row.program}>{shortProgram(row.program)}</span> },
    { key: "semester", header: "Semestre", align: "center" },
    { key: "risk", header: "Riesgo estimado", render: (row) => <RiskBar probability={row.current_probability} level={row.current_risk_level} /> },
    { key: "level", header: "Nivel", render: (row) => <RiskBadge level={row.current_risk_level} /> },
    { key: "date", header: "Fecha de predicción", render: (row) => formatDate(row.current_prediction_date) },
    { key: "followup", header: "Seguimiento", render: (row) => <StatusBadge status={row.latest_followup_status || "SIN_SEGUIMIENTO"} label={row.latest_followup_status_display} /> },
    {
      key: "action", header: "Acción", align: "right",
      render: (row) => <Link to={`/estudiantes/${row.anonymous_code}`} className="link-action">Ver <ChevronRight size={16} aria-hidden="true" /></Link>,
    },
  ];

  const totals = data?.totals;
  return (
    <>
      <PageHeader
        title="Inicio"
        badge={data?.period ? `Periodo ${data.period}` : null}
        description="Resumen del riesgo estimado de deserción de los estudiantes a su cargo."
      />

      <FilterBar onClear={clearFilters} hasActive={Object.keys(filters).length > 0}>
        <Filter label="Programa" value={filters.program} onChange={(v) => setFilter("program", v)}
          options={programs.map((p) => ({ value: p.code, label: p.name }))} />
        <Filter label="Periodo" value={filters.period} onChange={(v) => setFilter("period", v)} allLabel="Actual"
          options={periods.map((p) => ({ value: p.code, label: p.code }))} />
        <Filter label="Nivel de riesgo" value={filters.risk_level} onChange={(v) => setFilter("risk_level", v)} allLabel="Alto (por defecto)"
          options={levelOptions} />
        <Filter label="Semestre" value={filters.semester} onChange={(v) => setFilter("semester", v)} options={SEMESTERS} />
        <Filter label="Seguimiento" value={filters.followup_status} onChange={(v) => setFilter("followup_status", v)}
          options={(config?.followup_statuses || []).map((s) => ({ value: s.value, label: s.label }))} />
      </FilterBar>

      {error && <ErrorMessage message={error} onRetry={reload} />}
      {loading && !data && <Loading message="Cargando resumen..." />}

      {totals && (
        <>
          {data.model && !data.model.available && (
            <Alert type="warning" title="Modelo no disponible.">
              No hay un modelo entrenado activo; las predicciones no pueden actualizarse.
            </Alert>
          )}
          {data.model?.is_synthetic && (
            <Alert type="info" title="Entorno de demostración.">
              El modelo activo ({data.model.name}) fue entrenado con datos sintéticos; los resultados no representan estudiantes reales.
            </Alert>
          )}

          <div className="stats-grid">
            <StatCard label="Total de estudiantes" value={formatNumber(totals.students)} icon={Users} tone="info"
              caption={data.scope_restricted ? "En sus programas asignados" : "Estudiantes activos registrados"} />
            <StatCard label="Riesgo alto" value={formatNumber(totals.high)} detail={`(${formatPercent(totals.high_pct)})`}
              icon={AlertTriangle} tone="high" caption="Atención prioritaria" />
            <StatCard label="Riesgo medio" value={formatNumber(totals.medium)} detail={`(${formatPercent(totals.medium_pct)})`}
              icon={MinusCircle} tone="medium" caption="Bajo monitoreo" />
            <StatCard label="Riesgo bajo" value={formatNumber(totals.low)} detail={`(${formatPercent(totals.low_pct)})`}
              icon={CheckCircle2} tone="low" caption="Situación estable" />
            <StatCard label="Predicciones realizadas" value={formatNumber(totals.predictions)} icon={BrainCircuit} tone="neutral"
              caption={`Vigentes en ${data.period || "el periodo"}${totals.without_prediction ? ` · ${totals.without_prediction} sin predicción` : ""}`} />
          </div>

          {totals.students > 0 && (
            <div className="grid-2">
              <Card title="Distribución por nivel de riesgo" subtitle="Estudiantes según su riesgo estimado vigente">
                <RiskDistributionChart totals={totals} />
              </Card>
              <Card title="Riesgo por programa" subtitle="Número de estudiantes por nivel en cada programa">
                <RiskByProgramChart rows={data.by_program} />
              </Card>
            </div>
          )}

          <Card
            title={<>Estudiantes que requieren atención <span className={`badge ${filters.risk_level === "BAJO" ? "risk-low" : filters.risk_level === "MEDIO" ? "risk-medium" : "risk-high"}`}>Riesgo {attentionLevel}</span></>}
            subtitle={`${data.attention_total} estudiante(s) identificados para seguimiento. Se muestran los de mayor riesgo estimado.`}
            actions={<Link className="link-action" to={`/estudiantes?risk_level=${filters.risk_level || "ALTO"}&ordering=-current_probability`}>Ver todos <ChevronRight size={16} /></Link>}
            padded={false}
          >
            <DataTable
              columns={columns}
              rows={data.attention}
              loading={loading}
              emptyTitle="No hay estudiantes en este nivel de riesgo."
              emptyDescription="Ajuste los filtros para consultar otros grupos."
              onRowClick={(row) => navigate(`/estudiantes/${row.anonymous_code}`)}
              caption="Estudiantes que requieren atención"
            />
          </Card>
          <p className="disclaimer">{PREDICTION_DISCLAIMER}</p>
        </>
      )}
    </>
  );
}
