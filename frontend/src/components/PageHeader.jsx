export default function PageHeader({ title, badge, actions, description }) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">
          {title}
          {badge !== undefined && badge !== null && <span className="page-badge">{badge}</span>}
        </h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}
