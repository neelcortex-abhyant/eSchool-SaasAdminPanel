"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ConcessionForm, FEE_TABS, StudentPicker, rupees } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { isOpsLive } from "@/lib/ops/mode";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import type { StudentRow } from "@/lib/people";
import { feeService } from "@/lib/ops/fees";
import { concessionValue } from "@/lib/ops/fees-math";
import type { Concession, FeeAssignment, FeeStructure } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";

export default function FeeAssignmentsPage() {
  return (
    <TeachingPage
      module="fees"
      title="Assignments & concessions"
      description="Students pay their class's fee structures automatically. Add extra fees (like transport) for individual students, and record discounts or exemptions."
      icon={<IconFees width={18} height={18} />}
      tabs={FEE_TABS}
      liveNote={OPS_LIVE_NOTE.fees}
    >
      <Suspense fallback={<div className="skeleton" style={{ height: 200 }} />}>
        <AssignmentsBody />
      </Suspense>
    </TeachingPage>
  );
}

function AssignmentsBody() {
  const toast = useToast();
  const params = useSearchParams();
  const [structureId, setStructureId] = useState<number | "">(() => Number(params.get("structure")) || "");
  const structures = useOptions(useCallback(() => feeService().structures({ pageSize: 50, status: "1" }).then((page) => page.items), []));
  const assignments = useOptions(useCallback(() => feeService().assignments(structureId || undefined), [structureId]));
  const concessions = useOptions(useCallback(() => feeService().concessions(structureId || undefined), [structureId]));
  const [assigning, setAssigning] = useState(false);
  const [editing, setEditing] = useState<Concession | "new" | null>(null);
  const [removing, setRemoving] = useState<{ kind: "assignment"; row: FeeAssignment } | { kind: "concession"; row: Concession } | null>(null);
  const [pending, setPending] = useState(false);
  const byId = useMemo(() => new Map(structures.options.map((row) => [row.id, row])), [structures.options]);

  const assignmentColumns: Column<FeeAssignment>[] = [
    { key: "student", label: "Student", render: (row) => <strong>{row.student_name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no },
    { key: "structure", label: "Fee structure", render: (row) => row.structure_name },
    { key: "amount", label: "Amount", render: (row) => rupees(byId.get(row.structure_id)?.total ?? 0) },
  ];
  const concessionColumns: Column<Concession>[] = [
    { key: "student", label: "Student", render: (row) => <strong>{row.student_name}</strong> },
    { key: "structure", label: "Fee structure", render: (row) => row.structure_name },
    {
      key: "value",
      label: "Concession",
      render: (row) =>
        row.kind === "percent" && row.value >= 100 ? <Chip tone="blue">Full exemption</Chip> : row.kind === "percent" ? `${row.value}%` : rupees(row.value),
    },
    { key: "worth", label: "Worth", render: (row) => rupees(concessionValue(byId.get(row.structure_id)?.total ?? 0, row)) },
    { key: "reason", label: "Reason", render: (row) => row.reason },
  ];

  return (
    <>
      <div className="school-filters">
        <select aria-label="Fee structure" value={structureId} onChange={(event) => setStructureId(event.target.value ? Number(event.target.value) : "")}>
          <option value="">{structures.loading ? "Loading…" : "All fee structures"}</option>
          {structures.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={structures.error ?? assignments.error ?? concessions.error} onRetry={() => { void assignments.reload(); void concessions.reload(); }} />
      <section className="resource-card" aria-labelledby="extra-title">
        <div className="teach-detail-head">
          <h2 id="extra-title" className="teach-section-title">Extra fees for individual students</h2>
          <button className="btn-pill btn-pill-green" type="button" onClick={() => setAssigning(true)}>
            Assign to a student
          </button>
        </div>
        <DataTable
          columns={assignmentColumns}
          rows={assignments.options}
          loading={assignments.loading}
          emptyText="No individual assignments. Class fee structures already apply to every student in the class."
          actions={(row) => (
            <button className="link-btn danger" type="button" onClick={() => setRemoving({ kind: "assignment", row })}>
              Remove
            </button>
          )}
        />
      </section>
      <section className="resource-card" aria-labelledby="concession-title">
        <div className="teach-detail-head">
          <h2 id="concession-title" className="teach-section-title">Concessions, discounts and exemptions</h2>
          <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
            Add concession
          </button>
        </div>
        <DataTable
          columns={concessionColumns}
          rows={concessions.options}
          loading={concessions.loading}
          emptyText="No concessions yet."
          actions={(row) => (
            <>
              {isOpsLive("fees") ? null : (
                <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                  Edit
                </button>
              )}
              <button className="link-btn danger" type="button" onClick={() => setRemoving({ kind: "concession", row })}>
                Remove
              </button>
            </>
          )}
        />
      </section>
      {assigning ? (
        <AssignForm
          structures={structures.options}
          initialStructure={structureId}
          onClose={() => setAssigning(false)}
          onSaved={() => {
            setAssigning(false);
            toast("success", "Fees assigned to the student.");
            void assignments.reload();
          }}
        />
      ) : null}
      {editing ? (
        <ConcessionForm
          structures={structures.options}
          concession={
            editing === "new"
              ? null
              : { id: editing.id, student: { id: editing.student_id, name: editing.student_name } as StudentRow, structure_id: editing.structure_id, kind: editing.kind, value: editing.value, reason: editing.reason }
          }
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            toast("success", "Concession saved. The student's balance now reflects it.");
            void concessions.reload();
          }}
        />
      ) : null}
      {removing ? (
        <ConfirmDialog
          title={removing.kind === "assignment" ? "Remove these fees from the student?" : "Remove this concession?"}
          body={`${removing.row.student_name} · ${removing.row.structure_name}`}
          confirmLabel="Remove"
          tone="danger"
          pending={pending}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              if (removing.kind === "assignment") await feeService().unassign(removing.row.id);
              else await feeService().removeConcession(removing.row.id);
              toast("success", "Removed.");
              void assignments.reload();
              void concessions.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to remove it."));
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

function AssignForm({ structures, initialStructure, onClose, onSaved }: { structures: FeeStructure[]; initialStructure: number | ""; onClose: () => void; onSaved: () => void }) {
  const [student, setStudent] = useState<StudentRow | null>(null);
  const [structureId, setStructureId] = useState(initialStructure ? String(initialStructure) : "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!student) invalid.student_id = "Choose a student.";
    if (!structureId) invalid.structure_id = "Choose a fee structure.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await feeService().assign(Number(structureId), (student as StudentRow).id);
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to assign the fees.");
      setSaving(false);
    }
  }

  return (
    <FormModal title="Assign fees to a student" description="For fees outside the student's class structure, like transport." error={errors.formError} saving={saving} submitLabel="Assign" wide onSubmit={() => void submit()} onClose={onClose}>
      <StudentPicker id="as-student" value={student} onPick={setStudent} error={errors.fieldErrors.student_id} />
      <SelectField id="as-structure" label="Fee structure" required placeholder="Choose a structure" value={structureId} onChange={setStructureId} options={structures.map((row) => ({ value: String(row.id), label: `${row.name} (${rupees(row.total)})` }))} error={errors.fieldErrors.structure_id} />
    </FormModal>
  );
}
