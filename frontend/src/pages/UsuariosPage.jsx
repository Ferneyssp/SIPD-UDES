import { Pencil, Plus, Power } from "lucide-react";
import { useEffect, useState } from "react";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import ConfirmationModal from "../components/ConfirmationModal";
import DataTable from "../components/DataTable";
import Filter, { FilterBar } from "../components/Filter";
import Input from "../components/Input";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import SearchBar from "../components/SearchBar";
import Select from "../components/Select";
import StatusBadge from "../components/StatusBadge";
import { ROLES } from "../config/appConfig";
import { useAuth } from "../context/AuthContext";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useDebounce } from "../hooks/useDebounce";
import { useFilters } from "../hooks/useFilters";
import { userService } from "../services/api";
import { getErrorMessage, getFieldErrors } from "../utils/errors";
import { formatDate } from "../utils/format";

const PAGE_SIZE = 10;
const EMPTY_FORM = { username: "", email: "", first_name: "", last_name: "", role: ROLES.COORDINATOR, program_ids: [], can_manage_users: false, password: "" };

function UserFormModal({ open, user, onClose, onSaved }) {
  const { config, programs: allPrograms } = useConfig();
  const { user: currentUser } = useAuth();
  const isAdmin = currentUser.role === ROLES.ADMIN;
  // Un coordinador gestor sólo crea coordinadores y sólo con sus propios programas (lo exige el backend).
  const ownIds = new Set((currentUser.programs || []).map((p) => p.id));
  const programs = isAdmin ? allPrograms : allPrograms.filter((p) => ownIds.has(p.id));
  const roleOptions = (config?.roles || []).filter((r) => isAdmin || r.value !== ROLES.ADMIN);
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setErrors({});
    setError(null);
    setForm(user ? {
      username: user.username, email: user.email, first_name: user.first_name, last_name: user.last_name, role: user.role,
      program_ids: user.programs.map((p) => p.id), can_manage_users: user.can_manage_users, password: "",
    } : EMPTY_FORM);
  }, [open, user]);

  const update = (field) => (event) => setForm((f) => ({ ...f, [field]: event.target.type === "checkbox" ? event.target.checked : event.target.value }));
  const toggleProgram = (id) => setForm((f) => ({
    ...f, program_ids: f.program_ids.includes(id) ? f.program_ids.filter((p) => p !== id) : [...f.program_ids, id],
  }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload = { ...form };
    if (!payload.password) delete payload.password;
    try {
      const saved = user ? await userService.update(user.id, payload) : await userService.create(payload);
      onSaved(saved, user ? "Usuario actualizado." : "Usuario creado.");
    } catch (err) {
      setErrors(getFieldErrors(err));
      setError(getErrorMessage(err, "No se pudo guardar el usuario."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} size="lg" title={user ? `Editar usuario ${user.username}` : "Crear usuario"}
      footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button type="submit" form="user-form" loading={saving}>Guardar</Button></>}>
      <form id="user-form" className="form-grid" onSubmit={submit} autoComplete="off">
        {error && <div className="span-2"><Alert type="error">{error}</Alert></div>}
        <Input label="Usuario" value={form.username} onChange={update("username")} required error={errors.username} />
        <Input label="Correo institucional" type="email" value={form.email} onChange={update("email")} required error={errors.email} />
        <Input label="Nombres" value={form.first_name} onChange={update("first_name")} />
        <Input label="Apellidos" value={form.last_name} onChange={update("last_name")} />
        <Select label="Rol" value={form.role} onChange={update("role")} options={roleOptions} error={errors.role} />
        <Input label={user ? "Nueva contraseña (opcional)" : "Contraseña"} type="password" autoComplete="new-password"
          value={form.password} onChange={update("password")} required={!user} error={errors.password}
          hint="Mínimo 8 caracteres; no puede ser sólo numérica ni muy común." />
        <fieldset className="span-2 fieldset">
          <legend>Programas asignados {form.role === ROLES.COORDINATOR && <small className="text-muted">(sin programas no verá estudiantes)</small>}
            {form.role === ROLES.ADMIN && <small className="text-muted">(el administrador accede a todos)</small>}</legend>
          <div className="checkbox-grid">
            {programs.map((p) => (
              <label key={p.id} className="checkbox">
                <input type="checkbox" checked={form.program_ids.includes(p.id)} onChange={() => toggleProgram(p.id)} disabled={form.role === ROLES.ADMIN} />
                <span>{p.name}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {form.role === ROLES.COORDINATOR && isAdmin && (
          <label className="checkbox span-2">
            <input type="checkbox" checked={form.can_manage_users} onChange={update("can_manage_users")} />
            <span>Otorgar permiso explícito para administrar usuarios</span>
          </label>
        )}
      </form>
    </Modal>
  );
}

export default function UsuariosPage() {
  const { user: me } = useAuth();
  const { config } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const [search, setSearch] = useState(filters.search || "");
  const debounced = useDebounce(search);
  const [modal, setModal] = useState({ open: false, user: null });
  const [toggleTarget, setToggleTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const page = Number(filters.page || 1);

  useEffect(() => {
    if ((filters.search || "") !== debounced) setFilter("search", debounced);
  }, [debounced, filters.search, setFilter]);

  const { data, loading, error, reload } = useApi(
    () => userService.list({ ...filters, page, page_size: PAGE_SIZE }),
    [JSON.stringify(filters)],
    { errorMessage: "Error al cargar los usuarios." },
  );

  const toggleActive = async () => {
    setBusy(true);
    try {
      if (toggleTarget.is_active) await userService.deactivate(toggleTarget.id);
      else await userService.activate(toggleTarget.id);
      setNotice({ type: "success", text: `Usuario ${toggleTarget.is_active ? "desactivado" : "activado"}.` });
      reload();
    } catch (err) {
      setNotice({ type: "error", text: getErrorMessage(err) });
    } finally {
      setBusy(false);
      setToggleTarget(null);
    }
  };

  const columns = [
    { key: "username", header: "Usuario", render: (u) => <><strong>{u.username}</strong><br /><small className="text-muted">{[u.first_name, u.last_name].filter(Boolean).join(" ")}</small></> },
    { key: "email", header: "Correo" },
    { key: "role_display", header: "Rol" },
    { key: "programs", header: "Programas", render: (u) => (u.role === ROLES.ADMIN ? "Todos" : u.programs.map((p) => p.code).join(", ") || "Sin asignar") },
    { key: "is_active", header: "Estado", render: (u) => <StatusBadge className={u.is_active ? "status-success" : "status-muted"} label={u.is_active ? "Activo" : "Inactivo"} /> },
    { key: "created_at", header: "Fecha de creación", render: (u) => formatDate(u.created_at) },
    {
      key: "actions", header: "Acciones", align: "right",
      render: (u) => (
        <div className="row-actions">
          <Button variant="link" size="sm" icon={Pencil} onClick={() => setModal({ open: true, user: u })}>Editar</Button>
          {u.id !== me.id && (
            <Button variant="link" size="sm" icon={Power} onClick={() => setToggleTarget(u)}>{u.is_active ? "Desactivar" : "Activar"}</Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Usuarios" badge={data ? `${data.count} registros` : null}
        actions={<Button icon={Plus} onClick={() => setModal({ open: true, user: null })}>Crear usuario</Button>} />
      {notice && <Alert type={notice.type} onClose={() => setNotice(null)}>{notice.text}</Alert>}
      <FilterBar onClear={() => { setSearch(""); clearFilters(); }} hasActive={Object.keys(filters).length > 0}>
        <SearchBar value={search} onChange={setSearch} placeholder="Buscar por usuario, correo o nombre..." className="grow" />
        <Filter label="Rol" value={filters.role} onChange={(v) => setFilter("role", v)} options={config?.roles || []} />
        <Filter label="Estado" value={filters.is_active} onChange={(v) => setFilter("is_active", v)}
          options={[{ value: "true", label: "Activos" }, { value: "false", label: "Inactivos" }]} />
      </FilterBar>
      <Card padded={false}>
        <DataTable columns={columns} rows={data?.results} loading={loading} error={error} onRetry={reload} emptyTitle="No hay usuarios." caption="Usuarios" />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPageChange={(p) => setFilter("page", String(p))} />}
      </Card>
      <UserFormModal open={modal.open} user={modal.user} onClose={() => setModal({ open: false, user: null })}
        onSaved={(_saved, text) => { setModal({ open: false, user: null }); setNotice({ type: "success", text }); reload(); }} />
      <ConfirmationModal
        open={Boolean(toggleTarget)}
        title={toggleTarget?.is_active ? "Desactivar usuario" : "Activar usuario"}
        message={toggleTarget?.is_active
          ? `El usuario ${toggleTarget?.username} no podrá iniciar sesión. Su historial se conserva para trazabilidad.`
          : `El usuario ${toggleTarget?.username} podrá volver a iniciar sesión.`}
        confirmLabel={toggleTarget?.is_active ? "Desactivar" : "Activar"}
        variant={toggleTarget?.is_active ? "danger" : "primary"}
        loading={busy}
        onConfirm={toggleActive}
        onCancel={() => setToggleTarget(null)}
      />
    </>
  );
}
