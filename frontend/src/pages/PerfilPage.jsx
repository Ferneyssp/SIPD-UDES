import { KeyRound } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import Input from "../components/Input";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { authService } from "../services/api";
import { getErrorMessage, getFieldErrors } from "../utils/errors";
import { formatDate, formatDateTime, initials } from "../utils/format";

const EMPTY = { current_password: "", new_password: "", confirm_password: "" };

export default function PerfilPage() {
  const { user, logoutLocal } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const update = (field) => (event) => setForm((f) => ({ ...f, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setErrors({});
    setError(null);
    if (form.new_password !== form.confirm_password) {
      setErrors({ confirm_password: "Las contraseñas no coinciden." });
      return;
    }
    setSaving(true);
    try {
      await authService.changePassword(form);
      // Por seguridad se cierran todas las sesiones; el inicio de sesión confirma que el cambio se hizo.
      logoutLocal();
      navigate("/login?aviso=contrasena-actualizada", { replace: true });
    } catch (err) {
      setErrors(getFieldErrors(err));
      setError(getErrorMessage(err, "No se pudo cambiar la contraseña."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader title="Perfil" />
      <div className="grid-2">
        <Card title="Información de la cuenta">
          <div className="profile-head">
            <span className="avatar avatar-lg" aria-hidden="true">{initials(user)}</span>
            <div>
              <p className="profile-name">{[user.first_name, user.last_name].filter(Boolean).join(" ") || user.username}</p>
              <p className="text-muted">{user.role_display}</p>
            </div>
          </div>
          <dl className="info-list">
            <div><dt>Nombre de usuario</dt><dd>{user.username}</dd></div>
            <div><dt>Correo</dt><dd>{user.email}</dd></div>
            <div><dt>Rol</dt><dd>{user.role_display}</dd></div>
            <div><dt>Programas asignados</dt><dd>{user.programs?.length ? user.programs.map((p) => p.name).join(", ") : "Todos / no aplica"}</dd></div>
            <div><dt>Fecha de creación</dt><dd>{formatDate(user.created_at)}</dd></div>
            <div><dt>Último acceso</dt><dd>{formatDateTime(user.last_login)}</dd></div>
            <div><dt>Estado</dt><dd><StatusBadge className={user.is_active ? "status-success" : "status-muted"} label={user.is_active ? "Activo" : "Inactivo"} /></dd></div>
          </dl>
        </Card>
        <Card title="Cambiar contraseña" subtitle="Al cambiarla se cerrará la sesión y deberá ingresar nuevamente.">
          <form className="stack" onSubmit={submit}>
            {error && <Alert type="error">{error}</Alert>}
            <Input label="Contraseña actual" type="password" autoComplete="current-password" value={form.current_password}
              onChange={update("current_password")} required error={errors.current_password} />
            <Input label="Nueva contraseña" type="password" autoComplete="new-password" value={form.new_password}
              onChange={update("new_password")} required minLength={8} error={errors.new_password}
              hint="Mínimo 8 caracteres; evite contraseñas comunes o sólo numéricas." />
            <Input label="Confirmar nueva contraseña" type="password" autoComplete="new-password" value={form.confirm_password}
              onChange={update("confirm_password")} required error={errors.confirm_password} />
            <Button type="submit" icon={KeyRound} loading={saving}>Actualizar contraseña</Button>
          </form>
        </Card>
      </div>
    </>
  );
}
