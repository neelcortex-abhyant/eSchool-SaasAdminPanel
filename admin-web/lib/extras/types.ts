import type { RefKind } from "@/lib/extras/refs";
import type { Raw } from "@/lib/extras/api";

export type FieldType = "text" | "textarea" | "number" | "date" | "time" | "datetime" | "email" | "tel" | "url" | "select" | "checkbox" | "ref";

export type FieldDef = {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  /** For "ref": what the id points at. */
  ref?: RefKind;
  /** For "select". */
  options?: { value: string; label: string }[];
  /** The server's PATCH ignores this field, so it can't change after the record is added. */
  createOnly?: boolean;
  hint?: string;
  span?: boolean;
  maxLength?: number;
  /** Default value for a new record. */
  initial?: string;
  /** A typed id the server can't list yet, so no picker is possible. */
  rawId?: boolean;
  /** For a session ref: pick the current session when the form opens empty. */
  defaultCurrent?: boolean;
};

export type ColumnDef = {
  key: string;
  label: string;
  /** Show the name for this id. */
  ref?: RefKind;
  /** Turn the cell value into text. */
  format?: (value: unknown, row: Raw) => string;
};

/** A list of records on one server path, with add, edit and delete as the server allows. */
export type ResourceConfig = {
  kind: "resource";
  title: string;
  description: string;
  /** e.g. "/holidays"; rows are edited at `${path}/{id}`. */
  path: string;
  /** Name of one record, e.g. "holiday". */
  noun: string;
  fields: FieldDef[];
  columns: ColumnDef[];
  canEdit: boolean;
  canDelete: boolean;
  /** False for read-only lists. */
  canCreate?: boolean;
  /** Text searched by the page's search box. */
  searchKeys?: string[];
  /** Fixed query parameters for the list. */
  listParams?: Record<string, string | number>;
  /** What the server doesn't keep or can't do, shown above the table. */
  note?: string;
  /** Rows sorted by this key, newest/largest first when `desc`. */
  sort?: { key: string; desc?: boolean };
};

/** A settings object read with GET and saved with PUT. */
export type SettingsConfig = {
  kind: "settings";
  title: string;
  description: string;
  path: string;
  fields: FieldDef[];
  note?: string;
};

/** Read-only figures from one or more GET routes. */
export type ReportConfig = {
  kind: "report";
  title: string;
  description: string;
  paths: { path: string; title: string }[];
  /** Keys shown as money. */
  money?: string[];
};

export type ExtraConfig = ResourceConfig | SettingsConfig | ReportConfig;
