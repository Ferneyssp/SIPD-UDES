import { Link } from "react-router-dom";

/** Contenedor con título opcional y acciones a la derecha. */
export default function Card({ title, subtitle, actions, children, className = "", padded = true, ...props }) {
  return (
    <section className={`card ${padded ? "card-padded" : ""} ${className}`} {...props}>
      {(title || actions) && (
        <header className="card-header">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {subtitle && <p className="card-subtitle">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** Tarjeta de indicador (Inicio). tone: neutral | high | medium | low | info. Con `to`, abre esa ruta (p. ej. el listado filtrado). */
export function StatCard({ label, value, detail, caption, icon: Icon, tone = "neutral", to }) {
  const content = (
    <article className={`stat-card tone-${tone} ${to ? "is-link" : ""}`}>
      {Icon && (
        <span className="stat-icon" aria-hidden="true">
          <Icon size={24} />
        </span>
      )}
      <div className="stat-body">
        <p className="stat-label">{label}</p>
        <p className="stat-value">
          {value}
          {detail && <span className="stat-detail"> {detail}</span>}
        </p>
        {caption && <p className="stat-caption">{caption}</p>}
      </div>
    </article>
  );
  return to ? <Link to={to} className="stat-card-link" aria-label={`${label}: ${value}. Ver listado`}>{content}</Link> : content;
}
