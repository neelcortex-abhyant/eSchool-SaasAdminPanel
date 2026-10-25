"use client";

import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { StatusToggle, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { gradingService } from "@/lib/ops/grading";
import { rangeProblems } from "@/lib/ops/grading-math";
import type { GradeRange, GradingScale } from "@/lib/ops/types";
import { IconExam } from "@/lib/icons";

export default function GradingPage() {
  const [editing, setEditing] = useState<GradingScale | "new" | null>(null);
  return (
    <TeachingPage
      module="grading"
      title="Grading scales"
      description="Grade bands by percentage. The default scale grades exam results and report cards."
      icon={<IconExam width={18} height={18} />}
      liveNote={OPS_LIVE_NOTE.grading}
      tabs={[
        { href: "/school/grading", label: "Grading scales" },
        { href: "/school/report-cards", label: "Report cards" },
      ]}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add scale
        </button>
      }
    >
      <ScalesBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function ScalesBody({ editing, setEditing }: { editing: GradingScale | "new" | null; setEditing: (value: GradingScale | "new" | null) => void }) {
  const toast = useToast();
  const state = useOptions(useCallback(() => gradingService().scales(), []));
  const [deleting, setDeleting] = useState<GradingScale | null>(null);
  const [pending, setPending] = useState(false);

  async function makeDefault(scale: GradingScale) {
    try {
      await gradingService().saveScale({ ...scale, is_default: true }, scale.id);
      toast("success", `“${scale.name}” is now the default scale.`);
      void state.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the default scale."));
    }
  }

  return (
    <>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      {state.loading && !state.options.length ? <div className="resource-card"><div className="skeleton" style={{ height: 200 }} /></div> : null}
      {!state.loading && !state.error && state.options.length === 0 ? (
        <div className="resource-card">
          <div className="empty-state">No grading scales yet. Add one to show grades on results and report cards.</div>
        </div>
      ) : null}
      <div className="ops-card-grid">
        {state.options.map((scale) => (
          <section key={scale.id} className="resource-card ops-scale" aria-labelledby={`scale-${scale.id}`}>
            <div className="teach-detail-head">
              <div>
                <h2 id={`scale-${scale.id}`}>
                  {scale.name} {scale.is_default ? <Chip tone="green">Default</Chip> : null} {scale.status === 0 ? <Chip tone="grey">Inactive</Chip> : null}
                </h2>
                {scale.description ? <p className="muted">{scale.description}</p> : null}
              </div>
              <div className="teach-detail-actions">
                {!scale.is_default && scale.status === 1 ? (
                  <button className="link-btn" type="button" onClick={() => void makeDefault(scale)}>
                    Make default
                  </button>
                ) : null}
                <button className="link-btn" type="button" onClick={() => setEditing(scale)}>
                  Edit
                </button>
                <button className="link-btn danger" type="button" disabled={scale.is_default} title={scale.is_default ? "Choose another default first" : undefined} onClick={() => setDeleting(scale)}>
                  Delete
                </button>
              </div>
            </div>
            <div className="table-wrap">
              <table className="data-table ops-range-table">
                <thead>
                  <tr>
                    <th scope="col">Grade</th>
                    <th scope="col">Percentage</th>
                    <th scope="col">Grade point</th>
                    <th scope="col">Remark</th>
                    <th scope="col">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {[...scale.ranges].sort((a, b) => b.min_percent - a.min_percent).map((range) => (
                    <tr key={`${range.grade}-${range.min_percent}`}>
                      <td><strong>{range.grade}</strong></td>
                      <td>{range.min_percent}–{range.max_percent}%</td>
                      <td>{range.grade_point ?? "—"}</td>
                      <td>{range.remark ?? "—"}</td>
                      <td>{range.is_pass ? <Chip tone="green">Pass</Chip> : <Chip tone="red">Fail</Chip>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}
      </div>
      {editing ? (
        <ScaleForm
          scale={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? "Grading scale added." : "Grading scale saved.");
            void state.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          title="Delete this grading scale?"
          body={`“${deleting.name}” and its ${deleting.ranges.length} grade ranges will be removed.`}
          confirmLabel="Delete scale"
          tone="danger"
          pending={pending}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await gradingService().removeScale(deleting.id);
              toast("success", "Grading scale deleted.");
              void state.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete the scale."));
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

type RangeDraft = { grade: string; min: string; max: string; point: string; remark: string; pass: boolean };

const toDraft = (range: GradeRange): RangeDraft => ({
  grade: range.grade,
  min: String(range.min_percent),
  max: String(range.max_percent),
  point: range.grade_point === null ? "" : String(range.grade_point),
  remark: range.remark ?? "",
  pass: range.is_pass,
});

const fromDraft = (draft: RangeDraft): GradeRange => ({
  grade: draft.grade,
  min_percent: draft.min === "" ? Number.NaN : Number(draft.min),
  max_percent: draft.max === "" ? Number.NaN : Number(draft.max),
  grade_point: draft.point === "" ? null : Number(draft.point),
  remark: draft.remark || null,
  is_pass: draft.pass,
});

function ScaleForm({ scale, onClose, onSaved }: { scale: GradingScale | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const [name, setName] = useState(scale?.name ?? "");
  const [description, setDescription] = useState(scale?.description ?? "");
  const [isDefault, setIsDefault] = useState(scale?.is_default ?? false);
  const [active, setActive] = useState(scale ? scale.status === 1 : true);
  const [ranges, setRanges] = useState<RangeDraft[]>(
    scale ? [...scale.ranges].sort((a, b) => b.min_percent - a.min_percent).map(toDraft) : [
      { grade: "A", min: "75", max: "100", point: "", remark: "", pass: true },
      { grade: "B", min: "50", max: "74.99", point: "", remark: "", pass: true },
      { grade: "C", min: "33", max: "49.99", point: "", remark: "", pass: true },
      { grade: "F", min: "0", max: "32.99", point: "", remark: "", pass: false },
    ],
  );
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  function setRange(index: number, patch: Partial<RangeDraft>) {
    setRanges((list) => list.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  async function submit() {
    const parsed = ranges.map(fromDraft);
    const problems = { ...rangeProblems(parsed) };
    if (!name.trim()) problems.name = "Enter a name for the scale.";
    if (Object.keys(problems).length) {
      errors.setFieldErrors(problems);
      errors.setFormError(problems.ranges ?? "");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await gradingService().saveScale({ name, description: description || null, is_default: isDefault, status: active ? 1 : 0, ranges: parsed }, scale?.id);
      onSaved(!scale);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the grading scale.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={scale ? "Edit grading scale" : "Add grading scale"} description="Ranges are inclusive and must cover 0–100% without overlapping." error={errors.formError} saving={saving} submitLabel="Save scale" wide onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="gs-name" label="Name" required maxLength={80} value={name} onChange={setName} error={errors.fieldErrors.name} />
      <TextField id="gs-description" label="Description" maxLength={255} value={description} onChange={setDescription} />
      <div className="form-field field-span ops-check-row">
        <StatusToggle id="gs-default" checked={isDefault} onChange={setIsDefault} label="Default scale for results and report cards" />
        <StatusToggle id="gs-active" checked={active} onChange={setActive} label="Active" />
      </div>
      <fieldset className="form-field field-span ops-ranges">
        <legend>Grade ranges *</legend>
        <div className="ops-range-row ops-range-head" aria-hidden>
          <span>Grade</span>
          <span>From %</span>
          <span>To %</span>
          <span>Point</span>
          <span>Remark</span>
          <span>Pass</span>
          <span />
        </div>
        {ranges.map((range, index) => (
          <div key={index} className="ops-range-row">
            <input aria-label={`Grade ${index + 1}`} maxLength={4} value={range.grade} className={errors.fieldErrors[`ranges.${index}.grade`] ? "invalid" : undefined} onChange={(event) => setRange(index, { grade: event.target.value })} />
            <input aria-label={`From percent ${index + 1}`} type="number" min={0} max={100} step="0.01" value={range.min} className={errors.fieldErrors[`ranges.${index}.min_percent`] ? "invalid" : undefined} onChange={(event) => setRange(index, { min: event.target.value })} />
            <input aria-label={`To percent ${index + 1}`} type="number" min={0} max={100} step="0.01" value={range.max} onChange={(event) => setRange(index, { max: event.target.value })} />
            <input aria-label={`Grade point ${index + 1}`} type="number" min={0} step="0.1" value={range.point} onChange={(event) => setRange(index, { point: event.target.value })} />
            <input aria-label={`Remark ${index + 1}`} maxLength={60} value={range.remark} onChange={(event) => setRange(index, { remark: event.target.value })} />
            <input aria-label={`Grade ${index + 1} passes`} type="checkbox" checked={range.pass} onChange={(event) => setRange(index, { pass: event.target.checked })} />
            <button className="link-btn danger" type="button" disabled={ranges.length <= 1} onClick={() => setRanges((list) => list.filter((_, i) => i !== index))}>
              Remove<span className="acad-sr"> range {index + 1}</span>
            </button>
            {errors.fieldErrors[`ranges.${index}.grade`] || errors.fieldErrors[`ranges.${index}.min_percent`] ? (
              <p className="field-error ops-range-error">{errors.fieldErrors[`ranges.${index}.grade`] || errors.fieldErrors[`ranges.${index}.min_percent`]}</p>
            ) : null}
          </div>
        ))}
        <button className="link-btn" type="button" disabled={ranges.length >= 15} onClick={() => setRanges((list) => [...list, { grade: "", min: "", max: "", point: "", remark: "", pass: true }])}>
          + Add range
        </button>
      </fieldset>
    </FormModal>
  );
}
