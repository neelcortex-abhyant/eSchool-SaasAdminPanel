"use client";

import type { ReactNode } from "react";

export type Column<T> = {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  /** Set to make the header a sort button. The value is passed to onSort. */
  sortKey?: string;
};

export type SortState = { key: string; order: "asc" | "desc" };

/**
 * Table that turns into stacked cards on narrow screens. Each cell carries its column label
 * in data-label, which the mobile CSS shows next to the value.
 */
export function DataTable<T extends { id: number }>({
  columns,
  rows,
  loading,
  emptyText,
  actions,
  sort,
  onSort,
}: {
  columns: Column<T>[];
  rows: T[];
  loading: boolean;
  emptyText: string;
  actions?: (row: T) => ReactNode;
  sort?: SortState;
  onSort?: (key: string) => void;
}) {
  const span = columns.length + (actions ? 1 : 0);
  return (
    <div className="table-wrap">
      <table className="data-table acad-table" aria-busy={loading}>
        <thead>
          <tr>
            {columns.map((column) => {
              const sorted = sort && column.sortKey === sort.key ? sort.order : null;
              return (
                <th key={column.key} scope="col" aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}>
                  {column.sortKey && onSort ? (
                    <button className="sort-btn" type="button" onClick={() => onSort(column.sortKey as string)}>
                      {column.label}
                      <span aria-hidden className="sort-mark">
                        {sorted === "asc" ? " ▲" : sorted === "desc" ? " ▼" : " ↕"}
                      </span>
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
            {actions ? (
              <th scope="col">
                <span className="acad-sr">Actions</span>
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {loading && rows.length === 0 ? (
            [0, 1, 2].map((index) => (
              <tr key={`skeleton-${index}`} className="acad-skeleton-row">
                <td colSpan={span}>
                  <div className="skeleton" style={{ height: 18 }} />
                </td>
              </tr>
            ))
          ) : rows.length === 0 ? (
            <tr className="acad-empty-row">
              <td colSpan={span}>
                <div className="empty-state">{emptyText}</div>
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.id} className={loading ? "is-stale" : undefined}>
                {columns.map((column) => (
                  <td key={column.key} data-label={column.label}>
                    {column.render(row)}
                  </td>
                ))}
                {actions ? (
                  <td className="acad-row-actions" data-label="">
                    {actions(row)}
                  </td>
                ) : null}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);
  return (
    <nav className="acad-pager" aria-label="Pagination">
      <span className="muted">
        {first}–{last} of {total}
      </span>
      <div className="acad-pager-buttons">
        <button className="btn-pill btn-pill-green-soft" type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <span className="muted">
          Page {page} of {lastPage}
        </span>
        <button className="btn-pill btn-pill-green-soft" type="button" disabled={page >= lastPage} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </nav>
  );
}
