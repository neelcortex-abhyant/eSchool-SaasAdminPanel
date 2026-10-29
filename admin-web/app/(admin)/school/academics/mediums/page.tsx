"use client";

import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { AcademicPage } from "@/components/academics/AcademicPage";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useToast } from "@/components/academics/Toasts";
import { useDebounced, useFormErrors, usePagedList } from "@/components/academics/hooks";
import { academicsService, errorMessage, type Medium, type Page } from "@/lib/academics";
import { IconGlobe } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = academicsService("mediums");
const classService = academicsService("classes");

export default function MediumsPage() {
  const [editing, setEditing] = useState<Medium | "new" | null>(null);
  return (
    <AcademicPage
      feature="mediums"
      title="Mediums"
      description="Add the languages your school teaches in. Every class and subject belongs to one medium."
      icon={<IconGlobe width={18} height={18} />}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add medium
        </button>
      }
    >
      <MediumsBody editing={editing} setEditing={setEditing} />
    </AcademicPage>
  );
}

function MediumsBody({ editing, setEditing }: { editing: Medium | "new" | null; setEditing: (value: Medium | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim().toLowerCase());
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<Medium | null>(null);
  const [pending, setPending] = useState(false);

  // A school has a handful of mediums, so search and paging run on the full list here.
  const loader = useCallback(async (): Promise<Page<Medium>> => {
    const rows = (await service.listMediums())
      .filter((row) => !search || row.name.toLowerCase().includes(search))
      .sort((a, b) => a.name.localeCompare(b.name));
    return { items: rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), total: rows.length, page, page_size: PAGE_SIZE };
  }, [page, search]);
  const { data, loading, error, reload } = usePagedList(loader);

  const columns = useMemo<Column<Medium>[]>(() => [{ key: "name", label: "Medium", render: (row) => <strong>{row.name}</strong> }], []);

  async function remove() {
    if (!deleting) return;
    setPending(true);
    try {
      // The server doesn't check this, so a medium in use would leave classes pointing at nothing.
      const classes = await classService.listClasses({ page: 1, pageSize: 1, mediumId: deleting.id });
      if (classes.total > 0) {
        toast("error", `${deleting.name} has ${classes.total} ${classes.total === 1 ? "class" : "classes"}. Move or delete them before deleting the medium.`);
        setDeleting(null);
        return;
      }
      await service.deleteMedium(deleting.id);
      toast("success", `${deleting.name} deleted.`);
      setDeleting(null);
      await reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to delete the medium."));
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search mediums" placeholder="Search mediums" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
      </div>

      <ErrorAlert error={error} onRetry={() => void reload()} />

      {!error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={loading}
            emptyText={search ? "No mediums match this search." : "No mediums yet. Add the language your school teaches in, such as English."}
            actions={(row) => (
              <>
                <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                  Edit
                </button>
                <button className="link-btn" type="button" onClick={() => setDeleting(row)}>
                  Delete
                </button>
              </>
            )}
          />
          <Pagination page={data?.page ?? page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
        </div>
      ) : null}

      {editing ? (
        <MediumForm
          medium={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async (saved, created) => {
            setEditing(null);
            toast("success", created ? `${saved.name} added.` : `${saved.name} updated.`);
            await reload();
          }}
        />
      ) : null}

      {deleting ? (
        <ConfirmDialog
          title={`Delete ${deleting.name}?`}
          body="A medium can be deleted only when no class uses it. Subjects in this medium keep it on their records."
          confirmLabel="Delete"
          tone="danger"
          pending={pending}
          onConfirm={() => void remove()}
          onCancel={() => setDeleting(null)}
        />
      ) : null}
    </>
  );
}

function MediumForm({ medium, onClose, onSaved }: { medium: Medium | null; onClose: () => void; onSaved: (saved: Medium, created: boolean) => Promise<void> }) {
  const [name, setName] = useState(medium?.name ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    if (!name.trim()) {
      errors.setFieldErrors({ name: "Enter a medium name, such as English." });
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      const saved = medium ? await service.updateMedium(medium.id, name) : await service.createMedium(name);
      await onSaved(saved, !medium);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the medium.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={medium ? `Edit ${medium.name}` : "Add medium"}
      error={errors.formError}
      saving={saving}
      submitLabel={medium ? "Save changes" : "Add medium"}
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <TextField id="medium-name" label="Medium name" required span maxLength={255} placeholder="English" value={name} onChange={setName} error={errors.fieldErrors.name} />
    </FormModal>
  );
}
