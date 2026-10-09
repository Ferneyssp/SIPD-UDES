import { ArrowLeft, BrainCircuit, History, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import DataTable from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorMessage from "../components/ErrorMessage";
import FollowUpFormModal from "../components/FollowUpFormModal";
import Loading from "../components/Loading";
import PageHeader from "../components/PageHeader";
import RiskBadge from "../components/RiskBadge";
import { RiskTimelineChart } from "../components/RiskCharts";
import StatusBadge from "../components/StatusBadge";
import StudentFormModal from "../components/StudentFormModal";
import { PREDICTION_DISCLAIMER, ROLES } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { followupService, predictionService, studentService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { formatDate, formatDateTime, formatFeatureValue, formatProbability } from "../utils/format";
import { riskInfo } from "../utils/risk";

function displayFeature(key, value) {
  if (key === "approval_rate" && value !== null && value !== undefined) return `${Math.round(value * 100)} %`;
  if (key === "works_while_studying" && value !== null && value !== undefined) return value ? "Sí" : "No";
  return formatFeatureValue(value);
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
  const { user } = useAuth();
  const { config } = useConfig();
  const isAdmin = user.role === ROLES.ADMIN;
  const [followupModal, setFollowupModal] = useState({ open: false, followup: null });
  const [editOpen, setEditOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState(null);

  const student = useApi(() => studentService.get(code), [code], { errorMessage: "Error al cargar el estudiante." });
  const predictionId = student.data?.current_prediction_id;
  const prediction = useApi(() => predictionService.get(predictionId), [predictionId], { enabled: Boolean(predictionId) });
  const history = useApi(() => predictionService.history(code), [code]);
  const followups = useApi(() => followupService.list({ student_exact: code, page_size: 50 }), [code]);

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

  const runPrediction = async () => {
    setRunning(true);
    setNotice(null);
    try {
      const result = await predictionService.run(code);
      setNotice({ type: "success", text: `Predicción generada: riesgo estimado ${result.risk_percentage} % (${result.risk_level}).` });
      await Promise.all([student.reload(), history.reload()]);
    } catch (err) {
      setNotice({ type: "error", text: getErrorMessage(err, "No se pudo ejecutar la predicción.") });
    } finally {
      setRunning(false);
    }
  };

  const recordColumns = [
    { key: "academic_period", header: "Periodo" },
    { key: "semester", header: "Semestre" },
    { key: "gpa", header: "Promedio", render: (r) => formatFeatureValue(r.gpa) },
    { key: "credits", header: "Créditos (matr./aprob./reprob.)", render: (r) => `${r.credits_enrolled} / ${r.credits_approved} / ${r.credits_failed}` },
    { key: "failed_subjects", header: "Asig. perdidas" },
    { key: "attendance_percentage", header: "Asistencia", render: (r) => `${formatFeatureValue(r.attendance_percentage)} %` },
    { key: "academic_status", header: "Estado" },
  ];

  const followupColumns = [
    { key: "follow_up_date", header: "Fecha", render: (f) => formatDate(f.follow_up_date) },
    { key: "intervention_type_display", header: "Tipo" },
    { key: "observation", header: "Observación", className: "cell-wrap" },
    { key: "user_name", header: "Responsable" },
    { key: "status", header: "Estado", render: (f) => <StatusBadge status={f.status} label={f.status_display} /> },
    { key: "edit", header: "", align: "right", render: (f) => (
      <Button variant="link" size="sm" icon={Pencil} onClick={() => setFollowupModal({ open: true, followup: f })}>Editar</Button>
    ) },
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
            {isAdmin && <Button variant="secondary" icon={Pencil} onClick={() => setEditOpen(true)}>Editar</Button>}
            {isAdmin && <Button icon={BrainCircuit} loading={running} onClick={runPrediction}>Ejecutar predicción</Button>}
          </>
        }
      />
      {notice && <Alert type={notice.type} onClose={() => setNotice(null)}>{notice.text}</Alert>}

      <div className="grid-3">
        <Card title="Resultado predictivo" className={`prediction-card ${riskInfo(data.current_risk_level).className}-border`}>
          {data.current_probability === null ? (
            <EmptyState title="Sin predicción disponible." description="Aún no se ha estimado el riesgo para este estudiante." />
          ) : (
            <div className="prediction-result">
              <p className="prediction-label">Riesgo estimado de deserción</p>
              <p className={`prediction-value ${riskInfo(data.current_risk_level).className}-text`}>{formatProbability(data.current_probability)}</p>
              <p className="prediction-level">Nivel de riesgo: <RiskBadge level={data.current_risk_level} /></p>
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
        <Card title="Variables asociadas al resultado" subtitle="Variables que más influyeron en la estimación del modelo. Indican asociación, no causalidad.">
          {current ? (
            <ul className="factor-list">
              {current.explanation.map((factor) => (
                <li key={factor.feature}>
                  <div>
                    <strong>{factor.label}</strong>
                    <span className="text-muted"> · valor: {displayFeature(factor.feature, factor.value)}</span>
                  </div>
                  <span className={`factor-direction ${factor.direction.includes("mayor") ? "up" : factor.direction.includes("menor") ? "down" : "neutral"}`}>
                    {factor.direction.includes("mayor") ? "▲ " : factor.direction.includes("menor") ? "▼ " : "● "}{factor.direction}
                  </span>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="Sin predicción disponible." />}
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

      <Card title="Historial académico disponible" padded={false}>
        <DataTable columns={recordColumns} rows={data.academic_records} emptyTitle="Sin registros académicos." caption="Historial académico" />
      </Card>

      <Card
        title="Seguimiento"
        subtitle="Intervenciones registradas por profesores y coordinadores"
        actions={<Button icon={Plus} onClick={() => setFollowupModal({ open: true, followup: null })}>Registrar seguimiento</Button>}
        padded={false}
      >
        <DataTable
          columns={followupColumns}
          rows={followups.data?.results}
          loading={followups.loading}
          error={followups.error}
          onRetry={followups.reload}
          emptyTitle="Aún no hay seguimientos registrados."
          caption="Seguimientos del estudiante"
        />
      </Card>
      <p className="disclaimer">{PREDICTION_DISCLAIMER}</p>

      <FollowUpFormModal
        open={followupModal.open}
        followup={followupModal.followup}
        studentCode={data.anonymous_code}
        onClose={() => setFollowupModal({ open: false, followup: null })}
        onSaved={() => {
          setFollowupModal({ open: false, followup: null });
          followups.reload();
          student.reload();
        }}
      />
      <StudentFormModal
        open={editOpen}
        student={data}
        onClose={() => setEditOpen(false)}
        onSaved={() => { setEditOpen(false); student.reload(); }}
      />
    </>
  );
}
