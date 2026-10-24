"use client";

import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { Chip, FileButton, formatDateTime, TeachingPage } from "@/components/teaching/Frame";
import { MATERIAL_TYPE_LABEL, MATERIALS_LIVE_NOTE, MaterialForm, ReplaceFileForm } from "@/components/teaching/materials";
import { PlacementFilters, usePlacementFilter, useSubjects } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { materialService } from "@/lib/teaching/materials";
import type { Material, MaterialType } from "@/lib/teaching/types";
import { IconBook } from "@/lib/icons";

const PAGE_SIZE = 10;

export default function StudyMaterialsPage() {
  const [editing, setEditing] = useState<Material | "new" | null>(null);
  return (
    <TeachingPage
      module="materials"
      title="Study materials"
      description="Share notes, worksheets, videos and reference links with a section, organised by subject, chapter and topic."
      icon={<IconBook width={18} height={18} />}
      liveNote={MATERIALS_LIVE_NOTE}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add material
        </button>
      }
    >
      <MaterialsBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function MaterialLink({ material }: { material: Material }) {
  if (material.resource_type === "file") {
    return material.file ? <FileButton file={material.file} label="Open" /> : <span className="muted">No file</span>;
  }
  const url = material.external_url ?? "";
  if (!/^https?:\/\//i.test(url)) return <span className="muted">Link not available</span>;
  return (
    <a className="link-btn" href={url} target="_blank" rel="noopener noreferrer">
      Open link ↗
    </a>
  );
}

function MaterialsBody({ editing, setEditing }: { editing: Material | "new" | null; setEditing: (value: Material | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [filter, setFilter] = usePlacementFilter();
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [type, setType] = useState<MaterialType | "">("");
  const subjects = useSubjects(filter.classId ? String(filter.classId) : "");
  const [page, setPage] = useState(1);
  const [replacing, setReplacing] = useState<Material | null>(null);
  const [deleting, setDeleting] = useState<Material | null>(null);
  const [pending, setPending] = useState(false);

  const loader = useCallback(
    () => materialService().list({ page, pageSize: PAGE_SIZE, q: search, sessionYearId: filter.sessionId, classSectionId: filter.sectionId, subjectId, resourceType: type }),
    [page, search, filter.sessionId, filter.sectionId, subjectId, type],
  );
  const list = usePagedList(loader);
  const rows = (list.data?.items ?? []).filter((row) => !filter.classId || filter.sectionId || row.class_id === filter.classId || row.class_id === 0);

  const columns: Column<Material>[] = [
    {
      key: "title",
      label: "Material",
      render: (row) => (
        <div>
          <strong>{row.title}</strong>
          {row.chapter || row.topic ? <div className="muted">{[row.chapter, row.topic].filter(Boolean).join(" · ")}</div> : null}
        </div>
      ),
    },
    { key: "type", label: "Type", render: (row) => <Chip tone={row.resource_type === "file" ? "blue" : "grey"}>{MATERIAL_TYPE_LABEL[row.resource_type]}</Chip> },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}`.trim() },
    { key: "subject", label: "Subject", render: (row) => row.subject_name || "—" },
    { key: "added", label: "Added", render: (row) => formatDateTime(row.created_at) },
    { key: "open", label: "View", render: (row) => <MaterialLink material={row} /> },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search materials" placeholder="Search title, chapter or topic" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setSubjectId(""); setPage(1); }} />
        <select aria-label="Filter by subject" value={subjectId} onChange={(event) => { setSubjectId(event.target.value ? Number(event.target.value) : ""); setPage(1); }}>
          <option value="">{subjects.loading ? "Loading subjects…" : "All subjects"}</option>
          {subjects.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
        <select aria-label="Filter by type" value={type} onChange={(event) => { setType(event.target.value as MaterialType | ""); setPage(1); }}>
          <option value="">All types</option>
          {(Object.keys(MATERIAL_TYPE_LABEL) as MaterialType[]).map((value) => (
            <option key={value} value={value}>
              {MATERIAL_TYPE_LABEL[value]}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={list.loading}
          emptyText={list.error ? "Study materials couldn't be loaded." : search || type || subjectId || filter.sectionId ? "No materials match these filters." : "No study materials yet. Use Add material to share the first one."}
          actions={(row) => (
            <>
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                Edit
              </button>
              {row.resource_type === "file" ? (
                <button className="link-btn" type="button" onClick={() => setReplacing(row)}>
                  Replace file
                </button>
              ) : null}
              <button className="link-btn danger" type="button" onClick={() => setDeleting(row)}>
                Delete
              </button>
            </>
          )}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {editing ? (
        <MaterialForm
          material={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(_, created) => {
            setEditing(null);
            toast("success", created ? "Study material added." : "Study material updated.");
            void list.reload();
          }}
        />
      ) : null}
      {replacing ? (
        <ReplaceFileForm
          material={replacing}
          onClose={() => setReplacing(null)}
          onSaved={() => {
            setReplacing(null);
            toast("success", "File replaced.");
            void list.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          title="Delete this material?"
          body={`“${deleting.title}” will be removed for every student in ${deleting.class_name} ${deleting.section_name}.`}
          confirmLabel="Delete material"
          tone="danger"
          pending={pending}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await materialService().remove(deleting.id);
              toast("success", "Study material deleted.");
              if (rows.length === 1 && page > 1) setPage(page - 1);
              else void list.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete the material."));
            } finally {
              setPending(false);
              setDeleting(null);
            }
          }}
        />
      ) : null}
    </>
  );
}
