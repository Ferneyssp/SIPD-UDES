import { BrainCog, CheckCircle2, Database, FileSpreadsheet, RotateCcw, UploadCloud } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import ConfirmationModal from "../components/ConfirmationModal";
import DataTable from "../components/DataTable";
import ErrorMessage from "../components/ErrorMessage";
import Filter, { FilterBar } from "../components/Filter";
import Loading from "../components/Loading";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import Select from "../components/Select";
import StatusBadge from "../components/StatusBadge";
import TrainingRunDetail, { APPROVAL_CLASS, METRICS, RUN_STATUS_CLASS, formatMetric } from "../components/TrainingRunDetail";
import { useApi } from "../hooks/useApi";
import { trainingService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber } from "../utils/format";

const HISTORY_PAGE_SIZE = 10;
const RUN_STATUSES = ["PENDIENTE", "VALIDANDO", "PREPARANDO", "ENTRENANDO", "EVALUANDO", "REGISTRANDO", "COMPLETADO", "FALLIDO", "CANCELADO"];

function versionState(version) {
  if (version.active) return <StatusBadge className="status-success" label="Activo" />;
  if (version.approval_status === "APROBADO") return <StatusBadge className="status-info" label="Aprobado (disponible)" />;
  if (version.approval_status === "PENDIENTE") return <StatusBadge className="status-warning" label="Evaluado · pendiente" />;
  if (version.approval_status === "RECHAZADO") return <StatusBadge className="status-danger" label="Rechazado" />;
  return <StatusBadge className="status-neutral" label="Disponible" />;
}

function ModelsStatus({ overview }) {
  const columns = [
    { key: "name", header: "Modelo", render: (m) => <><strong>{m.name}</strong><br /><small className="text-muted">v{m.version}</small></> },
    { key: "trained_at", header: "Entrenado", render: (m) => formatDateTime(m.trained_at) },
    ...METRICS.map(([key, label]) => ({ key, header: label, align: "right", render: (m) => formatMetric(m.metrics?.[key]) })),
    { key: "origin", header: "Origen", render: (m) => (m.training_run ? `Web (#${m.training_run})` : "Offline") },
    { key: "data", header: "Datos", render: (m) => (m.is_synthetic ? <StatusBadge className="status-warning" label="Sintéticos" /> : <span className="text-muted">No marcados</span>) },
    { key: "state", header: "Estado", render: versionState },
  ];
  const active = overview.active_model;
  const last = overview.last_run;
  return (
    <Card title="Estado de los modelos" padded={false}
      subtitle="Métricas sobre el conjunto de prueba de cada entrenamiento. Activo = modelo que usan las nuevas predicciones.">
      <div className="card-inner stats-grid three">
        <div className="mini-stat"><span>Modelo activo</span><strong className="stat-text">{active ? `${active.name}` : "Ninguno"}</strong>
          <small className="text-muted">{active ? `v${active.version} · ${formatDateTime(active.trained_at)}` : "No hay modelo disponible"}</small></div>
        <div className="mini-stat"><span>Algoritmos del procedimiento</span><strong className="stat-text">{overview.config.algorithms.map((a) => a.label).join(", ")}</strong></div>
        <div className="mini-stat"><span>Último entrenamiento</span>
          <strong className="stat-text">{last ? <StatusBadge className={RUN_STATUS_CLASS[last.status]} label={last.status_display} /> : "Sin registros"}</strong>
          <small className="text-muted">{last ? `#${last.id} · ${formatDateTime(last.finished_at || last.created_at)}` : "Aún no se ha reentrenado desde la web"}</small></div>
      </div>
      <DataTable columns={columns} rows={overview.versions} caption="Versiones de modelos" emptyTitle="No hay modelos registrados." />
    </Card>
  );
}

function ValidationReport({ dataset }) {
  const { report } = dataset;
  const valid = dataset.status === "VALIDO";
  return (
    <div className="validation-report">
      <Alert type={valid ? "success" : "error"} title={valid ? "Dataset válido." : "Dataset rechazado."}>
        {valid ? "Cumple los requisitos del procedimiento de entrenamiento." : "Corrija los problemas indicados y vuelva a cargarlo. No se entrenará con este archivo."}
      </Alert>
      {report.rows > 0 && (
        <div className="stats-grid three">
          <div className="mini-stat"><span>Registros detectados</span><strong>{formatNumber(report.rows)}</strong></div>
          <div className="mini-stat"><span>Casos de deserción (1)</span><strong>{formatNumber(report.summary?.class_counts?.["1"])}</strong></div>
          <div className="mini-stat"><span>Casos sin deserción (0)</span><strong>{formatNumber(report.summary?.class_counts?.["0"])}</strong></div>
        </div>
      )}
      {dataset.is_synthetic && <Alert type="warning">El dataset está marcado como SINTÉTICO: las métricas sólo servirán como prueba técnica.</Alert>}
      {report.errors.length > 0 && (
        <DataTable caption="Errores de validación" rowKey={(e) => `${e.code}-${e.column}-${e.message}`} rows={report.errors}
          columns={[
            { key: "column", header: "Columna" },
            { key: "message", header: "Problema", className: "cell-wrap" },
            { key: "count", header: "Filas afectadas", align: "right", render: (e) => e.count || "—" },
            { key: "rows", header: "Ejemplos (fila del archivo)", render: (e) => (e.rows?.length ? e.rows.join(", ") : "—") },
          ]} />
      )}
      {report.warnings.length > 0 && (
        <details className="run-details" open={valid}>
          <summary>Advertencias ({report.warnings.length})</summary>
          <ul className="rules">{report.warnings.map((w) => <li key={`${w.code}-${w.column}`}><code>{w.column}</code> {w.message}</li>)}</ul>
        </details>
      )}
    </div>
  );
}

function NewTraining({ config, onStarted, blocked }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState(null);
  const [algorithms, setAlgorithms] = useState(config.algorithms.map((a) => a.value));
  const [metric, setMetric] = useState(config.default_selection_metric);
  const [confirming, setConfirming] = useState(false);
  const [starting, setStarting] = useState(false);
  const maxMb = config.dataset.max_mb;

  const reset = () => {
    setFile(null);
    setDataset(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const selectFile = (selected) => {
    reset();
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) return setError("Sólo se permiten archivos con extensión .csv.");
    if (selected.size > maxMb * 1024 * 1024) return setError(`El archivo supera el tamaño máximo de ${maxMb} MB.`);
    return setFile(selected);
  };

  const validate = async (useReference = false) => {
    setValidating(true);
    setError(null);
    try {
      setDataset(useReference ? await trainingService.useReferenceDataset() : await trainingService.validateDataset(file));
    } catch (err) {
      if (err.response?.status === 422 && err.response.data?.id) setDataset(err.response.data);
      else setError(getErrorMessage(err, "No se pudo validar el archivo."));
    } finally {
      setValidating(false);
      window.dispatchEvent(new Event("sipd:notifications-changed"));
    }
  };

  const start = async () => {
    setStarting(true);
    try {
      const run = await trainingService.start({ dataset: dataset.id, algorithms, selection_metric: metric });
      setConfirming(false);
      reset();
      onStarted(run);
    } catch (err) {
      setError(getErrorMessage(err, "No se pudo iniciar el entrenamiento."));
      setConfirming(false);
    } finally {
      setStarting(false);
    }
  };

  const toggleAlgorithm = (value) =>
    setAlgorithms((current) => (current.includes(value) ? current.filter((a) => a !== value) : [...current, value]));
  const valid = dataset?.status === "VALIDO";
  const labels = Object.fromEntries(config.algorithms.map((a) => [a.value, a.label]));
  const fixed = config.fixed_parameters;
  const warnings = dataset?.report?.warnings || [];

  return (
    <Card title="Nuevo reentrenamiento" subtitle="1) Seleccione los datos · 2) Valide · 3) Configure · 4) Confirme. Entrenar no activa ningún modelo.">
      {error && <Alert type="error" onClose={() => setError(null)}>{error}</Alert>}
      {blocked && <Alert type="info">Hay un entrenamiento en curso. Podrá iniciar otro cuando termine.</Alert>}
      <div className="grid-2">
        <div>
          <h3 className="section-title">Datos de entrenamiento</h3>
          <label className="dropzone compact">
            <UploadCloud size={30} aria-hidden="true" />
            <span><strong>Seleccione un archivo CSV</strong> con datos históricos etiquetados</span>
            <small className="text-muted">UTF-8, separado por coma o punto y coma. Máximo {maxMb} MB y {formatNumber(config.dataset.max_rows)} registros.</small>
            <input ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => selectFile(e.target.files?.[0])} />
          </label>
          {file && <div className="file-chip"><FileSpreadsheet size={18} aria-hidden="true" /><span>{file.name}</span><small className="text-muted">{(file.size / 1024).toFixed(1)} KB</small></div>}
          <div className="button-row">
            {config.dataset.reference_available && (
              <Button variant="ghost" icon={Database} disabled={validating || blocked} onClick={() => validate(true)}>Usar dataset de referencia (sintético)</Button>
            )}
            {(file || dataset) && <Button variant="ghost" onClick={reset}>Limpiar</Button>}
            <Button icon={CheckCircle2} disabled={!file || Boolean(dataset) || blocked} loading={validating} onClick={() => validate(false)}>Validar archivo</Button>
          </div>
        </div>
        <div>
          <h3 className="section-title">Requisitos (del procedimiento actual)</h3>
          <p className="text-muted">Columnas obligatorias:</p>
          <p className="code-list">{config.dataset.required_columns.map((c) => <code key={c}>{c}</code>)}</p>
          <p className="text-muted">Opcionales (se imputan si faltan): </p>
          <p className="code-list">{config.dataset.optional_columns.map((c) => <code key={c}>{c}</code>)}</p>
          <ul className="rules">
            <li><code>{config.dataset.target_column}</code>: variable objetivo, 0 = no desertó, 1 = desertó.</li>
            <li>Mínimo {config.dataset.min_rows} registros y {config.dataset.min_rows_per_class} por clase (requisito técnico de la partición estratificada).</li>
            <li>Las variables derivadas (tasa de aprobación y variación del promedio) se calculan automáticamente.</li>
          </ul>
        </div>
      </div>

      {dataset && <ValidationReport dataset={dataset} />}

      {valid && (
        <div className="training-config">
          <h3 className="section-title">Configuración</h3>
          <fieldset className="fieldset">
            <legend className="field-label">Algoritmos a entrenar</legend>
            <div className="checkbox-grid">
              {config.algorithms.map((a) => (
                <label key={a.value} className="checkbox">
                  <input type="checkbox" checked={algorithms.includes(a.value)} onChange={() => toggleAlgorithm(a.value)} />
                  <span>{a.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <Select label="Métrica para recomendar el mejor candidato" value={metric} onChange={(e) => setMetric(e.target.value)}
            options={config.selection_metrics.map((m) => ({ value: m, label: METRICS.find(([k]) => k === m)?.[1] || m }))} />
          <p className="text-muted small">
            Parámetros fijos del procedimiento experimental (no modificables para conservar la comparabilidad): partición
            estratificada {Math.round((1 - fixed.test_fraction) * 100)} % entrenamiento / {Math.round(fixed.test_fraction * 100)} % prueba,
            semilla {fixed.random_state} y umbral de clasificación {fixed.threshold} para calcular Precision, Recall y F1
            (coincide con el inicio del nivel de riesgo Medio).
          </p>
          <div className="button-row">
            <Button icon={BrainCog} disabled={!algorithms.length || blocked} onClick={() => setConfirming(true)}>Revisar y entrenar</Button>
          </div>
        </div>
      )}

      <ConfirmationModal
        open={confirming}
        title="Confirmar reentrenamiento"
        confirmLabel="Iniciar entrenamiento"
        loading={starting}
        onConfirm={start}
        onCancel={() => setConfirming(false)}
        message={
          <span className="confirm-summary">
            <strong>Datos:</strong> {dataset?.filename} ({formatNumber(dataset?.rows)} registros{dataset?.is_synthetic ? ", sintéticos" : ""})<br />
            <strong>Algoritmos:</strong> {algorithms.map((a) => labels[a]).join(", ")}<br />
            <strong>Métrica de selección:</strong> {METRICS.find(([k]) => k === metric)?.[1] || metric} · umbral {fixed.threshold}<br />
            {warnings.length > 0 && <><strong>Advertencias:</strong> {warnings.length} (ver detalle de la validación)<br /></>}
            El entrenamiento se ejecuta en el servidor y puede tardar varios minutos. Se crearán versiones nuevas
            <strong> pendientes de aprobación</strong>; el modelo activo y las versiones anteriores no se modifican.
          </span>
        }
      />
    </Card>
  );
}

function RunHistory({ config, selected, onSelect, refreshKey }) {
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const history = useApi(() => trainingService.runs({ ...filters, page, page_size: HISTORY_PAGE_SIZE }),
    [JSON.stringify(filters), page, refreshKey], { errorMessage: "Error al cargar el historial de entrenamientos." });
  const set = (key, value) => { setPage(1); setFilters((f) => ({ ...f, [key]: value })); };
  const columns = [
    { key: "id", header: "#", render: (r) => <Button variant="link" size="sm" onClick={() => onSelect(r.id)}>#{r.id}</Button> },
    { key: "created_at", header: "Inicio", render: (r) => formatDateTime(r.created_at) },
    { key: "finished_at", header: "Fin", render: (r) => formatDateTime(r.finished_at) },
    { key: "requested_by", header: "Responsable" },
    { key: "dataset", header: "Fuente de datos", render: (r) => `${r.dataset.filename} (${formatNumber(r.dataset.rows)})` },
    { key: "algorithms", header: "Algoritmos", render: (r) => r.algorithms.length },
    { key: "status", header: "Estado", render: (r) => <StatusBadge className={RUN_STATUS_CLASS[r.status]} label={r.status_display} /> },
    { key: "version", header: "Versión", render: (r) => r.version || "—" },
    { key: "f1", header: "F1 (mejor)", align: "right", render: (r) => formatMetric(r.versions.find((v) => v.selected)?.metrics?.f1) },
    { key: "activation", header: "Activación", render: (r) => (r.versions.some((v) => v.active) ? <StatusBadge className="status-success" label="Activa" /> : r.versions.length ? <StatusBadge className={APPROVAL_CLASS[r.versions.find((v) => v.selected)?.approval_status]} label={r.versions.find((v) => v.selected)?.approval_status_display} /> : "—") },
    { key: "error_message", header: "Error", className: "cell-wrap", render: (r) => r.error_message || "—" },
  ];
  return (
    <Card title="Historial de entrenamientos" padded={false} subtitle="Seleccione una ejecución para ver su detalle y evaluación.">
      <FilterBar onClear={() => { setFilters({}); setPage(1); }} hasActive={Object.values(filters).some(Boolean)}>
        <Filter label="Estado" value={filters.status} onChange={(v) => set("status", v)} options={RUN_STATUSES.map((s) => ({ value: s, label: s }))} />
        <Filter label="Algoritmo" value={filters.algorithm} onChange={(v) => set("algorithm", v)} options={config.algorithms} />
        <label className="filter"><span className="filter-label">Desde:</span>
          <input type="date" className="filter-select" value={filters.date_from || ""} onChange={(e) => set("date_from", e.target.value)} aria-label="Fecha desde" /></label>
        <label className="filter"><span className="filter-label">Hasta:</span>
          <input type="date" className="filter-select" value={filters.date_to || ""} onChange={(e) => set("date_to", e.target.value)} aria-label="Fecha hasta" /></label>
      </FilterBar>
      <DataTable columns={columns} rows={history.data?.results} loading={history.loading} error={history.error} onRetry={history.reload}
        emptyTitle="No hay entrenamientos registrados." caption="Historial de entrenamientos"
        onRowClick={(r) => onSelect(r.id)} rowKey={(r) => `${r.id}${r.id === selected ? "-selected" : ""}`} />
      {history.data && <Pagination page={page} pageSize={HISTORY_PAGE_SIZE} count={history.data.count} onPageChange={setPage} />}
    </Card>
  );
}

function ActivationHistory({ refreshKey, onChanged }) {
  const data = useApi(() => trainingService.activations(), [refreshKey], { errorMessage: "Error al cargar el historial de activaciones." });
  const [target, setTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const rollback = async () => {
    setBusy(true);
    try {
      const version = await trainingService.rollback(target.id);
      setMessage({ type: "success", text: `Se recuperó ${version.name} v${version.version} como modelo activo.` });
      onChanged();
      window.dispatchEvent(new Event("sipd:notifications-changed"));
    } catch (err) {
      setMessage({ type: "error", text: getErrorMessage(err) });
    } finally {
      setBusy(false);
      setTarget(null);
    }
  };
  const candidates = data.data?.rollback_candidates || [];
  return (
    <Card title="Activaciones y recuperación de versiones" padded={false}
      subtitle="Las versiones anteriores nunca se borran. Sólo pueden recuperarse versiones que estuvieron activas y cuyos artefactos superan la verificación de integridad.">
      {message && <div className="card-inner"><Alert type={message.type} onClose={() => setMessage(null)}>{message.text}</Alert></div>}
      {candidates.length > 0 && (
        <div className="card-inner rollback-list">
          {candidates.map((v) => (
            <div key={v.id} className="rollback-item">
              <span><strong>{v.name}</strong> v{v.version} <small className="text-muted">F1 {formatMetric(v.metrics?.f1)}</small></span>
              <Button variant="secondary" size="sm" icon={RotateCcw} onClick={() => setTarget(v)}>Recuperar</Button>
            </div>
          ))}
        </div>
      )}
      <DataTable caption="Historial de activaciones" rows={data.data?.results} loading={data.loading} error={data.error} onRetry={data.reload}
        emptyTitle="No hay cambios de modelo activo registrados."
        columns={[
          { key: "created_at", header: "Fecha", render: (a) => formatDateTime(a.created_at) },
          { key: "action_display", header: "Acción" },
          { key: "previous_label", header: "Versión anterior", render: (a) => a.previous_label || "—" },
          { key: "new_label", header: "Nueva versión activa" },
          { key: "performed_by", header: "Responsable", render: (a) => a.performed_by || "Sistema" },
        ]} />
      <ConfirmationModal open={Boolean(target)} title="Recuperar versión anterior" confirmLabel="Recuperar" loading={busy}
        onConfirm={rollback} onCancel={() => setTarget(null)}
        message={`Se verificará la integridad de ${target?.name} v${target?.version} y, si es correcta, pasará a ser el modelo activo. La versión activa actual se conservará.`} />
    </Card>
  );
}

export default function ReentrenamientoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const overview = useApi(() => trainingService.overview(), [], { errorMessage: "Error al cargar el estado de los modelos." });
  const [refreshKey, setRefreshKey] = useState(0);
  const runParam = Number(searchParams.get("run")) || null;
  const activeRunId = overview.data?.active_run?.id || null;
  const selectedRun = runParam || activeRunId;

  const selectRun = (id) => setSearchParams(id ? { run: String(id) } : {}, { replace: true });
  const reloadOverview = overview.reload;
  const refresh = useCallback(() => {
    reloadOverview();
    setRefreshKey((k) => k + 1);
  }, [reloadOverview]);

  if (overview.loading && !overview.data) return <Loading />;
  if (overview.error && !overview.data) return <ErrorMessage message={overview.error} onRetry={overview.reload} />;
  const { config } = overview.data;

  return (
    <>
      <PageHeader title="Reentrenamiento de modelos"
        description="Ejecuta el procedimiento real de entrenamiento y evaluación en el servidor. Las versiones nuevas quedan pendientes de aprobación y se activan sólo por decisión explícita." />
      {!config.enabled && <Alert type="warning" title="Reentrenamiento no disponible en este despliegue.">{config.disabled_reason}</Alert>}
      <ModelsStatus overview={overview.data} />
      {selectedRun && <TrainingRunDetail key={selectedRun} runId={selectedRun} onChanged={refresh} />}
      {config.enabled && (
        <NewTraining config={config} blocked={Boolean(activeRunId)} onStarted={(run) => { selectRun(run.id); refresh(); }} />
      )}
      <RunHistory config={config} selected={selectedRun} onSelect={selectRun} refreshKey={refreshKey} />
      <ActivationHistory refreshKey={refreshKey} onChanged={refresh} />
    </>
  );
}
