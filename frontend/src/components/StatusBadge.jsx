import { FOLLOWUP_STATUS_CLASS } from "../utils/risk";

export default function StatusBadge({ status, label, className }) {
  const tone = className || FOLLOWUP_STATUS_CLASS[status] || "status-neutral";
  return <span className={`badge ${tone}`}>{label || status}</span>;
}
