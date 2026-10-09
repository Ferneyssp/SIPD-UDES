import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState";

export default function NotFoundPage() {
  return (
    <EmptyState
      icon={Compass}
      title="La página solicitada no existe."
      action={<Link className="btn btn-primary btn-md" to="/inicio">Volver a Inicio</Link>}
    />
  );
}
