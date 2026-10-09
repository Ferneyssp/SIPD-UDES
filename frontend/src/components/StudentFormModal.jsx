import { useEffect, useState } from "react";
import { useConfig } from "../context/ConfigContext";
import { studentService } from "../services/api";
import { getErrorMessage, getFieldErrors } from "../utils/errors";
import Alert from "./Alert";
import Button from "./Button";
import Input from "./Input";
import Modal from "./Modal";
import Select from "./Select";

const EMPTY = { anonymous_code: "", program: "", semester: "1", academic_status: "Activo" };

/** Registro/edición básica de un estudiante (sólo Administrador). Sin datos personales. */
export default function StudentFormModal({ open, onClose, onSaved, student }) {
  const { programs, config } = useConfig();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setErrors({});
    setError(null);
    setForm(student ? {
      anonymous_code: student.anonymous_code, program: student.program_code,
      semester: String(student.semester), academic_status: student.academic_status,
    } : EMPTY);
  }, [open, student]);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = { ...form, semester: Number(form.semester) };
      const saved = student
        ? await studentService.update(student.anonymous_code, payload)
        : await studentService.create(payload);
      onSaved(saved);
    } catch (err) {
      setErrors(getFieldErrors(err));
      setError(getErrorMessage(err, "No se pudo guardar el estudiante."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={student ? `Editar estudiante ${student.anonymous_code}` : "Registrar estudiante"}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="student-form" loading={saving}>Guardar</Button>
        </>
      }
    >
      <form id="student-form" className="form-grid" onSubmit={submit}>
        {error && <div className="span-2"><Alert type="error">{error}</Alert></div>}
        <Input label="Código anonimizado" value={form.anonymous_code} onChange={update("anonymous_code")}
          placeholder="E001" hint="No use nombres ni documentos: sólo el código seudonimizado." required
          disabled={Boolean(student)} error={errors.anonymous_code} />
        <Select label="Programa" value={form.program} onChange={update("program")} placeholder="Seleccione..." required
          options={programs.map((p) => ({ value: p.code, label: p.name }))} error={errors.program} />
        <Select label="Semestre" value={form.semester} onChange={update("semester")}
          options={Array.from({ length: 12 }, (_, i) => ({ value: String(i + 1), label: `Semestre ${i + 1}` }))} />
        <Select label="Estado académico" value={form.academic_status} onChange={update("academic_status")}
          options={config?.academic_statuses || []} />
      </form>
    </Modal>
  );
}
