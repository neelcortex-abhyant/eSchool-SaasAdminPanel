"use client";

import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { AcademicPage } from "@/components/academics/AcademicPage";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, StatusToggle, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { StatusBadge } from "@/components/academics/StatusBadge";
import { useToast } from "@/components/academics/Toasts";
import { useDebounced, useFormErrors, useOptions, usePagedList } from "@/components/academics/hooks";
import { academicsService, academicsSupport, listAll, toId, type ClassSection, type SchoolClass } from "@/lib/academics";
import { IconBook } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = academicsService("sections");
const classService = academicsService("classes");
const supports = academicsSupport("sections");

type Editing = { section: ClassSection | null; classId: number | "" } | null;

export default function SectionsPage() {
  const [editing, setEditing] = useState<Editing>(null);
  const [classId, setClassId] = useState<number | "">("");
  return (
    <AcademicPage
      feature="sections"
      title="Sections"
      description="Split each class into sections, such as Class 5 A and Class 5 B."
      icon={<IconBook width={18} height={18} />}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing({ section: null, classId })}>
          Add section
        </button>
      }
    >
      <SectionsBody editing={editing} setEditing={setEditing} classId={classId} setClassId={setClassId} />
    </AcademicPage>
  );
}

function classLabel(row: SchoolClass) {
  return `${row.name}${row.medium_name ? ` · ${row.medium_name}` : ""}${row.status === 1 ? "" : " (inactive)"}`;
}

function SectionsBody({
  editing,
  setEditing,
  classId,
  setClassId,
}: {
  editing: Editing;
  setEditing: (value: Editing) => void;
  classId: number | "";
  setClassId: (value: number | "") => void;
}) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [page, setPage] = useState(1);

  const classes = useOptions(useCallback(() => listAll((p) => classService.listClasses({ page: p, pageSize: 50 })), []));
  const loader = useCallback(() => service.listSections({ page, pageSize: PAGE_SIZE, q: search, status, classId }), [page, search, status, classId]);
  const { data, loading, error, reload } = usePagedList(loader);
  const filtered = Boolean(search || status || classId);

  const columns = useMemo<Column<ClassSection>[]>(
    () => [
      { key: "section", label: "Section", render: (row) => <strong>{row.section_name}</strong> },
      { key: "class", label: "Class", render: (row) => row.class_name },
      ...(supports.status ? [{ key: "status", label: "Status", render: (row: ClassSection) => <StatusBadge active={row.status === 1} /> }] : []),
    ],
    [],
  );

  return (
    <>
      <div className="school-filters">
        <select aria-label="Filter by class" value={classId} onChange={(event) => { setClassId(toId(event.target.value)); setPage(1); }}>
          <option value="">{classes.loading ? "Loading classes…" : "All classes"}</option>
          {classes.options.map((row) => (
            <option key={row.id} value={row.id}>
              {classLabel(row)}
            </option>
          ))}
        </select>
        <input type="search" aria-label="Search sections" placeholder="Search sections" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        {supports.status ? (
          <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as "" | "0" | "1"); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="1">Active</option>
            <option value="0">Inactive</option>
          </select>
        ) : null}
      </div>

      <ErrorAlert error={error ?? classes.error} onRetry={() => { void reload(); void classes.reload(); }} />

      {!error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={loading}
            emptyText={classId ? "This class has no sections yet." : filtered ? "No sections match these filters." : "No sections yet. Add a section to a class to get started."}
            actions={(row) => (
              <button className="link-btn" type="button" onClick={() => setEditing({ section: row, classId: row.class_id })}>
                Edit
              </button>
            )}
          />
          <Pagination page={data?.page ?? page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
        </div>
      ) : null}

      {editing ? (
        <SectionForm
          section={editing.section}
          initialClassId={editing.classId}
          classes={classes.options}
          classesLoading={classes.loading}
          onClose={() => setEditing(null)}
          onSaved={async (saved, created) => {
            setEditing(null);
            toast("success", created ? `Section ${saved.section_name} added to ${saved.class_name}.` : `${saved.class_name} ${saved.section_name} updated.`);
            await reload();
          }}
        />
      ) : null}
    </>
  );
}

function SectionForm({
  section,
  initialClassId,
  classes,
  classesLoading,
  onClose,
  onSaved,
}: {
  section: ClassSection | null;
  initialClassId: number | "";
  classes: SchoolClass[];
  classesLoading: boolean;
  onClose: () => void;
  onSaved: (saved: ClassSection, created: boolean) => Promise<void>;
}) {
  const [classId, setClassId] = useState(String(initialClassId));
  const [name, setName] = useState(section?.section_name ?? "");
  const [active, setActive] = useState(section ? section.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const errors = useFormErrors();
  // A new section can only go to an active class. An existing one keeps its class shown even if inactive.
  const choices = classes.filter((row) => row.status === 1 || row.id === section?.class_id);

  function check() {
    const invalid: Record<string, string> = {};
    if (!classId) invalid.class_id = "Choose a class.";
    if (!name.trim()) invalid.section_name = "Enter a section name, such as A.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    if (section?.status === 1 && !active) setConfirmDeactivate(true);
    else void save();
  }

  async function save() {
    setConfirmDeactivate(false);
    errors.clear();
    setSaving(true);
    const body = { class_id: Number(classId), section_name: name.trim(), status: (active ? 1 : 0) as 0 | 1 };
    try {
      const saved = section ? await service.updateSection(section.id, body) : await service.createSection(body);
      await onSaved(saved, !section);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the section.");
      setSaving(false);
    }
  }

  return (
    <>
      <FormModal
        title={section ? `Edit ${section.class_name} ${section.section_name}` : "Add section"}
        description="Section names must be unique within a class."
        error={errors.formError}
        saving={saving}
        submitLabel={section ? "Save changes" : "Add section"}
        onSubmit={check}
        onClose={onClose}
      >
        <SelectField
          id="section-class"
          label="Class"
          required
          placeholder="Choose a class"
          loading={classesLoading}
          disabled={Boolean(section)}
          value={classId}
          onChange={setClassId}
          options={choices.map((row) => ({ value: String(row.id), label: classLabel(row) }))}
          error={errors.fieldErrors.class_id}
          hint={section ? "A section stays with the class it was created in." : undefined}
        />
        <TextField id="section-name" label="Section name" required maxLength={32} placeholder="A" value={name} onChange={setName} error={errors.fieldErrors.section_name} />
        {supports.status ? (
          <div className="form-field field-span">
            <StatusToggle id="section-active" checked={active} onChange={setActive} />
          </div>
        ) : (
          <p className="form-field field-span muted">Sections stay active. The server doesn&apos;t store a status for sections yet.</p>
        )}
      </FormModal>
      {confirmDeactivate ? (
        <ConfirmDialog
          title={`Mark ${section?.class_name} ${section?.section_name} inactive?`}
          body="Inactive sections stay in records but can't get new teacher assignments."
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
