import { BrainCircuit, CheckCircle2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import ConfirmationModal from "../components/ConfirmationModal";
import DataTable from "../components/DataTable";
import Filter, { FilterBar } from "../components/Filter";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import RiskBadge, { RiskBar } from "../components/RiskBadge";
import Select from "../components/Select";
import StatusBadge from "../components/StatusBadge";
import { ROLES } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../hooks/useFilters";
import { modelService, predictionService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { formatDate, formatDateTime, formatNumber, shortProgram } from "../utils/format";

const PAGE_SIZE = 15;
const METRICS = [["accuracy", "Accuracy"], ["precision", "Precision"], ["recall", "Recall"], ["f1", "F1-score"], ["roc_auc", "ROC-AUC"]];

function ModelsPanel({ isAdmin }) {
  const models = useApi(() => modelService.list(), [], { errorMessage: "Error al cargar los modelos." });
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  const act = async (action, successText) => {
    setBusy(true);
    setMessage(null);
    try {
      await action();
      setMessage({ type: "success", text: successText });
      models.reload();
    } catch (err) {
      setMessage({ type: "error", text: getErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const synthetic = models.data?.some((m) => m.is_synthetic);
  const columns = [
    { key: "name", header: "Modelo", render: (m) => <><strong>{m.name}</strong><br /><small className="text-muted">v{m.version}</small></> },
    ...METRICS.map(([key, label]) => ({
      key, header: label, align: "right",
      render: (m) => (m.metrics?.[key] !== undefined ? m.metrics[key].toFixed(3).replace(".", ",") : "—"),
    })),
    { key: "threshold", header: "Umbral eval.", align: "right", render: (m) => m.metrics?.threshold ?? "—" },
    { key: "data", header: "Datos", render: (m) => (m.is_synthetic ? <StatusBadge className="status-warning" label="Sintéticos" /> : <StatusBadge className="status-info" label="Institucionales" />) },
    {
      key: "active", header: "Estado", align: "right",
      render: (m) => (m.active ? (
        <StatusBadge className="status-success" label="Activo" />
      ) : isAdmin ? (
        <Button variant="link" size="sm" disabled={busy} onClick={() => act(() => modelService.activate(m.id), `${m.name} ahora es el modelo activo.`)}>Activar</Button>
      ) : <span className="text-muted">Inactivo</span>),
    },
  ];

  return (
    <Card
      title="Modelos disponibles y métricas de evaluación"
      subtitle="Métricas calculadas sobre el conjunto de prueba durante el entrenamiento. En deserción se priorizan Recall, F1 y ROC-AUC sobre Accuracy."
      actions={isAdmin && <Button variant="secondary" size="sm" icon={RefreshCw} loading={busy} onClick={() => act(modelService.sync, "Modelos sincronizados.")}>Sincronizar</Button>}
      padded={false}
    >
      {synthetic && (
        <div className="card-inner"><Alert type="warning">Las métricas de modelos entrenados con datos sintéticos sirven sólo para pruebas técnicas; no son resultados académicos reales.</Alert></div>
      )}
      {message && <div className="card-inner"><Alert type={message.type} onClose={() => setMessage(null)}>{message.text}</Alert></div>}
      <DataTable columns={columns} rows={models.data} loading={models.loading} error={models.error} onRetry={models.reload}
        emptyTitle="No hay modelos registrados." emptyDescription="Entrene un modelo con ml/scripts/train.py y sincronice." caption="Modelos" />
    </Card>
  );
}

function BatchRunner({ onDone }) {
  const { periods, programs, config } = useConfig();
  const [period, setPeriod] = useState("");
  const [program, setProgram] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState(null);
  const selectedPeriod = period || config?.current_period || "";

  const run = async () => {
    setRunning(true);
    try {
      const result = await predictionService.runBatch(selectedPeriod, program);
      setMessage({ type: "success", text: result.detail });
      onDone();
    } catch (err) {
      setMessage({ type: "error", text: getErrorMessage(err, "No se pudieron generar las predicciones.") });
    } finally {
      setRunning(false);
      setConfirming(false);
    }
  };

  return (
    <Card title="Ejecutar proceso de predicción" subtitle="Genera nuevas predicciones con el modelo activo. Las anteriores se conservan en el historial.">
      {message && <Alert type={message.type} onClose={() => setMessage(null)}>{message.text}</Alert>}
      <div className="inline-form">
        <Select label="Periodo" value={selectedPeriod} onChange={(e) => setPeriod(e.target.value)} options={periods.map((p) => ({ value: p.code, label: p.code }))} />
        <Select label="Programa" value={program} onChange={(e) => setProgram(e.target.value)} placeholder="Todos los programas"
          options={programs.map((p) => ({ value: p.code, label: p.name }))} />
        <Button icon={BrainCircuit} onClick={() => setConfirming(true)} disabled={!selectedPeriod}>Ejecutar predicciones</Button>
      </div>
      <ConfirmationModal
        open={confirming}
        title="Ejecutar predicciones"
        message={`Se generarán nuevas predicciones para el periodo ${selectedPeriod}${program ? ` (programa ${program})` : ""}. Las predicciones vigentes pasarán al historial como "Reemplazadas". ¿Desea continuar?`}
        confirmLabel="Ejecutar"
        loading={running}
        onConfirm={run}
        onCancel={() => setConfirming(false)}
      />
    </Card>
  );
}

export default function PrediccionesPage() {
  const { user } = useAuth();
  const isAdmin = user.role === ROLES.ADMIN;
  const { config, programs, periods } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const page = Number(filters.page || 1);
  const { data, loading, error, reload } = useApi(
    () => predictionService.list({ ...filters, page, page_size: PAGE_SIZE }),
    [JSON.stringify(filters)],
    { errorMessage: "Error al cargar las predicciones." },
  );

  const columns = [
    { key: "student_code", header: "Estudiante", render: (p) => <Link className="link-strong" to={`/estudiantes/${p.student_code}`}>{p.student_code}</Link> },
    { key: "program", header: "Programa", render: (row) => <span title={row.program}>{shortProgram(row.program)}</span> },
    { key: "academic_period", header: "Periodo" },
    { key: "model_name", header: "Modelo utilizado", render: (p) => <span title={`Versión ${p.model_version_label}`}>{p.model_name}</span> },
    { key: "probability", header: "Probabilidad", render: (p) => <RiskBar probability={p.probability} level={p.risk_level} compact /> },
    { key: "risk_level", header: "Nivel", render: (p) => <RiskBadge level={p.risk_level} /> },
    { key: "prediction_date", header: "Fecha", render: (p) => <span title={formatDateTime(p.prediction_date)}>{formatDate(p.prediction_date)}</span> },
    { key: "status", header: "Estado", render: (p) => <StatusBadge className={p.status === "VIGENTE" ? "status-success" : "status-muted"} label={p.status_display} /> },
  ];

  return (
    <>
      <PageHeader title="Predicciones" badge={data ? `${formatNumber(data.count)} registros` : null}
        description="Probabilidad estimada de deserción por estudiante y periodo." />

      {isAdmin && <BatchRunner onDone={reload} />}

      <FilterBar onClear={clearFilters} hasActive={Object.keys(filters).length > 0}>
        <Filter label="Periodo" value={filters.period} onChange={(v) => setFilter("period", v)} options={periods.map((p) => ({ value: p.code, label: p.code }))} />
        <Filter label="Programa" value={filters.program} onChange={(v) => setFilter("program", v)} options={programs.map((p) => ({ value: p.code, label: p.name }))} />
        <Filter label="Nivel" value={filters.risk_level} onChange={(v) => setFilter("risk_level", v)}
          options={(config?.risk_levels || []).map((l) => ({ value: l.code, label: l.label })).reverse()} />
        <Filter label="Modelo" value={filters.model} onChange={(v) => setFilter("model", v)}
          options={[{ value: "Regresión", label: "Regresión Logística" }, { value: "Random Forest", label: "Random Forest" }, { value: "XGBoost", label: "XGBoost" }]} />
        <Filter label="Estado" value={filters.status} onChange={(v) => setFilter("status", v)} allLabel="Vigentes"
          options={[{ value: "all", label: "Todas (incluye reemplazadas)" }, { value: "REEMPLAZADA", label: "Reemplazadas" }]} />
        <label className="filter">
          <span className="filter-label">Desde:</span>
          <input type="date" className="filter-select" value={filters.date_from || ""} onChange={(e) => setFilter("date_from", e.target.value)} aria-label="Fecha desde" />
        </label>
        <label className="filter">
          <span className="filter-label">Hasta:</span>
          <input type="date" className="filter-select" value={filters.date_to || ""} onChange={(e) => setFilter("date_to", e.target.value)} aria-label="Fecha hasta" />
        </label>
      </FilterBar>

      <Card padded={false}>
        <DataTable columns={columns} rows={data?.results} loading={loading} error={error} onRetry={reload}
          emptyTitle="No hay predicciones para los filtros seleccionados." caption="Predicciones" />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPageChange={(p) => setFilter("page", String(p))} />}
      </Card>

      <ModelsPanel isAdmin={isAdmin} />
      <p className="disclaimer"><CheckCircle2 size={14} aria-hidden="true" /> Umbrales vigentes: Bajo &lt; {config ? config.risk_thresholds.low * 100 : "—"} % · Medio &lt; {config ? config.risk_thresholds.medium * 100 : "—"} % · Alto ≥ {config ? config.risk_thresholds.medium * 100 : "—"} %.</p>
    </>
  );
}
