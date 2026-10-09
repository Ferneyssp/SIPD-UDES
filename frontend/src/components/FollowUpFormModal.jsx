import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { followupService } from "../services/api";
import { getErrorMessage, getFieldErrors } from "../utils/errors";
import Alert from "./Alert";
import Button from "./Button";
import Input from "./Input";
import Modal from "./Modal";
import Select from "./Select";

const today = () => new Date().toISOString().slice(0, 10);

/** Registro / edición de un seguimiento (intervención) de un estudiante. */
export default function FollowUpFormModal({ open, onClose, onSaved, followup, studentCode }) {
  const { user } = useAuth();
  const { config } = useConfig();
  const { data: responsibles } = useApi(() => followupService.responsibles(), [], { enabled: open });
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setErrors({});
    setError(null);
    setForm(followup ? {
      student: followup.student, intervention_type: followup.intervention_type, observation: followup.observation,
      user: String(followup.user), status: followup.status, follow_up_date: followup.follow_up_date,
    } : {
      student: studentCode || "", intervention_type: "TUTORIA", observation: "", user: String(user.id),
      status: "PENDIENTE", follow_up_date: today(),
    });
  }, [open, followup, studentCode, user.id]);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = { ...form, student: form.student.trim().toUpperCase(), user: Number(form.user) };
      const saved = followup ? await followupService.update(followup.id, payload) : await followupService.create(payload);
      onSaved(saved);
    } catch (err) {
      setErrors(getFieldErrors(err));
      setError(getErrorMessage(err, "No se pudo guardar el seguimiento."));
    } finally {
      setSaving(false);
    }
  };

  const statusOptions = (config?.followup_statuses || []).filter((s) => s.value !== "SIN_SEGUIMIENTO");
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={followup ? "Editar seguimiento" : "Registrar nueva intervención"}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="followup-form" loading={saving}>Guardar intervención</Button>
        </>
      }
    >
      <form id="followup-form" className="form-grid" onSubmit={submit}>
        {error && <div className="span-2"><Alert type="error">{error}</Alert></div>}
        <Input label="Estudiante (código)" value={form.student || ""} onChange={update("student")} placeholder="E001"
          required disabled={Boolean(followup || studentCode)} error={errors.student} />
        <Select label="Tipo de intervención" value={form.intervention_type || ""} onChange={update("intervention_type")}
          options={config?.intervention_types || []} error={errors.intervention_type} />
        <Input as="textarea" rows={4} className="span-2" label="Observaciones" value={form.observation || ""}
          onChange={update("observation")} maxLength={2000} required error={errors.observation}
          hint="Registre acciones y acuerdos. Evite incluir datos sensibles innecesarios." />
        <Select label="Responsable" value={form.user || ""} onChange={update("user")} error={errors.user}
          options={(responsibles || [{ id: user.id, name: user.username, role: user.role_display }]).map((r) => ({ value: String(r.id), label: `${r.name} (${r.role})` }))} />
        <Select label="Estado" value={form.status || ""} onChange={update("status")} options={statusOptions} error={errors.status} />
        <Input label="Fecha" type="date" value={form.follow_up_date || ""} onChange={update("follow_up_date")} error={errors.follow_up_date} />
      </form>
    </Modal>
  );
}
