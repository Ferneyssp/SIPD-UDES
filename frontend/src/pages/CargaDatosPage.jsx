import { CheckCircle2, Download, FileSpreadsheet, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import ConfirmationModal from "../components/ConfirmationModal";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { uploadService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber } from "../utils/format";

const STATUS_CLASS = { VALIDADO: "status-warning", PROCESADO: "status-success", RECHAZADO: "status-danger", FALLIDO: "status-danger" };
const REQUIRED = ["student_code", "program_code", "academic_period", "semester", "gpa", "credits_enrolled", "credits_approved",
  "credits_failed", "failed_subjects", "attendance_percentage", "academic_status"];

function Step({ number, title, active, done }) {
  return (
    <li className={`step ${active ? "active" : ""} ${done ? "done" : ""}`}>
      <span className="step-number">{done ? <CheckCircle2 size={16} /> : number}</span>
      {title}
    </li>
  );
}

export default function CargaDatosPage() {
  const { config } = useConfig();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [validating, setValidating] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [askConfirm, setAskConfirm] = useState(false);
  const [runPredictions, setRunPredictions] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const uploads = useApi(() => uploadService.list({ page_size: 10 }), [], { errorMessage: "Error al cargar el historial de cargas." });
  const maxMb = config?.upload_max_mb || 5;

  const selectFile = (selected) => {
    setError(null);
    setReport(null);
    setResult(null);
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setError("Sólo se permiten archivos con extensión .csv.");
      return;
    }
    if (selected.size > maxMb * 1024 * 1024) {
      setError(`El archivo supera el tamaño máximo de ${maxMb} MB.`);
      return;
    }
    setFile(selected);
  };

  const validate = async () => {
    setValidating(true);
    setError(null);
    try {
      setReport(await uploadService.validate(file));
    } catch (err) {
      const data = err.response?.data;
      if (err.response?.status === 422 && data?.status) setReport(data);
      else setError(getErrorMessage(err, "No se pudo procesar el archivo."));
    } finally {
      setValidating(false);
      uploads.reload();
    }
  };

  const confirm = async () => {
    setConfirming(true);
    try {
      setResult(await uploadService.confirm(report.id, runPredictions));
      setAskConfirm(false);
      uploads.reload();
    } catch (err) {
      setError(getErrorMessage(err, "No se pudo procesar el archivo."));
      setAskConfirm(false);
    } finally {
      setConfirming(false);
    }
  };

  const downloadTemplate = async () => {
    try {
      const response = await uploadService.downloadTemplate();
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "plantilla_carga_sipd.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getErrorMessage(err, "No se pudo descargar la plantilla."));
    }
  };

  const reset = () => {
    // Una carga validada que no se confirma se descarta: sólo se conservan las procesadas.
    if (report?.id && report.status === "VALIDADO" && !result) uploadService.discard(report.id).then(uploads.reload).catch(() => {});
    setFile(null);
    setReport(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const step = result ? 4 : report ? 3 : file ? 2 : 1;
  const errorColumns = [
    { key: "row", header: "Fila", render: (e) => e.row ?? "—" },
    { key: "column", header: "Columna" },
    { key: "message", header: "Error" },
    { key: "value", header: "Valor recibido", render: (e) => e.value ?? "—" },
  ];
  const historyColumns = [
    { key: "upload_date", header: "Fecha", render: (u) => formatDateTime(u.upload_date) },
    { key: "filename", header: "Archivo" },
    { key: "uploaded_by", header: "Usuario" },
    { key: "records_found", header: "Encontrados", align: "right" },
    { key: "records_valid", header: "Válidos", align: "right" },
    { key: "records_failed", header: "Con errores", align: "right" },
    { key: "records_processed", header: "Procesados", align: "right" },
    { key: "predictions_generated", header: "Predicciones", align: "right" },
    { key: "status", header: "Estado", render: (u) => <StatusBadge className={STATUS_CLASS[u.status]} label={u.status_display} /> },
  ];

  return (
    <>
      <PageHeader
        title="Carga de datos"
        description="Actualice la información académica de los estudiantes mediante archivos CSV."
        actions={<Button variant="secondary" icon={Download} onClick={downloadTemplate}>Descargar plantilla</Button>}
      />

      <ol className="steps" aria-label="Pasos de la carga">
        <Step number={1} title="Seleccionar archivo" active={step === 1} done={step > 1} />
        <Step number={2} title="Validar estructura" active={step === 2} done={step > 2} />
        <Step number={3} title="Revisar y confirmar" active={step === 3} done={step > 3} />
        <Step number={4} title="Procesado" active={step === 4} done={false} />
      </ol>

      {error && <Alert type="error" onClose={() => setError(null)}>{error}</Alert>}

      <div className="grid-2">
        <Card title="1. Seleccionar archivo">
          <label
            className={`dropzone ${dragOver ? "drag-over" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); selectFile(e.dataTransfer.files?.[0]); }}
          >
            <UploadCloud size={36} aria-hidden="true" />
            <span><strong>Haga clic para seleccionar</strong> o arrastre un archivo CSV aquí</span>
            <small className="text-muted">Formato UTF-8, separado por coma o punto y coma. Máximo {maxMb} MB.</small>
            <input ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => selectFile(e.target.files?.[0])} />
          </label>
          {file && (
            <div className="file-chip">
              <FileSpreadsheet size={18} aria-hidden="true" />
              <span>{file.name}</span>
              <small className="text-muted">{(file.size / 1024).toFixed(1)} KB</small>
            </div>
          )}
          <div className="button-row">
            <Button icon={CheckCircle2} disabled={!file || Boolean(report)} loading={validating} onClick={validate}>Validar archivo</Button>
            {(file || report) && <Button variant="ghost" onClick={reset}>Cancelar / nueva carga</Button>}
          </div>
        </Card>

        <Card title="Estructura esperada">
          <p className="text-muted">Columnas obligatorias:</p>
          <p className="code-list">{REQUIRED.map((c) => <code key={c}>{c}</code>)}</p>
          <p className="text-muted">Columnas opcionales (encuestas institucionales):</p>
          <p className="code-list">
            {["course_repetitions", "works_while_studying", "socioeconomic_stratum", "financial_difficulty", "motivation_level"].map((c) => <code key={c}>{c}</code>)}
          </p>
          <ul className="rules">
            <li><code>student_code</code>: identificador anonimizado (E001). No incluya nombres ni documentos.</li>
            <li><code>academic_period</code>: formato AAAA-1 o AAAA-2.</li>
            <li><code>gpa</code>: entre {config?.gpa_range.min ?? 0} y {config?.gpa_range.max ?? 5}. <code>attendance_percentage</code>: entre 0 y 100.</li>
            <li>Créditos aprobados + reprobados ≤ créditos matriculados. No se permiten filas duplicadas.</li>
          </ul>
        </Card>
      </div>

      {report && (
        <Card title="2. Resultado de la validación" subtitle={report.message}>
          <div className="stats-grid three">
            <div className="mini-stat"><span>Registros encontrados</span><strong>{formatNumber(report.records_found)}</strong></div>
            <div className="mini-stat ok"><span>Registros válidos</span><strong>{formatNumber(report.records_valid)}</strong></div>
            <div className="mini-stat bad"><span>Registros con errores</span><strong>{formatNumber(report.records_failed)}</strong></div>
          </div>
          {report.records_failed > 0 && (
            <Alert type="warning">
              Las filas con errores <strong>no se cargarán</strong>. Corríjalas en el archivo y cárguelo nuevamente si lo requiere.
            </Alert>
          )}
          {report.errors?.length > 0 && (
            <div className="errors-table">
              <DataTable columns={errorColumns} rows={report.errors} rowKey={(e) => `${e.row}-${e.column}-${e.message}`} caption="Errores de validación" />
              {report.errors.length >= 500 && <p className="text-muted">Se muestran los primeros 500 errores.</p>}
            </div>
          )}
          {!result && report.status === "VALIDADO" && (
            <div className="button-row">
              <label className="checkbox">
                <input type="checkbox" checked={runPredictions} onChange={(e) => setRunPredictions(e.target.checked)} />
                <span>Generar predicciones para los registros cargados</span>
              </label>
              <Button icon={UploadCloud} onClick={() => setAskConfirm(true)}>Confirmar carga ({report.records_valid} registros)</Button>
            </div>
          )}
        </Card>
      )}

      {result && <Alert type="success" title="Carga procesada.">{result.message}</Alert>}

      <Card title="Historial de cargas" padded={false}>
        <DataTable columns={historyColumns} rows={uploads.data?.results} loading={uploads.loading} error={uploads.error}
          onRetry={uploads.reload} emptyTitle="Aún no se han realizado cargas." caption="Historial de cargas" />
      </Card>

      <ConfirmationModal
        open={askConfirm}
        title="Confirmar carga de datos"
        message={`Se cargarán ${report?.records_valid} registros válidos${runPredictions ? " y se generarán sus predicciones" : ""}. Los registros existentes del mismo estudiante y periodo se actualizarán. ¿Desea continuar?`}
        confirmLabel="Confirmar carga"
        loading={confirming}
        onConfirm={confirm}
        onCancel={() => setAskConfirm(false)}
      />
    </>
  );
}
