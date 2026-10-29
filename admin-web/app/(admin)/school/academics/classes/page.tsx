"use client";

import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { AcademicPage } from "@/components/academics/AcademicPage";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, StatusToggle, TextField } from "@/components/academics/Fields";
import { AddMedium } from "@/components/academics/AddMedium";
import { FormModal } from "@/components/academics/FormModal";
import { StatusBadge } from "@/components/academics/StatusBadge";
import { useToast } from "@/components/academics/Toasts";
import { useDebounced, useFormErrors, useOptions, usePagedList } from "@/components/academics/hooks";
import { academicsService, academicsSupport, listAll, toId, type AcademicSession, type ClassInput, type Medium, type SchoolClass } from "@/lib/academics";
import { IconClasses } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = academicsService("classes");
const sessionService = academicsService("sessions");
const supports = academicsSupport("classes");

export default function ClassesPage() {
  const [editing, setEditing] = useState<SchoolClass | "new" | null>(null);
  return (
    <AcademicPage
      feature="classes"
      title="Classes"
      description="Add the classes your school runs and the session each one belongs to."
      icon={<IconClasses width={18} height={18} />}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add class
        </button>
      }
    >
      <ClassesBody editing={editing} setEditing={setEditing} />
    </AcademicPage>
  );
}

function ClassesBody({ editing, setEditing }: { editing: SchoolClass | "new" | null; setEditing: (value: SchoolClass | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [sessionId, setSessionId] = useState<number | "">("");
  const [mediumId, setMediumId] = useState<number | "">("");
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [page, setPage] = useState(1);

  const sessions = useOptions(useCallback(() => listAll((p) => sessionService.listSessions({ page: p, pageSize: 50 })), []));
  const mediums = useOptions(useCallback(() => service.listMediums(), []));

  const loader = useCallback(
    () => service.listClasses({ page, pageSize: PAGE_SIZE, q: search, status, sessionYearId: sessionId, mediumId }),
    [page, search, status, sessionId, mediumId],
  );
  const { data, loading, error, reload } = usePagedList(loader);
  const filtered = Boolean(search || status || sessionId || mediumId);

  const columns = useMemo<Column<SchoolClass>[]>(
    () => [
      { key: "name", label: "Class", render: (row) => <strong>{row.name}</strong> },
      { key: "medium", label: "Medium", render: (row) => row.medium_name || "—" },
      ...(supports.classSession
        ? [{ key: "session", label: "Session", render: (row: SchoolClass) => row.session_name || <span className="muted">All sessions</span> }]
        : []),
      ...(supports.status ? [{ key: "status", label: "Status", render: (row: SchoolClass) => <StatusBadge active={row.status === 1} /> }] : []),
    ],
    [],
  );

  function resetFilters() {
    setSearchInput("");
    setSessionId("");
    setMediumId("");
    setStatus("");
    setPage(1);
  }

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search classes" placeholder="Search classes" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        {supports.classSession ? (
          <select aria-label="Filter by session" value={sessionId} onChange={(event) => { setSessionId(toId(event.target.value)); setPage(1); }}>
            <option value="">All sessions</option>
            {sessions.options.map((session) => (
              <option key={session.id} value={session.id}>
                {session.name}
                {session.is_active ? " (active)" : ""}
              </option>
            ))}
          </select>
        ) : null}
        <select aria-label="Filter by medium" value={mediumId} onChange={(event) => { setMediumId(toId(event.target.value)); setPage(1); }}>
          <option value="">All mediums</option>
          {mediums.options.map((medium) => (
            <option key={medium.id} value={medium.id}>
              {medium.name}
            </option>
          ))}
        </select>
        {supports.status ? (
          <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as "" | "0" | "1"); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="1">Active</option>
            <option value="0">Inactive</option>
          </select>
        ) : null}
        {filtered ? (
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={resetFilters}>
            Reset
          </button>
        ) : null}
      </div>

      <ErrorAlert error={error} onRetry={() => void reload()} />

      {!error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={loading}
            emptyText={filtered ? "No classes match these filters." : "No classes yet. Add your first class to get started."}
            actions={(row) => (
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                Edit
              </button>
            )}
          />
          <Pagination page={data?.page ?? page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
        </div>
      ) : null}

      {editing ? (
        <ClassForm
          schoolClass={editing === "new" ? null : editing}
          sessions={sessions.options}
          mediums={mediums.options}
          lookupsLoading={sessions.loading || mediums.loading}
          onClose={() => setEditing(null)}
          onSaved={async (saved, created) => {
            setEditing(null);
            toast("success", created ? `${saved.name} added.` : `${saved.name} updated.`);
            await reload();
          }}
        />
      ) : null}
    </>
  );
}

function ClassForm({
  schoolClass,
  sessions,
  mediums,
  lookupsLoading,
  onClose,
  onSaved,
}: {
  schoolClass: SchoolClass | null;
  sessions: AcademicSession[];
  mediums: Medium[];
  lookupsLoading: boolean;
  onClose: () => void;
  onSaved: (saved: SchoolClass, created: boolean) => Promise<void>;
}) {
  const [name, setName] = useState(schoolClass?.name ?? "");
  const [mediumId, setMediumId] = useState(schoolClass ? String(schoolClass.medium_id) : mediums.length === 1 ? String(mediums[0].id) : "");
  const [addedMediums, setAddedMediums] = useState<Medium[]>([]);
  const mediumChoices = [...mediums, ...addedMediums.filter((added) => !mediums.some((row) => row.id === added.id))];
  const [sessionId, setSessionId] = useState(schoolClass?.session_year_id ? String(schoolClass.session_year_id) : "");
  const [active, setActive] = useState(schoolClass ? schoolClass.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const errors = useFormErrors();

  function body(): ClassInput {
    return { name: name.trim(), medium_id: Number(mediumId), session_year_id: sessionId ? Number(sessionId) : null, status: active ? 1 : 0 };
  }

  function check() {
    const invalid: Record<string, string> = {};
    if (!name.trim()) invalid.name = "Enter a class name.";
    if (!mediumId) invalid.medium_id = "Choose a medium.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    if (schoolClass?.status === 1 && !active) setConfirmDeactivate(true);
    else void save();
  }

  async function save() {
    setConfirmDeactivate(false);
    errors.clear();
    setSaving(true);
    try {
      const saved = schoolClass ? await service.updateClass(schoolClass.id, body()) : await service.createClass(body());
      await onSaved(saved, !schoolClass);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the class.");
      setSaving(false);
    }
  }

  return (
    <>
      <FormModal
        title={schoolClass ? `Edit ${schoolClass.name}` : "Add class"}
        error={errors.formError}
        saving={saving}
        submitLabel={schoolClass ? "Save changes" : "Add class"}
        onSubmit={check}
        onClose={onClose}
      >
        <TextField id="class-name" label="Class name" required span maxLength={255} placeholder="Class 5" value={name} onChange={setName} error={errors.fieldErrors.name} />
        <SelectField
          id="class-medium"
          label="Medium"
          required
          placeholder="Choose a medium"
          loading={lookupsLoading}
          value={mediumId}
          onChange={setMediumId}
          options={mediumChoices.map((medium) => ({ value: String(medium.id), label: medium.name }))}
          error={errors.fieldErrors.medium_id}
        />
        {!lookupsLoading ? (
          <div className="form-field field-span">
            <AddMedium
              service={service}
              empty={mediumChoices.length === 0}
              onAdded={(medium) => {
                setAddedMediums((current) => [...current, medium]);
                setMediumId(String(medium.id));
              }}
            />
          </div>
        ) : null}
        {supports.classSession ? (
        <SelectField
          id="class-session"
          label="Academic session"
          placeholder="All sessions"
          loading={lookupsLoading}
          value={sessionId}
          onChange={setSessionId}
          options={sessions.map((session) => ({ value: String(session.id), label: `${session.name}${session.is_active ? " (active)" : ""}` }))}
          error={errors.fieldErrors.session_year_id}
          hint="Leave as All sessions for a class that runs every year."
        />
        ) : null}
        {supports.status ? (
          <div className="form-field field-span">
            <StatusToggle id="class-active" checked={active} onChange={setActive} />
          </div>
        ) : null}
        {!supports.classSession || !supports.status ? (
          <p className="form-field field-span muted">Classes run in every session and stay active. The server doesn&apos;t store a session or status for classes yet.</p>
        ) : null}
      </FormModal>
      {confirmDeactivate ? (
        <ConfirmDialog
          title={`Mark ${schoolClass?.name} inactive?`}
          body="Inactive classes stay in records but can't get new sections or teacher assignments."
          confirmLabel="Mark inactive"
          tone="danger"
          pending={saving}
          onConfirm={() => void save()}
          onCancel={() => setConfirmDeactivate(false)}
        />
      ) : null}
    </>
  );
}
