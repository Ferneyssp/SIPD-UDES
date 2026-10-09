import EmptyState from "./EmptyState";
import ErrorMessage from "./ErrorMessage";
import Loading from "./Loading";

/**
 * Tabla genérica con estados de carga, error y vacío.
 * columns: [{ key, header, render?: (row) => node, align?: "left"|"right"|"center", className? }]
 */
export default function DataTable({
  columns, rows, rowKey = "id", loading, error, onRetry, emptyTitle, emptyDescription, caption, onRowClick,
}) {
  if (error) return <div className="table-state"><ErrorMessage message={error} onRetry={onRetry} /></div>;
  if (loading && !rows?.length) return <div className="table-state"><Loading /></div>;
  if (!rows?.length) return <EmptyState title={emptyTitle} description={emptyDescription} />;

  return (
    <div className={`table-wrap ${loading ? "is-refreshing" : ""}`}>
      <table className="data-table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={`align-${column.align || "left"} ${column.className || ""}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={typeof rowKey === "function" ? rowKey(row) : row[rowKey]}
              className={onRowClick ? "clickable" : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((column) => (
                <td key={column.key} className={`align-${column.align || "left"} ${column.className || ""}`} data-label={column.header}>
                  {column.render ? column.render(row) : row[column.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
