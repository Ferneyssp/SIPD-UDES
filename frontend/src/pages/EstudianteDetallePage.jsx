import { ArrowLeft, BellRing, History } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import Card from "../components/Card";
import DataTable from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorMessage from "../components/ErrorMessage";
import FollowUpHistory from "../components/FollowUpHistory";
import Loading from "../components/Loading";
import PageHeader from "../components/PageHeader";
import { manageAlertPath } from "./AlertasPage";
import RiskBadge, { RiskChange, RiskRangesInfo } from "../components/RiskBadge";
import { RiskTimelineChart } from "../components/RiskCharts";
import StatusBadge from "../components/StatusBadge";
import { PREDICTION_DISCLAIMER } from "../config/appConfig";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { alertService, predictionService, studentService } from "../services/api";
import { formatDateTime, formatFeatureValue, formatProbability } from "../utils/format";
import { riskInfo } from "../utils/risk";

function displayFeature(key, value) {
  if (key === "approval_rate" && value !== null && value !== undefined) return `${Math.round(value * 100)} %`;
  if (key === "works_while_studying" && value !== null && value !== undefined) return value ? "Sí" : "No";
  return formatFeatureValue(value);
}

const ALERT_STATUS_CLASS = { ABIERTA: "status-danger", EN_ATENCION: "status-warning", CERRADA: "status-muted" };

/** Factores separados por dirección, como Inspiration / Intervention en Civitas Inspire. */
function FactorGroups({ factors }) {
  const up = factors.filter((f) => f.direction.includes("mayor"));
  const down = factors.filter((f) => f.direction.includes("menor"));
  const neutral = factors.filter((f) => !up.includes(f) && !down.includes(f));
  const group = (title, items, tone, symbol) => items.length > 0 && (
    <div className={`factor-group ${tone}`}>
      <h3>{symbol} {title}</h3>
      <ul className="factor-list">
        {items.map((factor) => (
          <li key={factor.feature}>
            <strong>{factor.label}</strong>
            <span className="text-muted"> · valor: {displayFeature(factor.feature, factor.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <div className="factor-groups">
      {group("Asociadas a mayor riesgo estimado", up, "up", "▲")}
      {group("Asociadas a menor riesgo estimado", down, "down", "▼")}
      {group("Variables con alta relevancia para el modelo", neutral, "neutral", "●")}
    </div>
  );
}

function InfoList({ items }) {
  return (
    <dl className="info-list">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function EstudianteDetallePage() {
  const { code } = useParams();
  const { config } = useConfig();

  const student = useApi(() => studentService.get(code), [code], { errorMessage: "Error al cargar el estudiante." });
  const predictionId = student.data?.current_prediction_id;
  const prediction = useApi(() => predictionService.get(predictionId), [predictionId], { enabled: Boolean(predictionId) });
  const history = useApi(() => predictionService.history(code), [code]);
  const alerts = useApi(() => alertService.list({ student: code, page_size: 10 }), [code]);

  if (student.loading && !student.data) return <Loading message="Cargando estudiante..." />;
  if (student.error) {
    return (
      <>
        <Link to="/estudiantes" className="back-link"><ArrowLeft size={16} /> Volver a estudiantes</Link>
        <ErrorMessage message={student.error} onRetry={student.reload} />
      </>
    );
  }
  const data = student.data;
  if (!data) return null;
  const latest = data.academic_records[0];
  const current = prediction.data;
  const labels = config?.feature_labels || {};

  const recordColumns = [
    { key: "academic_period", header: "Periodo" },
    { key: "semester", header: "Semestre" },
    { key: "gpa", header: "Promedio", render: (r) => formatFeatureValue(r.gpa) },
    { key: "credits", header: "Créditos (matr./aprob./reprob.)", render: (r) => `${r.credits_enrolled} / ${r.credits_approved} / ${r.credits_failed}` },
    { key: "failed_subjects", header: "Asig. perdidas" },
    { key: "attendance_percentage", header: "Asistencia", render: (r) => `${formatFeatureValue(r.attendance_percentage)} %` },
    { key: "academic_status", header: "Estado" },
  ];


  return (
    <>
      <Link to="/estudiantes" className="back-link"><ArrowLeft size={16} /> Volver a estudiantes</Link>
      <PageHeader
        title={`Estudiante ${data.anonymous_code}`}
        badge={data.current_prediction_period ? `Periodo ${data.current_prediction_period}` : null}
        description={`${data.program} · Semestre ${data.semester}`}
        actions={
          <>
            <Link className="btn btn-secondary btn-md" to={`/historial?student=${data.anonymous_code}`}><History size={16} /> <span>Ver historial</span></Link>
          </>
        }
      />

      <div className="grid-3">
        <Card title="Resultado predictivo" className={`prediction-card ${riskInfo(data.current_risk_level).className}-border`}>
          {data.current_probability === null ? (
            <EmptyState title="Sin predicción disponible." description="Aún no se ha estimado el riesgo para este estudiante." />
          ) : (
            <div className="prediction-result">
              <p className="prediction-label">Riesgo estimado de deserción <RiskRangesInfo levels={config?.risk_levels} /></p>
              <p className={`prediction-value ${riskInfo(data.current_risk_level).className}-text`}>{formatProbability(data.current_probability)}</p>
              <p className="prediction-level">Nivel de riesgo: <RiskBadge level={data.current_risk_level} /></p>
              <p className="prediction-change">
                Cambio frente al periodo anterior: <RiskChange points={data.risk_change_points} />
              </p>
              <p className="estimate-note">Probabilidad estimada por el modelo; no es una certeza.</p>
              <InfoList items={[
                ["Modelo utilizado", current ? `${current.model_name} (v${current.model_version_label})` : "—"],
                ["Periodo", data.current_prediction_period],
                ["Fecha de predicción", formatDateTime(data.current_prediction_date)],
              ]} />
            </div>
          )}
        </Card>
        <Card title="Información general">
          <InfoList items={[
            ["Identificador anonimizado", data.anonymous_code],
            ["Programa", data.program],
            ["Semestre", data.semester],
            ["Periodo", data.current_period],
            ["Estado académico", data.academic_status],
            ["Seguimiento", <StatusBadge key="s" status={data.latest_followup_status || "SIN_SEGUIMIENTO"} label={data.latest_followup_status_display} />],
          ]} />
        </Card>
        <Card title="Información académica" subtitle={latest ? `Periodo ${latest.academic_period}` : null}>
          {latest ? (
            <InfoList items={[
              ["Promedio", formatFeatureValue(latest.gpa)],
              ["Créditos matriculados", latest.credits_enrolled],
              ["Créditos aprobados", latest.credits_approved],
              ["Créditos reprobados", latest.credits_failed],
              ["Asignaturas perdidas", latest.failed_subjects],
              ["Asistencia", `${formatFeatureValue(latest.attendance_percentage)} %`],
            ]} />
          ) : <EmptyState title="Sin información académica registrada." />}
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Factores principales" subtitle="Variables que más influyeron en la estimación del modelo. Indican asociación, no causalidad.">
          {current ? <FactorGroups factors={current.explanation} /> : <EmptyState title="Sin predicción disponible." />}
        </Card>
        <Card title="Evolución del riesgo estimado">
          {history.error && <ErrorMessage message={history.error} onRetry={history.reload} compact />}
          {history.data?.timeline?.length ? (
            <RiskTimelineChart points={history.data.timeline} thresholds={config?.risk_thresholds} />
          ) : (!history.loading && <EmptyState title="No hay predicciones anteriores." />)}
        </Card>
      </div>

      {current && (
        <Card title="Variables utilizadas para la predicción" subtitle="Datos de entrada procesados por el modelo (los valores faltantes se imputan durante el preprocesamiento)">
          <dl className="info-list three-cols">
            {Object.entries(current.input_features).map(([key, value]) => (
              <div key={key}>
                <dt>{labels[key] || key}</dt>
                <dd>{displayFeature(key, value)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <Card title="Alertas tempranas" padded={false}
        subtitle="Se generan automáticamente con nivel Alto o con un aumento del riesgo estimado respecto al periodo anterior.">
        <DataTable caption="Alertas del estudiante" rows={alerts.data?.results} loading={alerts.loading} error={alerts.error}
          onRetry={alerts.reload} emptyTitle="El estudiante no tiene alertas." columns={[
            { key: "academic_period", header: "Periodo" },
            { key: "reason_display", header: "Motivo", className: "cell-wrap" },
            { key: "status", header: "Estado", render: (a) => <StatusBadge className={ALERT_STATUS_CLASS[a.status]} label={a.status_display} /> },
            { key: "assigned_to_name", header: "Responsable", render: (a) => a.assigned_to_name || "Sin asignar" },
            { key: "open", header: "", align: "right", render: (a) => <Link className="link-action" to={manageAlertPath(a.student_code)}><BellRing size={14} aria-hidden="true" /> Gestionar seguimiento</Link> },
          ]} />
      </Card>

      <Card title="Historial académico disponible" padded={false}
        subtitle="Sólo lectura: la información se actualiza mediante la carga de datos institucional.">
        <DataTable columns={recordColumns} rows={data.academic_records} emptyTitle="Sin registros académicos." caption="Historial académico" />
      </Card>

      <FollowUpHistory studentCode={data.anonymous_code} onSaved={() => { student.reload(); alerts.reload(); }} />
      <p className="disclaimer">{PREDICTION_DISCLAIMER}</p>

    </>
  );
}
