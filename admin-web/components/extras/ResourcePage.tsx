"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { FormModal } from "@/components/academics/FormModal";
import { useDebounced, useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage, FieldInput, type Tab } from "@/components/extras/Frame";
import { errorMessage } from "@/lib/academics";
import { create, displayValue, listRows, remove, update, type Raw } from "@/lib/extras/api";
import { initialValues, problems, toBody, type Values } from "@/lib/extras/form";
import { refKey, refNames, type RefKind } from "@/lib/extras/refs";
import type { ResourceConfig } from "@/lib/extras/types";
import type { StudentRow } from "@/lib/people";
import { num } from "@/lib/teaching/client";

const PAGE_SIZE = 20;

type Row = Raw & { id: number };

/** Names for every id column in the rows, loaded together. */
function useRefNames(config: ResourceConfig, rows: Row[]) {
  const [names, setNames] = useState<Record<string, Map<number, string>>>({});
  const refs = useMemo(() => config.columns.filter((column) => column.ref).map((column) => ({ key: column.key, ref: column.ref as RefKind })), [config]);
  useEffect(() => {
    let live = true;
    if (!rows.length || !refs.length) return;
    void Promise.all(
      refs.map(async ({ key, ref }) => [refKey(ref), await refNames(ref, rows.map((row) => num(row[key])).filter(Boolean)).catch(() => new Map<number, string>())] as const),
    ).then((entries) => {
      if (live) setNames(Object.fromEntries(entries));
    });
    return () => {
      live = false;
    };
  }, [rows, refs]);
  return names;
}

export function ResourcePage({ config, icon, tabs, extraActions }: { config: ResourceConfig; icon: ReactNode; tabs?: Tab[]; extraActions?: (row: Row, reload: () => void) => ReactNode }) {
  const [editing, setEditing] = useState<Row | "new" | null>(null);
  return (
    <ExtrasPage
      title={config.title}
      description={config.description}
      icon={icon}
      tabs={tabs}
      note={config.note}
      actions={
        config.canCreate === false ? undefined : (
          <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
            Add {config.noun}
          </button>
        )
      }
    >
      <ResourceBody config={config} editing={editing} setEditing={setEditing} extraActions={extraActions} />
    </ExtrasPage>
  );
}

function ResourceBody({
  config,
  editing,
  setEditing,
  extraActions,
}: {
  config: ResourceConfig;
  editing: Row | "new" | null;
  setEditing: (row: Row | "new" | null) => void;
  extraActions?: (row: Row, reload: () => void) => ReactNode;
}) {
  const toast = useToast();
  const state = useOptions(useCallback(() => listRows(config.path, config.listParams) as Promise<Row[]>, [config]));
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim().toLowerCase());
  const [page, setPage] = useState(1);
  const [removing, setRemoving] = useState<Row | null>(null);
  const [pending, setPending] = useState(false);
  const names = useRefNames(config, state.options);

  const cell = useCallback(
    (row: Row, key: string, ref?: RefKind, format?: (value: unknown, row: Raw) => string) => {
      const value = row[key];
      if (format) return format(value, row);
      if (ref && value !== null && value !== undefined) return names[refKey(ref)]?.get(num(value)) ?? `#${num(value)}`;
      return displayValue(value);
    },
    [names],
  );

  const rows = useMemo(() => {
    const sorted = [...state.options];
    if (config.sort) {
      const { key, desc } = config.sort;
      sorted.sort((a, b) => String(a[key] ?? "").localeCompare(String(b[key] ?? ""), undefined, { numeric: true }) * (desc ? -1 : 1));
    }
    if (!search) return sorted;
    const keys = config.searchKeys ?? config.columns.map((column) => column.key);
    return sorted.filter((row) => keys.some((key) => cell(row, key, config.columns.find((c) => c.key === key)?.ref).toLowerCase().includes(search)));
  }, [state.options, search, config, cell]);
  const shown = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const columns: Column<Row>[] = config.columns.map((column) => ({ key: column.key, label: column.label, render: (row) => cell(row, column.key, column.ref, column.format) }));

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label={`Search ${config.title.toLowerCase()}`} placeholder="Search" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={shown}
          loading={state.loading}
          emptyText={state.error ? "The list couldn't be loaded." : search ? "Nothing matches your search." : config.canCreate === false ? "Nothing to show yet." : `No ${config.noun} added yet.`}
          actions={
            config.canEdit || config.canDelete || extraActions
              ? (row) => (
                  <>
                    {extraActions?.(row, () => void state.reload())}
                    {config.canEdit ? (
                      <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                        Edit
                      </button>
                    ) : null}
                    {config.canDelete ? (
                      <button className="link-btn danger" type="button" onClick={() => setRemoving(row)}>
                        Delete
                      </button>
                    ) : null}
                  </>
                )
              : undefined
          }
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} />
      </div>
      {editing ? (
        <RecordForm
          config={config}
          row={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? `${capital(config.noun)} added.` : "Changes saved.");
            void state.reload();
          }}
        />
      ) : null}
      {removing ? (
        <ConfirmDialog
          title={`Delete this ${config.noun}?`}
          body="It will be removed from the list. This can't be undone here."
          confirmLabel="Delete"
          tone="danger"
          pending={pending}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await remove(`${config.path}/${removing.id}`);
              toast("success", `${capital(config.noun)} deleted.`);
              void state.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete."));
            } finally {
              setPending(false);
              setRemoving(null);
            }
          }}
        />
      ) : null}
    </>
  );
}

function capital(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function RecordForm({ config, row, onClose, onSaved }: { config: ResourceConfig; row: Row | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const [values, setValues] = useState<Values>(() => initialValues(config.fields, row));
  const [students, setStudents] = useState<Record<string, StudentRow | null>>({});
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const editing = Boolean(row);

  async function submit() {
    const invalid = problems(config.fields, values, editing);
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      const body = toBody(config.fields, values, editing);
      if (row) await update(`${config.path}/${row.id}`, body);
      else await create(config.path, body);
      onSaved(!row);
    } catch (caught) {
      errors.fromError(caught, "Unable to save.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={`${editing ? "Edit" : "Add"} ${config.noun}`} error={errors.formError} saving={saving} submitLabel={editing ? "Save changes" : `Add ${config.noun}`} wide={config.fields.length > 4} onSubmit={() => void submit()} onClose={onClose}>
      {config.fields.map((field) => (
        <FieldInput
          key={field.key}
          field={field}
          value={values[field.key] ?? ""}
          disabled={editing && field.createOnly}
          error={errors.fieldErrors[field.key]}
          onChange={(value) => setValues((current) => ({ ...current, [field.key]: value }))}
          student={students[field.key]}
          onStudent={(student) => setStudents((current) => ({ ...current, [field.key]: student }))}
        />
      ))}
    </FormModal>
  );
}
