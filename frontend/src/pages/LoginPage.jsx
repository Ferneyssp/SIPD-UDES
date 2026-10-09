import { Eye, EyeOff, GraduationCap, Lock, Mail } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Input from "../components/Input";
import { APP_NAME, INSTITUTION_NAME, SYSTEM_DESCRIPTION } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../utils/errors";

export default function LoginPage() {
  const { login, isAuthenticated, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({ username: "", password: "", remember: false });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) return <Navigate to="/inicio" replace />;

  const expired = sessionExpired || searchParams.get("expired") === "1";

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.username.trim() || !form.password) {
      setError("Ingrese su usuario o correo y su contraseña.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await login(form.username.trim(), form.password, form.remember);
      navigate(location.state?.from || "/inicio", { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, "Credenciales incorrectas."));
    } finally {
      setSubmitting(false);
    }
  };

  const update = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.type === "checkbox" ? event.target.checked : event.target.value }));

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <span className="login-logo" aria-hidden="true">
            <GraduationCap size={40} />
          </span>
          <h1 className="login-title">{APP_NAME}</h1>
          <p className="login-institution">{INSTITUTION_NAME}</p>
          <p className="login-description">{SYSTEM_DESCRIPTION}</p>
        </div>

        {expired && !error && <Alert type="warning">Sesión expirada. Inicie sesión nuevamente.</Alert>}
        {error && <Alert type="error">{error}</Alert>}

        <form onSubmit={handleSubmit} className="login-form" noValidate>
          <Input
            label="Usuario o correo institucional"
            icon={Mail}
            name="username"
            autoComplete="username"
            value={form.username}
            onChange={update("username")}
            autoFocus
          />
          <Input
            label="Contraseña"
            icon={Lock}
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            value={form.password}
            onChange={update("password")}
            trailing={
              <button
                type="button"
                className="icon-button input-trailing"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            }
          />
          <Button type="submit" size="lg" className="btn-block" loading={submitting}>
            Iniciar sesión
          </Button>
          <label className="checkbox">
            <input type="checkbox" checked={form.remember} onChange={update("remember")} />
            <span>Recordar mi sesión en este equipo</span>
          </label>
        </form>
      </div>
    </div>
  );
}
