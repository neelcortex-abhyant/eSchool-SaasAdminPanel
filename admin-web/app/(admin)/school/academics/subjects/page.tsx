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
import {
  academicsService,
  academicsSupport,
  listAll,
  toId,
  type Medium,
  type SchoolClass,
  type Subject,
  type SubjectInput,
  type SubjectKind,
  type SubjectType,
} from "@/lib/academics";
import { IconExam } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = academicsService("subjects");
const classService = academicsService("classes");
const supports = academicsSupport("subjects");

export default function SubjectsPage() {
  const [editing, setEditing] = useState<Subject | "new" | null>(null);
  return (
    <AcademicPage
      feature="subjects"
      title="Subjects"
      description="Create subjects and choose which classes study them as compulsory or elective."
      icon={<IconExam width={18} height={18} />}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add subject
        </button>
      }
    >
      <SubjectsBody editing={editing} setEditing={setEditing} />
    </AcademicPage>
  );
}

function SubjectsBody({ editing, setEditing }: { editing: Subject | "new" | null; setEditing: (value: Subject | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [classId, setClassId] = useState<number | "">("");
  const [kind, setKind] = useState<"" | SubjectKind>("");
  const [type, setType] = useState<"" | SubjectType>("");
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [page, setPage] = useState(1);

  const classes = useOptions(useCallback(() => listAll((p) => classService.listClasses({ page: p, pageSize: 50 })), []));
  const mediums = useOptions(useCallback(() => classService.listMediums(), []));
  const loader = useCallback(
    () => service.listSubjects({ page, pageSize: PAGE_SIZE, q: search, status, classId, kind, type }),
    [page, search, status, classId, kind, type],
  );
  const { data, loading, error, reload } = usePagedList(loader);
  const filtered = Boolean(search || status || classId || kind || type);

  const columns = useMemo<Column<Subject>[]>(
    () => [
      { key: "name", label: "Subject", render: (row) => <strong>{row.name}</strong> },
      { key: "code", label: "Code", render: (row) => row.code || "—" },
      { key: "type", label: "Type", render: (row) => row.type },
      {
        key: "classes",
        label: "Classes",
        render: (row) =>
          row.classes.length ? (
            <ul className="acad-chips">
              {row.classes.map((link) => (
                <li key={link.class_id} className={link.type === "Elective" ? "is-elective" : undefined} title={link.type}>
                  {link.class_name}
                  {link.type === "Elective" ? " · Elective" : ""}
                </li>
              ))}
            </ul>
          ) : (
            <span className="muted">Not mapped</span>
          ),
      },
      ...(supports.status ? [{ key: "status", label: "Status", render: (row: Subject) => <StatusBadge active={row.status === 1} /> }] : []),
    ],
    [],
  );

  function resetFilters() {
    setSearchInput("");
    setClassId("");
    setKind("");
    setType("");
    setStatus("");
    setPage(1);
  }

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search by name or code" placeholder="Search by name or code" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <select aria-label="Filter by class" value={classId} onChange={(event) => { setClassId(toId(event.target.value)); setPage(1); }}>
          <option value="">All classes</option>
          {classes.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name} · {row.medium_name}
            </option>
          ))}
        </select>
        {supports.subjectKind ? (
          <select aria-label="Filter by compulsory or elective" value={kind} onChange={(event) => { setKind(event.target.value as "" | SubjectKind); setPage(1); }}>
            <option value="">Compulsory and elective</option>
            <option value="Compulsory">Compulsory</option>
            <option value="Elective">Elective</option>
          </select>
        ) : null}
        <select aria-label="Filter by type" value={type} onChange={(event) => { setType(event.target.value as "" | SubjectType); setPage(1); }}>
          <option value="">Theory and practical</option>
          <option value="Theory">Theory</option>
          <option value="Practical">Practical</option>
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
            emptyText={filtered ? "No subjects match these filters." : "No subjects yet. Add a subject and map it to classes."}
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
        <SubjectForm
          subject={editing === "new" ? null : editing}
          classes={classes.options}
          mediums={mediums.options}
          lookupsLoading={classes.loading || mediums.loading}
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

function SubjectForm({
  subject,
  classes,
  mediums,
  lookupsLoading,
  onClose,
  onSaved,
}: {
  subject: Subject | null;
  classes: SchoolClass[];
  mediums: Medium[];
  lookupsLoading: boolean;
  onClose: () => void;
  onSaved: (saved: Subject, created: boolean) => Promise<void>;
}) {
  const [name, setName] = useState(subject?.name ?? "");
  const [code, setCode] = useState(subject?.code ?? "");
  const [type, setType] = useState<SubjectType>(subject?.type ?? "Theory");
  const [mediumId, setMediumId] = useState(subject ? String(subject.medium_id) : mediums.length === 1 ? String(mediums[0].id) : "");
  const [addedMediums, setAddedMediums] = useState<Medium[]>([]);
  const mediumChoices = [...mediums, ...addedMediums.filter((added) => !mediums.some((row) => row.id === added.id))];
  const [links, setLinks] = useState<Map<number, SubjectKind>>(() => new Map((subject?.classes ?? []).map((link) => [link.class_id, link.type])));
  const [active, setActive] = useState(subject ? subject.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const errors = useFormErrors();

  const mediumClasses = classes.filter((row) => String(row.medium_id) === mediumId && (row.status === 1 || links.has(row.id)));

  function changeMedium(value: string) {
    setMediumId(value);
    // Classes from another medium can't take this subject.
    setLinks((current) => new Map([...current].filter(([id]) => classes.some((row) => row.id === id && String(row.medium_id) === value))));
  }

  function toggleClass(id: number, on: boolean) {
    setLinks((current) => {
      const next = new Map(current);
      if (on) next.set(id, "Compulsory");
      else next.delete(id);
      return next;
    });
  }

  function setKind(id: number, kind: SubjectKind) {
    setLinks((current) => new Map(current).set(id, kind));
  }

  function body(): SubjectInput {
    return {
      name: name.trim(),
      code: code.trim().toUpperCase(),
      type,
      medium_id: Number(mediumId),
      classes: [...links].map(([class_id, kind]) => ({ class_id, type: kind })),
      status: active ? 1 : 0,
    };
  }

  function check() {
    const invalid: Record<string, string> = {};
    if (!name.trim()) invalid.name = "Enter a subject name.";
    if (!mediumId) invalid.medium_id = "Choose a medium.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    if (subject?.status === 1 && !active) setConfirmDeactivate(true);
    else void save();
  }

  async function save() {
    setConfirmDeactivate(false);
    errors.clear();
    setSaving(true);
    try {
      const saved = subject ? await service.updateSubject(subject.id, body()) : await service.createSubject(body());
      await onSaved(saved, !subject);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the subject.");
      setSaving(false);
    }
  }

  return (
    <>
      <FormModal
        title={subject ? `Edit ${subject.name}` : "Add subject"}
        error={errors.formError}
        saving={saving}
        submitLabel={subject ? "Save changes" : "Add subject"}
        wide
        onSubmit={check}
        onClose={onClose}
      >
        <TextField id="subject-name" label="Subject name" required maxLength={255} placeholder="Mathematics" value={name} onChange={setName} error={errors.fieldErrors.name} />
        <TextField id="subject-code" label="Subject code" maxLength={64} placeholder="MATH" value={code} onChange={setCode} error={errors.fieldErrors.code} hint="Optional. Codes are unique in your school." />
        <SelectField
          id="subject-type"
          label="Type"
          required
          value={type}
          onChange={(value) => setType(value as SubjectType)}
          options={[
            { value: "Theory", label: "Theory" },
            { value: "Practical", label: "Practical" },
          ]}
          error={errors.fieldErrors.type}
        />
        <SelectField
          id="subject-medium"
          label="Medium"
          required
          placeholder="Choose a medium"
          loading={lookupsLoading}
          value={mediumId}
          onChange={changeMedium}
          options={mediumChoices.map((medium) => ({ value: String(medium.id), label: medium.name }))}
          error={errors.fieldErrors.medium_id}
        />
        {!lookupsLoading ? (
          <div className="form-field field-span">
            <AddMedium
              service={classService}
              empty={mediumChoices.length === 0}
              onAdded={(medium) => {
                setAddedMediums((current) => [...current, medium]);
                changeMedium(String(medium.id));
              }}
            />
          </div>
        ) : null}
        <fieldset className="form-field field-span acad-fieldset">
          <legend>Classes</legend>
          {!mediumId ? (
            <p className="field-hint">Choose a medium to see its classes.</p>
          ) : mediumClasses.length === 0 ? (
            <p className="field-hint">No active classes in this medium yet.</p>
          ) : (
            <ul className="acad-class-picker">
              {mediumClasses.map((row) => {
                const kind = links.get(row.id);
                return (
                  <li key={row.id}>
                    <label className="acad-check">
                      <input type="checkbox" checked={kind !== undefined} onChange={(event) => toggleClass(row.id, event.target.checked)} />
                      <span>{row.name}</span>
                    </label>
                    {supports.subjectKind ? (
                      <select aria-label={`${row.name}: compulsory or elective`} value={kind ?? "Compulsory"} disabled={kind === undefined} onChange={(event) => setKind(row.id, event.target.value as SubjectKind)}>
                        <option value="Compulsory">Compulsory</option>
                        <option value="Elective">Elective</option>
                      </select>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
          {errors.fieldErrors.classes ? <p className="field-error">{errors.fieldErrors.classes}</p> : null}
          {!supports.subjectKind ? <p className="field-hint">Every class takes this subject as compulsory. The server doesn&apos;t store elective subjects yet.</p> : null}
        </fieldset>
        {supports.status ? (
          <div className="form-field field-span">
            <StatusToggle id="subject-active" checked={active} onChange={setActive} />
          </div>
        ) : null}
      </FormModal>
      {confirmDeactivate ? (
        <ConfirmDialog
          title={`Mark ${subject?.name} inactive?`}
          body="Inactive subjects stay in records but can't get new teacher assignments."
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
