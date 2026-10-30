import { Plus } from "lucide-react";
import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { followupService } from "../services/api";
import { formatDate } from "../utils/format";
import Button from "./Button";
import Card from "./Card";
import DataTable from "./DataTable";
import FollowUpFormModal from "./FollowUpFormModal";
import StatusBadge from "./StatusBadge";

/**
 * Historial de seguimiento de un estudiante (perfil e Historial). Es de sólo lectura: cada intervención
 * queda registrada y sólo se pueden agregar nuevas. El último registro se actualiza desde Seguimiento.
 */
export default function FollowUpHistory({ studentCode, onSaved }) {
  const [open, setOpen] = useState(false);
  const followups = useApi(() => followupService.list({ student_exact: studentCode, page_size: 50 }), [studentCode]);
  const columns = [
    { key: "follow_up_date", header: "Fecha", render: (f) => formatDate(f.follow_up_date) },
    { key: "intervention_type_display", header: "Tipo" },
    { key: "observation", header: "Observación", className: "cell-wrap" },
    { key: "user_name", header: "Responsable" },
    { key: "status", header: "Estado", render: (f) => <StatusBadge status={f.status} label={f.status_display} /> },
  ];
  return (
    <Card
      title="Historial de seguimiento"
      subtitle="Intervenciones registradas por los coordinadores, de la más reciente a la más antigua."
      actions={<Button icon={Plus} onClick={() => setOpen(true)}>Registrar seguimiento</Button>}
      padded={false}
    >
      <DataTable columns={columns} rows={followups.data?.results} loading={followups.loading} error={followups.error}
        onRetry={followups.reload} emptyTitle="Aún no hay seguimientos registrados." caption="Historial de seguimiento" />
      <FollowUpFormModal
        open={open}
        studentCode={studentCode}
        onClose={() => setOpen(false)}
        onSaved={() => {
          setOpen(false);
          followups.reload();
          onSaved?.();
        }}
      />
    </Card>
  );
}
