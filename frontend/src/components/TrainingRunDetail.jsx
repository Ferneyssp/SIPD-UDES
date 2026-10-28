import { CheckCircle2, Loader2, Power, ShieldCheck, ThumbsDown, Timer, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { trainingService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { formatDateTime } from "../utils/format";
import Alert from "./Alert";
import Button from "./Button";
import Card from "./Card";
import ConfirmationModal from "./ConfirmationModal";
import DataTable from "./DataTable";
import ErrorMessage from "./ErrorMessage";
import Loading from "./Loading";
import StatusBadge from "./StatusBadge";

const POLL_MS = 3000;
export const METRICS = [["accuracy", "Accuracy"], ["precision", "Precision"], ["recall", "Recall"], ["f1", "F1-score"], ["roc_auc", "ROC-AUC"]];
export const RUN_STATUS_CLASS = {
  PENDIENTE: "status-neutral", VALIDANDO: "status-info", PREPARANDO: "status-info", ENTRENANDO: "status-info",
  EVALUANDO: "status-info", REGISTRANDO: "status-info", COMPLETADO: "status-success", FALLIDO: "status-danger",
  CANCELADO: "status-muted",
};
export const APPROVAL_CLASS = { PENDIENTE: "status-warning", APROBADO: "status-success", RECHAZADO: "status-danger", NO_REQUERIDA: "status-neutral" };

export function formatMetric(value) {
  return typeof value === "number" ? value.toFixed(3).replace(".", ",") : "No calculado";
}

function formatDiff(value) {
  if (typeof value !== "number") return "—";
  const text = (value > 0 ? "+" : "") + value.toFixed(3).replace(".", ",");
  return <span className={value > 0 ? "diff-up" : value < 0 ? "diff-down" : ""}>{text}</span>;
}

function elapsed(start, end) {
  if (!start) return null;
  const seconds = Math.max(0, Math.round(((end ? new Date(end) : new Date()) - new Date(start)) / 1000));
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} min ${seconds % 60} s` : `${seconds} s`;
}

/** Hace polling del estado real de la ejecución hasta que termina. */
function useRun(runId) {
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer;
    const load = async () => {
      try {
        const data = await trainingService.run(runId);
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (!data.is_finished) timer = setTimeout(load, POLL_MS);
      } catch (err) {
        if (cancelled) return;
        setError(getErrorMessage(err, "No se pudo consultar el estado del entrenamiento."));
        timer = setTimeout(load, POLL_MS * 3);
      }
    };
    setRun(null);
    load();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [runId, tick]);

  return { run, error, reload: () => setTick((t) => t + 1) };
}

function Progress({ run, onCancel, cancelling }) {
  const [, setNow] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setNow((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="run-progress" aria-live="polite">
      <div className="run-progress-head">
        <Loader2 className="spin" size={22} aria-hidden="true" />
        <div>
          <strong>{run.status_display}</strong>
          <p className="text-muted">{run.stage_message}</p>
        </div>
        <span className="run-elapsed"><Timer size={15} aria-hidden="true" /> {elapsed(run.started_at || run.created_at)}</span>
      </div>
      <p className="text-muted small">
        El proceso se ejecuta en el servidor. Puede navegar a otras secciones: al volver se mostrará el estado real.
        No se muestra un porcentaje porque el avance sólo se conoce por etapas.
      </p>
      {run.status === "PENDIENTE" && <Button variant="secondary" size="sm" loading={cancelling} onClick={onCancel}>Cancelar (aún no ha comenzado)</Button>}
    </div>
  );
}

function Timeline({ events }) {
  return (
    <ol className="run-timeline">
      {events.map((event, index) => (
        <li key={`${event.at}-${index}`}>
          <StatusBadge className={RUN_STATUS_CLASS[event.status]} label={event.status} />
          <span className="text-muted">{formatDateTime(event.at)}</span>
          <span>{event.message}</span>
        </li>
      ))}
    </ol>
  );
}

function VersionReview({ version, comparison, acceptance, onAction, busy }) {
  const [confirm, setConfirm] = useState(null);
  const run = async () => {
    await onAction(confirm, version);
    setConfirm(null);
  };
  const confirmText = {
    approve: `Se aprobará ${version.name} v${version.version}. Aprobar no la activa: el modelo activo no cambia hasta que la active explícitamente.`,
    reject: `Se rechazará ${version.name} v${version.version}. Permanecerá registrada pero no podrá activarse.`,
    activate: `Las nuevas predicciones usarán ${version.name} v${version.version}. La versión activa actual se conservará y podrá recuperarse. Las predicciones ya generadas no cambian.`,
  };

  return (
    <article className="version-review">
      <header className="version-review-head">
        <div>
          <h3>{version.name} <small className="text-muted">v{version.version}</small></h3>
          <div className="badge-row">
            {version.selected && <StatusBadge className="status-info" label="Mejor según la métrica de selección" />}
            <StatusBadge className={APPROVAL_CLASS[version.approval_status]} label={version.approval_status_display} />
            {version.active && <StatusBadge className="status-success" label="Activo" />}
          </div>
        </div>
        <div className="row-actions">
          {version.approval_status === "PENDIENTE" && (
            <>
              <Button size="sm" icon={ShieldCheck} disabled={busy || !acceptance?.passed} onClick={() => setConfirm("approve")}
                title={acceptance?.passed ? undefined : "No cumple los criterios de aceptación"}>Aprobar</Button>
              <Button size="sm" variant="secondary" icon={ThumbsDown} disabled={busy} onClick={() => setConfirm("reject")}>Rechazar</Button>
            </>
          )}
          {version.approval_status === "APROBADO" && !version.active && (
            <Button size="sm" icon={Power} disabled={busy} onClick={() => setConfirm("activate")}>Activar</Button>
          )}
        </div>
      </header>

      <div className="metric-grid">
        {METRICS.map(([key, label]) => (
          <div key={key} className="mini-stat"><span>{label}</span><strong>{formatMetric(version.metrics?.[key])}</strong></div>
        ))}
      </div>
      <p className="text-muted small">
        Métricas sobre el conjunto de <strong>prueba</strong> ({version.metrics?.test_size ?? "—"} registros, umbral de
        clasificación {version.metrics?.threshold ?? "—"}). No son métricas de entrenamiento.
      </p>
      {version.metrics?.confusion_matrix && (
        <table className="confusion-matrix" aria-label="Matriz de confusión del conjunto de prueba">
          <thead><tr><th /><th scope="col">Predicho: no deserta</th><th scope="col">Predicho: deserta</th></tr></thead>
          <tbody>
            <tr><th scope="row">Real: no desertó</th><td>{version.metrics.confusion_matrix.tn} <small>VN</small></td><td>{version.metrics.confusion_matrix.fp} <small>FP</small></td></tr>
            <tr><th scope="row">Real: desertó</th><td>{version.metrics.confusion_matrix.fn} <small>FN</small></td><td>{version.metrics.confusion_matrix.tp} <small>VP</small></td></tr>
          </tbody>
        </table>
      )}

      {acceptance && (
        <div className="acceptance">
          <h4>Criterios de aceptación {acceptance.passed ? <StatusBadge className="status-success" label="Cumple" /> : <StatusBadge className="status-danger" label="No cumple" />}</h4>
          <ul>
            {acceptance.checks.map((check) => (
              <li key={check.code}>
                {check.passed ? <CheckCircle2 size={16} className="text-ok" aria-label="Cumple" /> : <XCircle size={16} className="text-bad" aria-label="No cumple" />}
                <span><strong>{check.label}.</strong> <span className="text-muted">{check.detail}</span></span>
              </li>
            ))}
          </ul>
          {!acceptance.metric_minimums_configured && (
            <p className="text-muted small">No hay mínimos de rendimiento configurados (ML_ACCEPTANCE_MIN_*): el proyecto no define
              umbrales aprobados, por lo que la decisión de aprobar corresponde al administrador según la comparación.</p>
          )}
        </div>
      )}

      {comparison && (
        <div className="comparison">
          <h4>Comparación con {comparison.reference.label} {comparison.reference.active && "(activa)"}</h4>
          {comparison.warnings.map((warning) => <Alert key={warning} type="warning">{warning}</Alert>)}
          <DataTable caption="Comparación de métricas" rowKey="metric"
            columns={[
              { key: "metric", header: "Métrica", render: (r) => METRICS.find(([k]) => k === r.metric)?.[1] || r.metric },
              { key: "reference", header: "Versión de referencia", align: "right", render: (r) => formatMetric(r.reference) },
              { key: "new", header: "Nueva versión", align: "right", render: (r) => formatMetric(r.new) },
              { key: "difference", header: comparison.comparable ? "Diferencia" : "Diferencia (orientativa)", align: "right", render: (r) => formatDiff(r.difference) },
            ]}
            rows={comparison.rows} />
        </div>
      )}

      <ConfirmationModal
        open={Boolean(confirm)}
        title={{ approve: "Aprobar versión", reject: "Rechazar versión", activate: "Activar versión" }[confirm] || ""}
        message={confirmText[confirm]}
        confirmLabel={{ approve: "Aprobar", reject: "Rechazar", activate: "Activar" }[confirm]}
        variant={confirm === "reject" ? "danger" : "primary"}
        loading={busy}
        onConfirm={run}
        onCancel={() => setConfirm(null)}
      />
    </article>
  );
}

/** Estado, etapas, resultados y revisión de una ejecución de entrenamiento. */
export default function TrainingRunDetail({ runId, onChanged }) {
  const { run, error, reload } = useRun(runId);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [versions, setVersions] = useState({});
  const [wasRunning, setWasRunning] = useState(false);

  useEffect(() => {
    if (run && !run.is_finished) setWasRunning(true);
    if (run?.is_finished && wasRunning) {
      setWasRunning(false);
      onChanged?.();
      window.dispatchEvent(new Event("sipd:notifications-changed"));
    }
  }, [run, wasRunning, onChanged]);

  const act = async (action, version) => {
    setBusy(true);
    setMessage(null);
    try {
      const call = { approve: () => trainingService.approve(version.id, ""), reject: () => trainingService.reject(version.id, ""),
        activate: () => trainingService.activate(version.id) }[action];
      const updated = await call();
      setVersions((current) => ({ ...current, [version.id]: updated }));
      setMessage({ type: "success", text: { approve: "Versión aprobada. Aún no está activa.", reject: "Versión rechazada.",
        activate: `${updated.name} v${updated.version} es ahora el modelo activo.` }[action] });
      reload();
      onChanged?.();
      window.dispatchEvent(new Event("sipd:notifications-changed"));
    } catch (err) {
      setMessage({ type: "error", text: getErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    setBusy(true);
    try {
      await trainingService.cancel(run.id);
      reload();
      onChanged?.();
    } catch (err) {
      setMessage({ type: "error", text: getErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  if (error && !run) return <Card><ErrorMessage message={error} onRetry={reload} /></Card>;
  if (!run) return <Card><Loading message="Consultando el estado del entrenamiento..." /></Card>;

  return (
    <Card
      title={<>Entrenamiento #{run.id} <StatusBadge className={RUN_STATUS_CLASS[run.status]} label={run.status_display} /></>}
      subtitle={`Solicitado por ${run.requested_by || "—"} el ${formatDateTime(run.created_at)} · ${run.dataset.filename} (${run.dataset.rows} registros${run.dataset.is_synthetic ? ", sintéticos" : ""}) · Métrica de selección: ${run.selection_metric}`}
    >
      {error && <Alert type="warning">{error} Se reintentará automáticamente.</Alert>}
      {message && <Alert type={message.type} onClose={() => setMessage(null)}>{message.text}</Alert>}
      {!run.is_finished && <Progress run={run} onCancel={cancel} cancelling={busy} />}
      {run.status === "FALLIDO" && (
        <Alert type="error" title="El entrenamiento falló.">
          {run.error_message} No se activó ninguna versión: el modelo activo sigue siendo el anterior.
        </Alert>
      )}
      {run.status === "CANCELADO" && <Alert type="info">{run.stage_message}</Alert>}
      {run.status === "COMPLETADO" && (
        <>
          <Alert type="success" title="Entrenamiento completado.">
            {run.stage_message} Duración: {elapsed(run.started_at, run.finished_at)}. Ninguna versión se activó automáticamente.
          </Alert>
          {run.versions.map((item) => {
            const version = { ...item, ...versions[item.id] };
            return (
              <VersionReview key={item.id} busy={busy} onAction={act} version={version} acceptance={version.acceptance}
                comparison={run.comparisons?.[String(item.id)]} />
            );
          })}
        </>
      )}
      <details className="run-details">
        <summary>Etapas registradas ({run.events.length})</summary>
        <Timeline events={run.events} />
      </details>
    </Card>
  );
}
