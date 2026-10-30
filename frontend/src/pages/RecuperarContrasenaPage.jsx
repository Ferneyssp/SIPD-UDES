import { ArrowLeft, Lock, Mail } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Input from "../components/Input";
import { APP_NAME, INSTITUTION_NAME } from "../config/appConfig";
import { authService } from "../services/api";
import { getErrorMessage, getFieldErrors } from "../utils/errors";

function AuthCard({ title, description, children }) {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <img className="login-logo-img" src="/escudo-udes.png" alt="Escudo de la Universidad de Santander" />
          <h1 className="login-title">{APP_NAME}</h1>
          <p className="login-institution">{INSTITUTION_NAME}</p>
        </div>
        <h2 className="auth-subtitle">{title}</h2>
        <p className="login-description">{description}</p>
        {children}
        <Link to="/login" className="back-link auth-back"><ArrowLeft size={16} aria-hidden="true" /> Volver al inicio de sesión</Link>
      </div>
    </div>
  );
}

/** Paso 1: solicitar el enlace de recuperación por correo. */
export function RecuperarContrasenaPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (!email.includes("@")) {
      setError("Ingrese su correo institucional.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setSent((await authService.requestPasswordReset(email.trim())).detail);
    } catch (err) {
      setError(getErrorMessage(err, "No se pudo procesar la solicitud."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard title="Recuperar contraseña" description="Le enviaremos un enlace para crear una nueva contraseña.">
      {sent ? <Alert type="success">{sent}</Alert> : (
        <form className="login-form" onSubmit={submit} noValidate>
          {error && <Alert type="error">{error}</Alert>}
          <Input label="Correo institucional" icon={Mail} type="email" autoComplete="email" value={email}
            onChange={(e) => setEmail(e.target.value)} autoFocus />
          <Button type="submit" size="lg" className="btn-block" loading={loading}>Enviar enlace</Button>
        </form>
      )}
    </AuthCard>
  );
}

/** Paso 2: crear la nueva contraseña desde el enlace del correo. */
export function RestablecerContrasenaPage() {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState({ new_password: "", confirm_password: "" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setErrors({});
    setError(null);
    if (form.new_password !== form.confirm_password) {
      setErrors({ confirm_password: "Las contraseñas no coinciden." });
      return;
    }
    setLoading(true);
    try {
      await authService.confirmPasswordReset({ uid, token, ...form });
      navigate("/login?aviso=contrasena-restablecida", { replace: true });
    } catch (err) {
      setErrors(getFieldErrors(err));
      setError(err.response?.data?.detail || getErrorMessage(err, "No se pudo restablecer la contraseña."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard title="Crear nueva contraseña" description="Use al menos 8 caracteres; no puede ser sólo numérica ni muy común.">
      <form className="login-form" onSubmit={submit} noValidate>
        {error && (
          <Alert type="error">
            {error} {errors.token && <Link to="/recuperar-contrasena">Solicitar un nuevo enlace</Link>}
          </Alert>
        )}
        <Input label="Nueva contraseña" icon={Lock} type="password" autoComplete="new-password" value={form.new_password}
          onChange={update("new_password")} error={errors.new_password} autoFocus />
        <Input label="Confirmar contraseña" icon={Lock} type="password" autoComplete="new-password" value={form.confirm_password}
          onChange={update("confirm_password")} error={errors.confirm_password} />
        <Button type="submit" size="lg" className="btn-block" loading={loading}>Guardar contraseña</Button>
      </form>
    </AuthCard>
  );
}
