/** CSV export for report tables. */

function cell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  // Quote anything with commas, quotes or line breaks; neutralise spreadsheet formulas.
  const safe = /^[=+\-@]/.test(text) ? `'${text}` : text;
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function toCsv<T>(rows: T[], columns: { label: string; value: (row: T) => unknown }[]): string {
  return [columns.map((column) => cell(column.label)).join(","), ...rows.map((row) => columns.map((column) => cell(column.value(row))).join(","))].join("\r\n");
}

/** Saves text as a file in the browser. */
export function downloadText(fileName: string, text: string, type = "text/csv;charset=utf-8"): void {
  const url = URL.createObjectURL(new Blob(["﻿", text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
