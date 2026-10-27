"use client";

import { useCallback, useMemo, useState } from "react";
import { SelectField, StatusToggle, TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useDebounced, useFormErrors, useOptions } from "@/components/academics/hooks";
import { classLabel, sessionLabel, useClassesFor, useSessions } from "@/components/people/academicOptions";
import { Chip, type ChipTone } from "@/components/teaching/Frame";
import { useCurrentSessionId } from "@/components/teaching/Pickers";
import { peopleService, type StudentRow } from "@/lib/people";
import { feeService, structureFormProblems } from "@/lib/ops/fees";
import { paise, splitEvenly } from "@/lib/ops/fees-math";
import { isOpsLive } from "@/lib/ops/mode";
import { FEE_CATEGORIES, type ConcessionKind, type FeeStructure, type FeeType, type FeeTypeInput, type InstallmentInput, type PaymentStatus } from "@/lib/ops/types";

export const FEE_TABS = [
  { href: "/school/fees/collect", label: "Collect fees" },
  { href: "/school/fees/outstanding", label: "Outstanding" },
  { href: "/school/fees/payments", label: "Payments" },
  { href: "/school/fees/structures", label: "Fee structures" },
  { href: "/school/fees/assignments", label: "Assignments & concessions" },
  { href: "/school/fees/types", label: "Fee types" },
];

export function rupees(value: number): string {
  return `₹${Number(value || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const PAYMENT_STATUS: Record<PaymentStatus, { label: string; tone: ChipTone }> = {
  success: { label: "Paid", tone: "green" },
  pending: { label: "Pending confirmation", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
};

export function PaymentChip({ status }: { status: PaymentStatus }) {
  return <Chip tone={PAYMENT_STATUS[status].tone}>{PAYMENT_STATUS[status].label}</Chip>;
}

export function categoryLabel(value: string): string {
  return FEE_CATEGORIES.find((item) => item.value === value)?.label ?? value;
}

/** Search box that finds a student by name or admission number and returns their row. */
export function StudentPicker({ id, value, onPick, error, label = "Student" }: { id: string; value: StudentRow | null; onPick: (student: StudentRow | null) => void; error?: string; label?: string }) {
  const [text, setText] = useState("");
  const q = useDebounced(text.trim());
  const loader = useCallback(() => peopleService("students").listStudents({ q, pageSize: 8, status: "1" }).then((page) => page.items), [q]);
  const results = useOptions(q.length >= 2 ? loader : null);
  if (value) {
    return (
      <div className="form-field">
        <span className="field-label">{label}</span>
        <div className="ops-picked">
          <strong>{value.name}</strong>
          <span className="muted">
            {value.admission_no} · {value.class_name} {value.section_name}
          </span>
          <button className="link-btn" type="button" onClick={() => onPick(null)}>
            Change
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="form-field">
      <label htmlFor={id}>{label} *</label>
      <input id={id} type="search" autoComplete="off" placeholder="Name or admission number" value={text} className={error ? "invalid" : undefined} aria-invalid={Boolean(error)} onChange={(event) => setText(event.target.value)} />
      {error ? <p className="field-error">{error}</p> : <p className="field-hint">Type at least 2 letters.</p>}
      {q.length >= 2 ? (
        <ul className="ops-results" role="listbox" aria-label="Matching students">
          {results.loading ? <li className="muted">Searching…</li> : null}
          {!results.loading && results.options.length === 0 ? <li className="muted">No active student matches “{q}”.</li> : null}
          {results.options.map((student) => (
            <li key={student.id}>
              <button type="button" role="option" aria-selected="false" onClick={() => onPick(student)}>
                <strong>{student.name}</strong>
                <span className="muted">
                  {student.admission_no} · {student.class_name} {student.section_name}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function FeeTypeForm({ type, onClose, onSaved }: { type: FeeType | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const [name, setName] = useState(type?.name ?? "");
  const [category, setCategory] = useState<string>(type?.category ?? "tuition");
  const [description, setDescription] = useState(type?.description ?? "");
  const [active, setActive] = useState(type ? type.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!name.trim()) invalid.name = "Enter a name.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      const input: FeeTypeInput = { name: name.trim(), category: category as FeeTypeInput["category"], description: description.trim() || null, status: active ? 1 : 0 };
      await feeService().saveType(input, type?.id);
      onSaved(!type);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the fee type.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={type ? "Edit fee type" : "Add fee type"} error={errors.formError} saving={saving} submitLabel="Save fee type" onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="ft-name" label="Name" required maxLength={80} value={name} onChange={setName} error={errors.fieldErrors.name} placeholder="Tuition fee" />
      <SelectField id="ft-category" label="Category" required value={category} onChange={setCategory} options={FEE_CATEGORIES.map((item) => ({ value: item.value, label: item.label }))} error={errors.fieldErrors.category} />
      <TextAreaField id="ft-description" label="Description" span maxLength={255} value={description} onChange={setDescription} />
      <StatusToggle id="ft-active" checked={active} onChange={setActive} label="Active (can be added to fee structures)" />
    </FormModal>
  );
}

type ItemDraft = { fee_type_id: string; amount: string };
type InstallmentDraft = { id?: number; name: string; due_date: string; amount: string };

export function StructureForm({ structure, onClose, onSaved }: { structure: FeeStructure | null; onClose: () => void; onSaved: (saved: FeeStructure, created: boolean) => void }) {
  const live = isOpsLive("fees");
  const sessions = useSessions();
  const currentSessionId = useCurrentSessionId();
  const [sessionId, setSessionId] = useState(structure ? String(structure.session_year_id) : "");
  const effectiveSession = sessionId || (structure ? "" : String(currentSessionId || ""));
  const classes = useClassesFor(effectiveSession ? Number(effectiveSession) : "", true);
  const types = useOptions(useCallback(() => feeService().types(), []));
  const [name, setName] = useState(structure?.name ?? "");
  const [classId, setClassId] = useState(structure ? String(structure.class_id) : "");
  const [items, setItems] = useState<ItemDraft[]>(structure ? structure.items.map((item) => ({ fee_type_id: String(item.fee_type_id), amount: String(item.amount) })) : [{ fee_type_id: "", amount: "" }]);
  const [installments, setInstallments] = useState<InstallmentDraft[]>(
    structure ? structure.installments.map((item) => ({ id: item.id, name: item.name, due_date: item.due_date, amount: String(item.amount) })) : [{ name: "Full payment", due_date: "", amount: "" }],
  );
  const [lateFee, setLateFee] = useState(structure ? String(structure.late_fee_per_day) : "0");
  const [active, setActive] = useState(structure ? structure.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const total = useMemo(() => paise(items.reduce((sum, item) => sum + (Number(item.amount) || 0), 0)), [items]);
  const planned = useMemo(() => paise(installments.reduce((sum, item) => sum + (Number(item.amount) || 0), 0)), [installments]);

  function splitInto(count: number) {
    const amounts = splitEvenly(total, count);
    setInstallments((list) =>
      amounts.map((amount, index) => ({
        id: list[index]?.id,
        name: list[index]?.name || (count === 1 ? "Full payment" : `Installment ${index + 1}`),
        due_date: list[index]?.due_date ?? "",
        amount: amount.toFixed(2),
      })),
    );
  }

  async function submit() {
    const input = {
      name,
      session_year_id: Number(effectiveSession),
      class_id: Number(classId),
      items: items.map((item) => ({ fee_type_id: Number(item.fee_type_id), amount: Number(item.amount) })),
      installments: installments.map((item): InstallmentInput => ({ id: item.id, name: item.name, due_date: item.due_date, amount: Number(item.amount) })),
      late_fee_per_day: Number(lateFee) || 0,
      status: (active ? 1 : 0) as 0 | 1,
    };
    const problems = structureFormProblems(input);
    if (Object.keys(problems).length) {
      errors.setFieldErrors(problems);
      errors.setFormError(problems.installments || problems.items || "");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      onSaved(await feeService().saveStructure(input, structure?.id), !structure);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the fee structure.");
      setSaving(false);
    }
  }

  const fe = errors.fieldErrors;
  const activeTypes = types.options.filter((type) => type.status === 1 || items.some((item) => item.fee_type_id === String(type.id)));

  return (
    <FormModal title={structure ? "Edit fee structure" : "Add fee structure"} description={live ? "Fees for one class in one session. Assign the structure to each student who pays it." : "Fees for one class in one session, collected in one or more installments."} error={errors.formError} saving={saving} submitLabel="Save fee structure" wide onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="fs-name" label="Name" required span maxLength={120} value={name} onChange={setName} error={fe.name} placeholder="Class 5 annual fees 2026-27" />
      <SelectField
        id="fs-session"
        label="Academic session"
        required
        placeholder="Choose a session"
        loading={sessions.loading}
        value={effectiveSession}
        disabled={live && Boolean(structure)}
        onChange={(value) => {
          setSessionId(value);
          setClassId("");
        }}
        options={sessions.options.map((row) => ({ value: String(row.id), label: sessionLabel(row) }))}
        error={fe.session_year_id}
      />
      <SelectField id="fs-class" label="Class" required placeholder={effectiveSession ? "Choose a class" : "Choose a session first"} loading={classes.loading} disabled={!effectiveSession || (live && Boolean(structure))} value={classId} onChange={setClassId} options={classes.options.map((row) => ({ value: String(row.id), label: classLabel(row) }))} error={fe.class_id} />
      <fieldset className="form-field field-span ops-lines">
        <legend>Fees *</legend>
        {items.map((item, index) => (
          <div key={index} className="ops-line">
            <select aria-label={`Fee type ${index + 1}`} value={item.fee_type_id} className={fe[`items.${index}.fee_type_id`] ? "invalid" : undefined} onChange={(event) => setItems((list) => list.map((row, i) => (i === index ? { ...row, fee_type_id: event.target.value } : row)))}>
              <option value="">{types.loading ? "Loading…" : "Choose a fee type"}</option>
              {activeTypes.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name} ({categoryLabel(type.category)})
                </option>
              ))}
            </select>
            <input aria-label={`Amount ${index + 1}`} type="number" min={0} step="0.01" inputMode="decimal" placeholder="Amount (₹)" value={item.amount} className={fe[`items.${index}.amount`] ? "invalid" : undefined} onChange={(event) => setItems((list) => list.map((row, i) => (i === index ? { ...row, amount: event.target.value } : row)))} />
            <button className="link-btn danger" type="button" disabled={items.length <= 1} onClick={() => setItems((list) => list.filter((_, i) => i !== index))}>
              Remove<span className="acad-sr"> fee {index + 1}</span>
            </button>
            {fe[`items.${index}.fee_type_id`] || fe[`items.${index}.amount`] ? <p className="field-error ops-line-error">{fe[`items.${index}.fee_type_id`] || fe[`items.${index}.amount`]}</p> : null}
          </div>
        ))}
        <div className="ops-line-foot">
          <button className="link-btn" type="button" onClick={() => setItems((list) => [...list, { fee_type_id: "", amount: "" }])}>
            + Add fee
          </button>
          <strong>Total {rupees(total)}</strong>
        </div>
      </fieldset>
      {live ? null : (
      <fieldset className="form-field field-span ops-lines">
        <legend>Installments *</legend>
        <div className="ops-line-foot">
          <span className="muted">Split the total into</span>
          {[1, 2, 3, 4, 12].map((count) => (
            <button key={count} className="link-btn" type="button" disabled={!total} onClick={() => splitInto(count)}>
              {count === 1 ? "one payment" : count === 12 ? "12 monthly" : `${count} parts`}
            </button>
          ))}
        </div>
        {installments.map((item, index) => (
          <div key={index} className="ops-line ops-line-3">
            <input aria-label={`Installment ${index + 1} name`} placeholder="Term 1" maxLength={60} value={item.name} className={fe[`installments.${index}.name`] ? "invalid" : undefined} onChange={(event) => setInstallments((list) => list.map((row, i) => (i === index ? { ...row, name: event.target.value } : row)))} />
            <input aria-label={`Installment ${index + 1} due date`} type="date" value={item.due_date} className={fe[`installments.${index}.due_date`] ? "invalid" : undefined} onChange={(event) => setInstallments((list) => list.map((row, i) => (i === index ? { ...row, due_date: event.target.value } : row)))} />
            <input aria-label={`Installment ${index + 1} amount`} type="number" min={0} step="0.01" inputMode="decimal" placeholder="Amount (₹)" value={item.amount} className={fe[`installments.${index}.amount`] ? "invalid" : undefined} onChange={(event) => setInstallments((list) => list.map((row, i) => (i === index ? { ...row, amount: event.target.value } : row)))} />
            <button className="link-btn danger" type="button" disabled={installments.length <= 1} onClick={() => setInstallments((list) => list.filter((_, i) => i !== index))}>
              Remove<span className="acad-sr"> installment {index + 1}</span>
            </button>
            {fe[`installments.${index}.name`] || fe[`installments.${index}.due_date`] || fe[`installments.${index}.amount`] ? (
              <p className="field-error ops-line-error">{fe[`installments.${index}.name`] || fe[`installments.${index}.due_date`] || fe[`installments.${index}.amount`]}</p>
            ) : null}
          </div>
        ))}
        <div className="ops-line-foot">
          <button className="link-btn" type="button" disabled={installments.length >= 12} onClick={() => setInstallments((list) => [...list, { name: `Installment ${list.length + 1}`, due_date: "", amount: "" }])}>
            + Add installment
          </button>
          <span className={Math.abs(planned - total) > 0.001 ? "field-error" : "muted"}>
            Planned {rupees(planned)} of {rupees(total)}
          </span>
        </div>
        {fe.installments ? <p className="field-error">{fe.installments}</p> : null}
      </fieldset>
      )}
      {live ? null : <TextField id="fs-late" label="Late fee per day (₹)" type="number" min="0" value={lateFee} onChange={setLateFee} error={fe.late_fee_per_day} hint="Shown on overdue installments; 0 for none." />}
      <StatusToggle id="fs-active" checked={active} onChange={setActive} label="Active (charged to students)" />
    </FormModal>
  );
}

export function ConcessionForm({
  structures,
  concession,
  onClose,
  onSaved,
}: {
  structures: FeeStructure[];
  concession: { id: number; student: StudentRow | null; structure_id: number; kind: ConcessionKind; value: number; reason: string } | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [student, setStudent] = useState<StudentRow | null>(concession?.student ?? null);
  const [structureId, setStructureId] = useState(concession ? String(concession.structure_id) : "");
  const [kind, setKind] = useState<ConcessionKind>(concession?.kind ?? "percent");
  const [value, setValue] = useState(concession ? String(concession.value) : "");
  const [reason, setReason] = useState(concession?.reason ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const structure = structures.find((row) => String(row.id) === structureId);
  const worth = structure && Number(value) > 0 ? (kind === "percent" ? (structure.total * Math.min(Number(value), 100)) / 100 : Math.min(Number(value), structure.total)) : 0;

  async function submit() {
    errors.clear();
    setSaving(true);
    try {
      await feeService().saveConcession({ student_id: student?.id ?? concession?.student?.id ?? 0, structure_id: Number(structureId), kind, value: Number(value), reason }, concession?.id);
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to save the concession.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={concession ? "Edit concession" : "Add concession or exemption"} description="A discount on one fee structure for one student. 100% is a full exemption." error={errors.formError} saving={saving} submitLabel="Save concession" wide onSubmit={() => void submit()} onClose={onClose}>
      {concession?.student ? (
        <div className="form-field">
          <span className="field-label">Student</span>
          <strong>{concession.student.name}</strong>
        </div>
      ) : (
        <StudentPicker id="cn-student" value={student} onPick={setStudent} error={errors.fieldErrors.student_id} />
      )}
      <SelectField id="cn-structure" label="Fee structure" required placeholder="Choose a structure" value={structureId} onChange={setStructureId} options={structures.map((row) => ({ value: String(row.id), label: `${row.name} (${rupees(row.total)})` }))} error={errors.fieldErrors.structure_id} />
      <SelectField id="cn-kind" label="Type" required value={kind} onChange={(v) => setKind(v as ConcessionKind)} options={[{ value: "percent", label: "Percentage of the fees" }, { value: "amount", label: "Fixed amount (₹)" }]} />
      <TextField id="cn-value" label={kind === "percent" ? "Percentage" : "Amount (₹)"} type="number" min="0" required value={value} onChange={setValue} error={errors.fieldErrors.value} hint={worth ? `Worth ${rupees(worth)} on this structure.` : undefined} />
      <TextField id="cn-reason" label="Reason" required span maxLength={120} value={reason} onChange={setReason} error={errors.fieldErrors.reason} placeholder="Sibling discount, staff ward, scholarship…" />
    </FormModal>
  );
}
