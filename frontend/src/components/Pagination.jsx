import Button from "./Button";

function pageList(current, total) {
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const result = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1] > 1) result.push("…" + page);
    result.push(page);
  });
  return result;
}

export default function Pagination({ page, pageSize, count, onPageChange }) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  if (!count) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);
  return (
    <nav className="pagination" aria-label="Paginación">
      <span className="pagination-info">
        Mostrando registros del {from} al {to} de {count.toLocaleString("es-CO")}
      </span>
      <div className="pagination-controls">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Anterior</Button>
        {pageList(page, totalPages).map((item) =>
          typeof item === "string" ? (
            <span key={item} className="pagination-ellipsis" aria-hidden="true">…</span>
          ) : (
            <button
              key={item}
              type="button"
              className={`page-button ${item === page ? "active" : ""}`}
              aria-current={item === page ? "page" : undefined}
              onClick={() => onPageChange(item)}
            >
              {item}
            </button>
          ),
        )}
        <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>Siguiente</Button>
      </div>
    </nav>
  );
}
