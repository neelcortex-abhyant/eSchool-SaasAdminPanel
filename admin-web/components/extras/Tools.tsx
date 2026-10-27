"use client";

import { useCallback, useEffect, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { FormModal } from "@/components/academics/FormModal";
import { SelectField, TextAreaField, TextField } from "@/components/academics/Fields";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage, StudentSearch } from "@/components/extras/Frame";
import { Stat } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { create, displayValue, getOne, listRows, replace, staffDirectory, update, type Raw, type StaffRef } from "@/lib/extras/api";
import { CARD_PLACEHOLDERS, idCardBody, parseIdCardSettings, type CardKind, type IdCardSettings } from "@/lib/extras/idCards";
import { IdCardView, useCardSchool, type CardData } from "@/components/extras/IdCard";
import type { StudentRow } from "@/lib/people";
import { num, optStr, str } from "@/lib/teaching/client";
import { IconBook, IconFees, IconStaff } from "@/lib/icons";

function today() {
  return new Date().toISOString().slice(0, 10);
}

// ---------- Certificates ----------

/** Fills {placeholders} in a certificate's text; unknown ones stay as they are. */
export function fillTemplate(text: string, values: Record<string, string>): string {
  return text.replace(/\{\s*(\w+)\s*\}/g, (match, key: string) => (key in values ? values[key] : match));
}

export function CertificateAssign() {
  return (
    <ExtrasPage
      title="Certificate assign"
      description="Issue a certificate to a student from a template, then print it."
      icon={<IconBook width={18} height={18} />}
      note="Placeholders you can use in a template: {student_name}, {admission_no}, {class}, {section}, {roll_number}, {certificate_no}, {date}."
    >
      <CertificateBody />
    </ExtrasPage>
  );
}

function CertificateBody() {
  const toast = useToast();
  const templates = useOptions(useCallback(() => listRows("/certificate-templates") as Promise<(Raw & { id: number })[]>, []));
  const [templateId, setTemplateId] = useState("");
  const [student, setStudent] = useState<StudentRow | null>(null);
  const [number, setNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [issued, setIssued] = useState<{ text: string; title: string; number: string } | null>(null);
  const errors = useFormErrors();

  async function issue() {
    const invalid: Record<string, string> = {};
    if (!templateId) invalid.template = "Choose a template.";
    if (!student) invalid.student = "Choose the student.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      const template = templates.options.find((row) => String(row.id) === templateId) as Raw;
      const picked = student as StudentRow;
      const data = { student_name: picked.name, admission_no: picked.admission_no, class: picked.class_name, section: picked.section_name, roll_number: picked.roll_number ? String(picked.roll_number) : "", date: today() };
      const row = await create("/certificates/issue", { template_id: Number(templateId), student_id: picked.id, certificate_no: number.trim() || null, data });
      const certificateNo = str(row.certificate_no);
      setIssued({ title: str(template.name), number: certificateNo, text: fillTemplate(str(template.body_text), { ...data, certificate_no: certificateNo }) });
      toast("success", `Certificate ${certificateNo} issued.`);
    } catch (caught) {
      errors.fromError(caught, "Unable to issue the certificate.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <form
        className="resource-card resource-fields ops-no-print"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void issue();
        }}
      >
        {errors.formError ? <div className="alert alert-danger field-span">{errors.formError}</div> : null}
        <SelectField
          id="ce-template"
          label="Template"
          required
          placeholder={templates.options.length || templates.loading ? "Choose a template" : "Add a template first"}
          loading={templates.loading}
          value={templateId}
          onChange={setTemplateId}
          options={templates.options.map((row) => ({ value: String(row.id), label: str(row.name) }))}
          error={errors.fieldErrors.template}
        />
        <StudentSearch id="ce-student" label="Student" required value={student} onChange={setStudent} error={errors.fieldErrors.student} />
        <TextField id="ce-number" label="Certificate number" maxLength={64} value={number} onChange={setNumber} hint="Leave empty to number it automatically." />
        <div className="field-span">
          <button className="btn-pill btn-pill-green ops-inline-btn" type="submit" disabled={saving}>
            {saving ? "Issuing…" : "Issue certificate"}
          </button>
        </div>
      </form>
      {issued ? (
        <section className="resource-card extras-print" aria-label="Certificate">
          <div className="page-actions ops-no-print">
            <button className="btn-pill btn-pill-green" type="button" onClick={() => window.print()}>
              Print
            </button>
          </div>
          <h2>{issued.title}</h2>
          <p className="muted">No. {issued.number}</p>
          <p style={{ whiteSpace: "pre-wrap" }}>{issued.text || "This template has no text."}</p>
        </section>
      ) : null}
    </>
  );
}

// ---------- ID cards ----------

type Card = { kind: CardKind; title: string; lines: [string, string][]; image: string | null; front: string | null; back: string | null };

/** A printable card: the kind's own lines, and its front/back text with {placeholders} filled in. */
export function cardOf(kind: CardKind, data: Raw, lines: [string, string][], placeholders: Record<string, string>): Card {
  const name = `${str(data.first_name)} ${str(data.last_name)}`.trim() || "—";
  const text = parseIdCardSettings((data.settings as Raw | null) ?? {})[kind];
  const values: Record<string, string> = { name, ...placeholders };
  return {
    kind,
    title: name,
    lines: lines.filter(([, value]) => value && value !== "—"),
    image: optStr(data.image),
    front: text.front ? fillTemplate(text.front, values) : null,
    back: text.back ? fillTemplate(text.back, values) : null,
  };
}

function IdCard({ card }: { card: Card }) {
  const school = useCardSchool();
  return (
    <section className="resource-card extras-print" aria-label="ID card">
      <div className="page-actions ops-no-print">
        <button className="btn-pill btn-pill-green" type="button" onClick={() => window.print()}>
          Print or save as PDF
        </button>
        <span className="muted">Prints at ID card size (85.6 × 54 mm), front and back.</span>
      </div>
      <IdCardView card={card} school={school} />
    </section>
  );
}

export function StudentIdCard() {
  return (
    <ExtrasPage title="Student ID card" description="Print a student's ID card. Set what it shows in ID card settings." icon={<IconBook width={18} height={18} />}>
      <StudentCardBody />
    </ExtrasPage>
  );
}

function StudentCardBody() {
  const [student, setStudent] = useState<StudentRow | null>(null);
  const card = useOptions(
    useCallback(
      () =>
        student
          ? getOne(`/students/${student.id}/id-card`).then((data) => [
              cardOf(
                "student",
                data,
                [
                  ["Class", `${student.class_name} ${student.section_name}`],
                  ["Roll no.", displayValue(data.roll_number)],
                  ["Admission no.", str(data.admission_no)],
                  ["Guardian", student.guardian_name ?? ""],
                  ["Session", student.session_name],
                ],
                {
                  class: `${student.class_name} ${student.section_name}`,
                  roll_number: data.roll_number === null || data.roll_number === undefined ? "" : String(data.roll_number),
                  admission_no: str(data.admission_no),
                  guardian: student.guardian_name ?? "",
                  session: student.session_name,
                },
              ),
            ])
          : Promise.resolve([]),
      [student],
    ),
  );
  return (
    <>
      <div className="resource-card resource-fields ops-no-print">
        <StudentSearch id="sc-student" label="Student" required value={student} onChange={setStudent} />
      </div>
      <ErrorAlert error={card.error} onRetry={() => void card.reload()} />
      {card.options[0] ? <IdCard card={card.options[0]} /> : null}
    </>
  );
}

export function StaffIdCard() {
  return (
    <ExtrasPage title="Staff ID card" description="Print a staff member's ID card. Set what it shows in ID card settings." icon={<IconStaff width={18} height={18} />}>
      <StaffCardBody />
    </ExtrasPage>
  );
}

function StaffCardBody() {
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [staffId, setStaffId] = useState("");
  const card = useOptions(
    useCallback(
      () =>
        staffId
          ? getOne(`/staff/${staffId}/id-card`).then((data) => [
              cardOf(
                "staff",
                data,
                [
                  ["Designation", str(data.designation)],
                  ["Employee ID", str(data.employee_id)],
                  ["Department", str(data.department)],
                ],
                { designation: str(data.designation), employee_id: str(data.employee_id), department: str(data.department) },
              ),
            ])
          : Promise.resolve([]),
      [staffId],
    ),
  );
  return (
    <>
      <div className="resource-card resource-fields ops-no-print">
        <SelectField
          id="sf-staff"
          label="Staff member"
          required
          placeholder="Choose a staff member"
          loading={people.loading}
          value={staffId}
          onChange={setStaffId}
          options={people.options.map((row) => ({ value: String(row.staff_id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }))}
        />
      </div>
      <ErrorAlert error={card.error ?? people.error} onRetry={() => void card.reload()} />
      {card.options[0] ? <IdCard card={card.options[0]} /> : null}
    </>
  );
}

// ---------- Roles ----------

export function RolePermission() {
  return (
    <ExtrasPage title="Role permission" description="Which roles each teacher or staff member has in the school." icon={<IconStaff width={18} height={18} />} note="Roles control what someone can open in the school's apps. Teacher and Staff are created automatically when used.">
      <RolesBody />
    </ExtrasPage>
  );
}

function RolesBody() {
  const toast = useToast();
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const roles = useOptions(useCallback(() => listRows("/staff-roles").then((rows) => rows.map((row) => str(row.name)).filter(Boolean)), []));
  const [userId, setUserId] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let live = true;
    setLoaded(false);
    setError(null);
    if (!userId) return;
    getOne(`/staff/${userId}/roles`)
      .then((data) => {
        if (!live) return;
        setPicked(new Set((Array.isArray(data.roles) ? (data.roles as Raw[]) : []).map((row) => str(row.name))));
        setLoaded(true);
      })
      .catch((caught) => live && setError(caught));
    return () => {
      live = false;
    };
  }, [userId]);

  const names = [...new Set([...roles.options, "Teacher", "Staff", ...picked])].sort();
  return (
    <>
      <div className="resource-card resource-fields">
        <SelectField
          id="rl-user"
          label="Teacher or staff member"
          required
          placeholder="Choose someone"
          loading={people.loading}
          value={userId}
          onChange={setUserId}
          options={people.options.filter((row) => row.user_id).map((row) => ({ value: String(row.user_id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }))}
        />
      </div>
      <ErrorAlert error={error ?? roles.error ?? people.error} />
      {userId && loaded ? (
        <div className="resource-card">
          <fieldset className="form-field">
            <legend>Roles</legend>
            {names.map((name) => (
              <label key={name} className="acad-check">
                <input
                  type="checkbox"
                  checked={picked.has(name)}
                  onChange={(event) =>
                    setPicked((current) => {
                      const next = new Set(current);
                      if (event.target.checked) next.add(name);
                      else next.delete(name);
                      return next;
                    })
                  }
                />
                <span>{name}</span>
              </label>
            ))}
          </fieldset>
          <button
            className="btn-pill btn-pill-green"
            type="button"
            disabled={saving || picked.size === 0}
            onClick={async () => {
              setSaving(true);
              try {
                await replace(`/staff/${userId}/roles`, { roles: [...picked] });
                toast("success", "Roles saved.");
              } catch (caught) {
                toast("error", errorMessage(caught, "Unable to save the roles."));
              } finally {
                setSaving(false);
              }
            }}
          >
            {saving ? "Saving…" : "Save roles"}
          </button>
          {picked.size === 0 ? <p className="field-hint">Keep at least one role.</p> : null}
        </div>
      ) : null}
    </>
  );
}

// ---------- Payroll ----------

type PayrollRun = Raw & { id: number };
type PayLine = { staff_id: number; name: string; gross: string; deductions: string };

export function PayrollPage() {
  const [adding, setAdding] = useState(false);
  return (
    <ExtrasPage
      title="Payroll"
      description="Salary runs: what each staff member is paid for a period."
      icon={<IconFees width={18} height={18} />}
      note="A run is saved as a record of what was paid. The server can't edit or delete a run."
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setAdding(true)}>
          New payroll run
        </button>
      }
    >
      <PayrollBody adding={adding} setAdding={setAdding} />
    </ExtrasPage>
  );
}

function rupees(value: number) {
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function PayrollBody({ adding, setAdding }: { adding: boolean; setAdding: (value: boolean) => void }) {
  const toast = useToast();
  const runs = useOptions(useCallback(() => listRows("/payroll-runs").then((rows) => (rows as PayrollRun[]).sort((a, b) => str(b.run_date).localeCompare(str(a.run_date)))), []));
  const columns: Column<PayrollRun>[] = [
    { key: "period", label: "Period", render: (row) => <strong>{str(row.period_label)}</strong> },
    { key: "date", label: "Run date", render: (row) => displayValue(row.run_date) },
    { key: "status", label: "Status", render: (row) => (str(row.status) === "paid" ? "Paid" : "Draft") },
    { key: "total", label: "Total", render: (row) => rupees(num(row.total_amount)) },
  ];
  return (
    <>
      <ErrorAlert error={runs.error} onRetry={() => void runs.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={runs.options} loading={runs.loading} emptyText="No payroll runs yet." />
      </div>
      {adding ? (
        <PayrollForm
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            toast("success", "Payroll run saved.");
            void runs.reload();
          }}
        />
      ) : null}
    </>
  );
}

/** Net pay per line and the run's total. */
export function payrollTotals(lines: { gross: string; deductions: string }[]) {
  const nets = lines.map((line) => Math.round(((Number(line.gross) || 0) - (Number(line.deductions) || 0)) * 100) / 100);
  return { nets, total: Math.round(nets.reduce((sum, net) => sum + net, 0) * 100) / 100 };
}

function PayrollForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [period, setPeriod] = useState(() => new Date().toLocaleDateString("en-IN", { month: "long", year: "numeric" }));
  const [runDate, setRunDate] = useState(today());
  const [status, setStatus] = useState("draft");
  const [lines, setLines] = useState<PayLine[]>([]);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  useEffect(() => {
    // Gross pay starts from each person's monthly salary in Salary structure.
    if (people.options.length && !lines.length) setLines(people.options.map((row) => ({ staff_id: row.staff_id, name: row.name, gross: row.salary ? String(row.salary) : "", deductions: "" })));
  }, [people.options, lines.length]);

  const { nets, total } = payrollTotals(lines);
  const paid = lines.map((line, index) => ({ line, net: nets[index] })).filter(({ line }) => Number(line.gross) > 0);

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!period.trim()) invalid.period = "Enter the period, e.g. October 2026.";
    if (!paid.length) invalid.lines = "Enter the gross pay for at least one person.";
    if (paid.some(({ net }) => net < 0)) invalid.lines = "Deductions can't be more than the gross pay.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError(invalid.lines ?? "");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await create("/payroll-runs", {
        period_label: period.trim(),
        run_date: runDate,
        status,
        items: paid.map(({ line, net }) => ({ staff_id: line.staff_id, gross: Number(line.gross), deductions: Number(line.deductions) || 0, net })),
      });
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to save the payroll run.");
      setSaving(false);
    }
  }

  return (
    <FormModal title="New payroll run" description="Gross pay starts from each person's monthly salary (Salary structure). Add deductions, and clear anyone not paid in this run." error={errors.formError} saving={saving} submitLabel={`Save run (${rupees(total)})`} wide onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="pr-period" label="Period" required maxLength={64} value={period} onChange={setPeriod} error={errors.fieldErrors.period} />
      <TextField id="pr-date" label="Run date" type="date" value={runDate} onChange={setRunDate} />
      <SelectField id="pr-status" label="Status" value={status} onChange={setStatus} options={[{ value: "draft", label: "Draft" }, { value: "paid", label: "Paid" }]} />
      <fieldset className="form-field field-span ops-lines">
        <legend>Pay</legend>
        {people.loading ? <p className="muted">Loading staff…</p> : null}
        {lines.map((line, index) => (
          <div key={line.staff_id} className="ops-line ops-line-3">
            <span>{line.name}</span>
            <input aria-label={`${line.name} gross pay`} type="number" min={0} step="0.01" placeholder="Gross (₹)" value={line.gross} onChange={(event) => setLines((list) => list.map((row, i) => (i === index ? { ...row, gross: event.target.value } : row)))} />
            <input aria-label={`${line.name} deductions`} type="number" min={0} step="0.01" placeholder="Deductions (₹)" value={line.deductions} onChange={(event) => setLines((list) => list.map((row, i) => (i === index ? { ...row, deductions: event.target.value } : row)))} />
            <span className="muted">{Number(line.gross) > 0 ? rupees(nets[index]) : ""}</span>
          </div>
        ))}
      </fieldset>
    </FormModal>
  );
}


// ---------- ID card settings ----------

export function IdCardSettingsPage() {
  return (
    <ExtrasPage title="ID card settings" description="What students' ID cards and staff ID cards show. Each has its own front and back text." icon={<IconBook width={18} height={18} />}>
      <IdCardSettingsBody />
    </ExtrasPage>
  );
}

const SAMPLE: Record<CardKind, { title: string; lines: [string, string][]; values: Record<string, string> }> = {
  student: {
    title: "Diya Patel",
    lines: [["Class", "5 A"], ["Roll no.", "12"], ["Admission no.", "ADM2026001"], ["Guardian", "Kiran Patel"], ["Session", "2026-27"]],
    values: { name: "Diya Patel", class: "5 A", roll_number: "12", admission_no: "ADM2026001", guardian: "Kiran Patel", session: "2026-27" },
  },
  staff: {
    title: "Ravi Kumar",
    lines: [["Designation", "Accountant"], ["Employee ID", "STF0007"], ["Department", "Office"]],
    values: { name: "Ravi Kumar", designation: "Accountant", employee_id: "STF0007", department: "Office" },
  },
};

function IdCardSettingsBody() {
  const toast = useToast();
  const school = useCardSchool();
  const state = useOptions(useCallback(() => getOne("/id-card-settings").then((row) => [parseIdCardSettings(row)]), []));
  const [values, setValues] = useState<IdCardSettings | null>(null);
  const [kind, setKind] = useState<CardKind>("student");
  const [side, setSide] = useState<"front" | "back">("front");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (state.options[0]) setValues(state.options[0]);
  }, [state.options]);

  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!values) return <div className="resource-card"><div className="skeleton" style={{ height: 240 }} /></div>;

  const set = (text: string, which: "front" | "back") => setValues((current) => (current ? { ...current, [kind]: { ...current[kind], [which]: text } } : current));
  const sample = SAMPLE[kind];
  const preview: CardData = {
    kind,
    title: sample.title,
    lines: sample.lines,
    image: null,
    front: values[kind].front ? fillTemplate(values[kind].front, sample.values) : null,
    back: values[kind].back ? fillTemplate(values[kind].back, sample.values) : null,
  };

  function insert(placeholder: string) {
    const target = document.getElementById(`idc-${side}`) as HTMLTextAreaElement | null;
    const text = values?.[kind][side] ?? "";
    const at = target?.selectionStart ?? text.length;
    set(`${text.slice(0, at)}${placeholder}${text.slice(target?.selectionEnd ?? at)}`, side);
    requestAnimationFrame(() => {
      target?.focus();
      target?.setSelectionRange(at + placeholder.length, at + placeholder.length);
    });
  }

  return (
    <form
      noValidate
      onSubmit={async (event) => {
        event.preventDefault();
        setSaving(true);
        try {
          await replace("/id-card-settings", idCardBody(values));
          toast("success", "ID card settings saved for students and staff.");
          void state.reload();
        } catch (caught) {
          toast("error", errorMessage(caught, "Unable to save the settings."));
        } finally {
          setSaving(false);
        }
      }}
    >
      <nav className="acad-tabs" aria-label="Card">
        {(["student", "staff"] as CardKind[]).map((item) => (
          <button key={item} type="button" className={`acad-tab${kind === item ? " is-active" : ""}`} aria-pressed={kind === item} onClick={() => setKind(item)}>
            {item === "student" ? "Student ID card" : "Staff ID card"}
          </button>
        ))}
      </nav>
      <div className="idc-editor">
        <section className="resource-card idc-form" aria-label="Card text">
          <p className="muted">
            {kind === "student" ? "The card shows the photo, name, class, roll no., admission no. and guardian." : "The card shows the photo, name, designation, employee ID and department."}{" "}
            Add your own text for the front and back.
          </p>
          <div className="form-field">
            <label htmlFor="idc-front">Front side text</label>
            <textarea id="idc-front" rows={3} value={values[kind].front} placeholder={kind === "student" ? "Valid for the session {session}" : "Staff of the school"} onFocus={() => setSide("front")} onChange={(event) => set(event.target.value, "front")} />
          </div>
          <div className="form-field">
            <label htmlFor="idc-back">Back side text</label>
            <textarea id="idc-back" rows={3} value={values[kind].back} placeholder="Emergency: 1800 000 0000" onFocus={() => setSide("back")} onChange={(event) => set(event.target.value, "back")} />
            <p className="field-hint">The school's address and phone are added on the back automatically.</p>
          </div>
          <div className="form-field">
            <span className="field-label">Insert into the {side} side</span>
            <div className="idc-chips">
              {CARD_PLACEHOLDERS[kind].map((placeholder) => (
                <button key={placeholder} type="button" className="idc-chip" onClick={() => insert(placeholder)}>
                  {placeholder}
                </button>
              ))}
            </div>
          </div>
          <button className="btn-pill btn-pill-green ops-inline-btn" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save settings"}
          </button>
        </section>
        <section className="resource-card idc-preview" aria-label="Preview">
          <p className="field-label">Preview with sample details</p>
          <IdCardView card={preview} school={school} />
        </section>
      </div>
    </form>
  );
}

// ---------- Salary structure ----------

export function SalaryStructurePage() {
  return (
    <ExtrasPage
      title="Salary structure"
      description="The monthly salary for each teacher and staff member. New payroll runs start from these amounts."
      icon={<IconFees width={18} height={18} />}
      note="The server keeps one monthly salary per person. Allowances and deductions are entered for each payroll run."
    >
      <SalaryBody />
    </ExtrasPage>
  );
}

type SalaryRow = StaffRef & { id: number };

/** The route that edits a person's employment details: teachers and other staff are separate on the server. */
export function salaryPath(row: Pick<StaffRef, "kind" | "user_id">): string {
  return row.kind === "teacher" ? `/teachers/${row.user_id}` : `/staff/${row.user_id}`;
}

function SalaryBody() {
  const toast = useToast();
  const people = useOptions(useCallback(() => staffDirectory().then((rows) => rows.filter((row) => row.user_id).map((row) => ({ ...row, id: row.staff_id }))), []));
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<number | null>(null);
  const [kind, setKind] = useState<"" | "teacher" | "staff">("");
  const rows = people.options.filter((row) => !kind || row.kind === kind) as SalaryRow[];
  const total = rows.reduce((sum, row) => sum + (row.salary ?? 0), 0);
  const missing = rows.filter((row) => !row.salary).length;

  async function save(row: SalaryRow) {
    const value = Number(drafts[row.id]);
    if (!(value >= 0) || drafts[row.id] === "") {
      toast("error", "Enter a salary of 0 or more.");
      return;
    }
    setSaving(row.id);
    try {
      await update(salaryPath(row), { salary: value });
      toast("success", `Salary saved for ${row.name}.`);
      setDrafts((current) => {
        const next = { ...current };
        delete next[row.id];
        return next;
      });
      void people.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to save the salary."));
    } finally {
      setSaving(null);
    }
  }

  const columns: Column<SalaryRow>[] = [
    { key: "name", label: "Name", render: (row) => <div><strong>{row.name}</strong><div className="muted">{row.designation}</div></div> },
    { key: "kind", label: "Type", render: (row) => (row.kind === "teacher" ? "Teacher" : "Staff") },
    {
      key: "salary",
      label: "Monthly salary (₹)",
      render: (row) => (
        <input
          className="salary-input"
          type="number"
          min={0}
          step="100"
          inputMode="decimal"
          aria-label={`Monthly salary for ${row.name}`}
          value={drafts[row.id] ?? (row.salary ? String(row.salary) : "")}
          placeholder="Not set"
          onChange={(event) => setDrafts((current) => ({ ...current, [row.id]: event.target.value }))}
          onKeyDown={(event) => {
            if (event.key === "Enter") void save(row);
          }}
        />
      ),
    },
    { key: "year", label: "Per year", render: (row) => (row.salary ? rupees(row.salary * 12) : "—") },
  ];

  return (
    <>
      <div className="school-filters">
        <select aria-label="Show" value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
          <option value="">Teachers and staff</option>
          <option value="teacher">Teachers</option>
          <option value="staff">Other staff</option>
        </select>
      </div>
      <div className="teach-stats">
        <Stat label="Monthly payroll" value={rupees(total)} tone="green" />
        <Stat label="People" value={rows.length} />
        <Stat label="Salary not set" value={missing} tone={missing ? "amber" : "grey"} />
      </div>
      <ErrorAlert error={people.error} onRetry={() => void people.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={people.loading}
          emptyText={people.error ? "The list couldn't be loaded." : "No teachers or staff yet."}
          actions={(row) =>
            drafts[row.id] !== undefined ? (
              <button className="link-btn" type="button" disabled={saving !== null} onClick={() => void save(row)}>
                {saving === row.id ? "Saving…" : "Save"}
              </button>
            ) : null
          }
        />
      </div>
    </>
  );
}
