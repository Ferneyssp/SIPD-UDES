import { Search } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import DataTable from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorMessage from "../components/ErrorMessage";
import Input from "../components/Input";
import Loading from "../components/Loading";
import PageHeader from "../components/PageHeader";
import RiskBadge, { RiskBar } from "../components/RiskBadge";
import FollowUpHistory from "../components/FollowUpHistory";
import { RiskTimelineChart } from "../components/RiskCharts";
import StatusBadge from "../components/StatusBadge";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { predictionService } from "../services/api";
import { formatDateTime } from "../utils/format";

export default function HistorialPage() {
  const { config } = useConfig();
  const [searchParams, setSearchParams] = useSearchParams();
  const student = (searchParams.get("student") || "").toUpperCase();
  const includeSuperseded = searchParams.get("all") === "1";
  const [code, setCode] = useState(student);

  const history = useApi(() => predictionService.history(student, includeSuperseded), [student, includeSuperseded], {
    enabled: Boolean(student),
    errorMessage: "No se pudo consultar el historial del estudiante.",
  });

  const submit = (event) => {
    event.preventDefault();
    const value = code.trim().toUpperCase();
    setSearchParams(value ? { student: value } : {});
  };

  const current = history.data?.timeline.filter((p) => p.status === "VIGENTE") || [];
  const columns = [
    { key: "academic_period", header: "Periodo" },
    { key: "probability", header: "Riesgo estimado", render: (p) => <RiskBar probability={p.probability} level={p.risk_level} compact /> },
    { key: "risk_level", header: "Nivel", render: (p) => <RiskBadge level={p.risk_level} /> },
    { key: "model_name", header: "Modelo", render: (p) => `${p.model_name} v${p.model_version_label}` },
    { key: "prediction_date", header: "Fecha", render: (p) => formatDateTime(p.prediction_date) },
    { key: "status", header: "Estado", render: (p) => <StatusBadge className={p.status === "VIGENTE" ? "status-success" : "status-muted"} label={p.status_display} /> },
  ];

  return (
    <>
      <PageHeader title="Historial" description="Evolución del riesgo estimado y seguimiento de cada estudiante. Las predicciones y las intervenciones nunca se sobrescriben." />

      <Card title="Consultar estudiante">
        <form className="inline-form" onSubmit={submit}>
          <Input label="Código anonimizado" icon={Search} value={code} onChange={(e) => setCode(e.target.value)} placeholder="E001" />
          <Button type="submit">Consultar</Button>
          {student && (
            <label className="checkbox">
              <input type="checkbox" checked={includeSuperseded}
                onChange={(e) => setSearchParams(e.target.checked ? { student, all: "1" } : { student })} />
              <span>Incluir predicciones reemplazadas</span>
            </label>
          )}
        </form>
      </Card>

      {student && (
        <>
          {history.loading && <Loading message="Consultando historial..." />}
          {history.error && <ErrorMessage message={history.error} onRetry={history.reload} />}
          {history.data && (
            <div className="grid-2">
              <Card
                title={<>Evolución del riesgo · <Link className="link-strong" to={`/estudiantes/${history.data.student.anonymous_code}`}>{history.data.student.anonymous_code}</Link></>}
                subtitle={`${history.data.student.program} · Semestre ${history.data.student.semester}`}
              >
                {current.length ? (
                  <>
                    <RiskTimelineChart points={current} thresholds={config?.risk_thresholds} />
                    <ul className="timeline-text">
                      {current.map((p) => (
                        <li key={p.id}><strong>{p.academic_period}</strong> → {p.risk_percentage.toFixed(1).replace(".", ",")} % · {p.risk_level_display}</li>
                      ))}
                    </ul>
                  </>
                ) : <EmptyState title="El estudiante no tiene predicciones registradas." />}
              </Card>
              <Card title="Registro de predicciones" padded={false}>
                <DataTable columns={columns} rows={[...history.data.timeline].reverse()} emptyTitle="Sin predicciones." caption="Historial" />
              </Card>
            </div>
          )}
          {history.data && <FollowUpHistory studentCode={history.data.student.anonymous_code} />}
        </>
      )}

      {!student && (
        <Card>
          <EmptyState title="Consulte un estudiante por su código." description="Verá la evolución de su riesgo estimado y su historial de seguimiento." />
        </Card>
      )}
    </>
  );
}
