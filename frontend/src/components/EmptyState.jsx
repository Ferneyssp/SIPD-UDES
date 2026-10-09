import { Inbox } from "lucide-react";

export default function EmptyState({ title = "No hay información disponible.", description, icon: Icon = Inbox, action }) {
  return (
    <div className="empty-state">
      <Icon size={36} aria-hidden="true" />
      <p className="empty-title">{title}</p>
      {description && <p className="empty-description">{description}</p>}
      {action}
    </div>
  );
}
