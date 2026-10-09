import { Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import DataTable from "../components/DataTable";
import Filter, { FilterBar } from "../components/Filter";
import FollowUpFormModal from "../components/FollowUpFormModal";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import SearchBar from "../components/SearchBar";
import StatusBadge from "../components/StatusBadge";
import { useConfig } from "../context/ConfigContext";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../hooks/useFilters";
import { followupService } from "../services/api";
import { formatDate, formatNumber } from "../utils/format";

const PAGE_SIZE = 10;

export default function SeguimientoPage() {
  const { config, periods } = useConfig();
  const { filters, setFilter, clearFilters } = useFilters();
  const [modal, setModal] = useState({ open: false, followup: null });
  const page = Number(filters.page || 1);
  const { data, loading, error, reload } = useApi(
    () => followupService.list({ ...filters, page, page_size: PAGE_SIZE }),
    [JSON.stringify(filters)],
    { errorMessage: "Error al cargar los seguimientos." },
  );
  const responsibles = useApi(() => followupService.responsibles(), []);

  const columns = [
    { key: "follow_up_date", header: "Fecha", render: (f) => formatDate(f.follow_up_date) },
    { key: "student", header: "Estudiante", render: (f) => <><Link className="link-strong" to={`/estudiantes/${f.student}`}>{f.student}</Link><br /><small className="text-muted">{f.program}</small></> },
    { key: "intervention_type_display", header: "Tipo de intervención", className: "text-strong" },
    { key: "observation", header: "Observaciones", render: (f) => <span className="truncate" title={f.observation}>{f.observation}</span> },
    { key: "user_name", header: "Responsable" },
    { key: "status", header: "Estado", render: (f) => <StatusBadge status={f.status} label={f.status_display} /> },
    { key: "actions", header: "Acciones", align: "right", render: (f) => <Button variant="link" size="sm" icon={Pencil} onClick={() => setModal({ open: true, followup: f })}>Editar</Button> },
  ];

  return (
    <>
      <PageHeader
        title="Bitácora de intervenciones"
        badge={data ? `${formatNumber(data.count)} registros` : null}
        actions={<Button icon={Plus} onClick={() => setModal({ open: true, followup: null })}>Nueva intervención</Button>}
      />
      <FilterBar onClear={clearFilters} hasActive={Object.keys(filters).length > 0}>
        <SearchBar value={filters.student || ""} onChange={(v) => setFilter("student", v.toUpperCase())} placeholder="Código del estudiante (E001)" label="Estudiante" />
        <Filter label="Estado" value={filters.status} onChange={(v) => setFilter("status", v)}
          options={(config?.followup_statuses || []).filter((s) => s.value !== "SIN_SEGUIMIENTO")} />
        <Filter label="Tipo" value={filters.intervention_type} onChange={(v) => setFilter("intervention_type", v)} options={config?.intervention_types || []} />
        <Filter label="Responsable" value={filters.user} onChange={(v) => setFilter("user", v)}
          options={(responsibles.data || []).map((r) => ({ value: String(r.id), label: r.name }))} />
        <Filter label="Periodo" value={filters.period} onChange={(v) => setFilter("period", v)} options={periods.map((p) => ({ value: p.code, label: p.code }))} />
      </FilterBar>

      <Card padded={false}>
        <DataTable columns={columns} rows={data?.results} loading={loading} error={error} onRetry={reload}
          emptyTitle="No hay seguimientos registrados con estos filtros." caption="Seguimientos" />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} count={data.count} onPageChange={(p) => setFilter("page", String(p))} />}
      </Card>

      <FollowUpFormModal
        open={modal.open}
        followup={modal.followup}
        onClose={() => setModal({ open: false, followup: null })}
        onSaved={() => { setModal({ open: false, followup: null }); reload(); }}
      />
    </>
  );
}
