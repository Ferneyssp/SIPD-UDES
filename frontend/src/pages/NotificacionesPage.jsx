import { CheckCheck, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import Alert from "../components/Alert";
import Button from "../components/Button";
import Card from "../components/Card";
import DataTable from "../components/DataTable";
import Filter, { FilterBar } from "../components/Filter";
import { LEVEL_CLASS } from "../components/NotificationBell";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import StatusBadge from "../components/StatusBadge";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../hooks/useFilters";
import { notificationService } from "../services/api";
import { getErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber } from "../utils/format";

const PAGE_SIZE = 15;
const notifyChanged = () => window.dispatchEvent(new Event("sipd:notifications-changed"));

export default function NotificacionesPage() {
  const { filters, setFilter, clearFilters } = useFilters();
  const page = Number(filters.page || 1);
  const [message, setMessage] = useState(null);
  const { data, loading, error, reload } = useApi(
    () => notificationService.list({ ...filters, page, page_size: PAGE_SIZE }),
    [JSON.stringify(filters)],
    { errorMessage: "Error al cargar las notificaciones." },
  );

  const markRead = async (item) => {
    try {
      await notificationService.markRead(item.id);
      notifyChanged();
      reload();
    } catch (err) {
      setMessage({ type: "error", text: getErrorMessage(err) });
    }
  };

  const markAll = async () => {
    try {
      const result = await notificationService.markAllRead();
      setMessage({ type: "success", text: `${result.updated} notificaciones marcadas como leídas.` });
      notifyChanged();
      reload();
    } catch (err) {
      setMessage({ type: "error", text: getErrorMessage(err) });
    }
  };

  const columns = [
    { key: "created_at", header: "Fecha", render: (n) => formatDateTime(n.created_at) },
    {
      key: "title", header: "Notificación", className: "cell-wrap",
      render: (n) => (
        <>
          <strong className={n.is_read ? "" : "text-strong"}>{n.title}</strong>
          {n.message && <><br /><small className="text-muted">{n.message}</small></>}
        </>
      ),
    },
    { key: "type", header: "Tipo", render: (n) => <StatusBadge className={LEVEL_CLASS[n.level]} label={n.type_display} /> },
    { key: "status", header: "Estado", render: (n) => (n.is_read ? <span className="text-muted">Leída {formatDateTime(n.read_at)}</span> : <StatusBadge className="status-info" label="Sin leer" />) },
    {
      key: "actions", header: "Acciones", align: "right",
      render: (n) => (
        <span className="row-actions">
          {n.link && <Link className="link-action" to={n.link} onClick={() => !n.is_read && markRead(n)}><ExternalLink size={14} aria-hidden="true" /> Ver operación</Link>}
          {!n.is_read && <Button variant="link" size="sm" onClick={() => markRead(n)}>Marcar como leída</Button>}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Notificaciones"
        badge={data ? `${formatNumber(data.unread)} sin leer` : null}
        description="Avisos generados por los procesos del sistema. Leer una notificación no la elimina del historial."
        actions={<Button variant="secondary" icon={CheckCheck} onClick={markAll} disabled={!data?.unread}>Marcar todas como leídas</Button>}
      />
      {message && <Alert type={message.type} onClose={() => setMessage(null)}>{message.text}</Alert>}
      <FilterBar onClear={clearFilters} hasActive={Object.keys(filters).some((k) => k !== "page")}>
        <Filter label="Estado" value={filters.is_read} onChange={(v) => setFilter("is_read", v)} allLabel="Todas"
          options={[{ value: "false", label: "Sin leer" }, { value: "true", label: "Leídas" }]} />
        <Filter label="Categoría" value={filters.category} onChange={(v) => setFilter("category", v)} allLabel="Todas"
          options={data?.categories || []} />
        <Filter label="Tipo" value={filters.type} onChange={(v) => setFilter("type", v)} options={data?.types || []} />
      </FilterBar>
      <Card padded={false}>
        <DataTable columns={columns} rows={data?.results} loading={loading} error={error} onRetry={reload}
          emptyTitle="No hay notificaciones para los filtros seleccionados." caption="Notificaciones" />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPageChange={(p) => setFilter("page", String(p))} />}
      </Card>
    </>
  );
}
