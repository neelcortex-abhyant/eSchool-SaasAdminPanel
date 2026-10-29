"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { useCardSchool } from "@/components/extras/IdCard";
import { Chip, Stat, type ChipTone } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { staffDirectory } from "@/lib/extras/api";
import { downloadText, toCsv } from "@/lib/operations/export";
import { isOperationsLive, OPERATIONS_SAMPLE_NOTE } from "@/lib/operations/mode";
import { isMonth, money, monthLabel, payrollService, salaryComponents, structureProblems, structureTotals } from "@/lib/operations/payroll";
import type { PayrollStatus, Payslip, SalaryLine, SalaryStructure } from "@/lib/operations/types";
import { newIdempotencyKey, useSubmitOnce } from "@/lib/ops/submit";
import { IconFees } from "@/lib/icons";

export const PAYROLL_TABS = [
  { href: "/school/payroll", label: "Process payroll" },
  { href: "/school/payslips", label: "Payslips" },
  { href: "/school/payroll-reports", label: "Reports" },
  { href: "/school/salary-structure", label: "Salary structures" },
  { href: "/school/salary-components", label: "Salary components" },
  { href: "/school/monthly-salary", label: "Monthly salary (server)" },
  { href: "/school/payroll-runs", label: "Payroll runs (server)" },
  { href: "/school/payroll-settings", label: "Settings" },
];

const icon = <IconFees width={18} height={18} />;
const note = () => (isOperationsLive("payroll") ? undefined : OPERATIONS_SAMPLE_NOTE.payroll);

const STATUS: Record<PayrollStatus, { label: string; tone: ChipTone }> = {
  processed: { label: "Processed", tone: "green" },
  pending: { label: "Pending", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
};

function thisMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

// ---------- Salary structures ----------

export function SalaryStructuresPage() {
  const [editing, setEditing] = useState<SalaryStructure | "new" | null>(null);
  return (
    <ExtrasPage
      title="Salary structures"
      description="Basic salary, allowances and deductions, and which employees each structure applies to."
      icon={icon}
      tabs={PAYROLL_TABS}
      note={note()}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add structure
        </button>
      }
    >
      <StructuresBody editing={editing} setEditing={setEditing} />
    </ExtrasPage>
  );
}

function StructuresBody({ editing, setEditing }: { editing: SalaryStructure | "new" | null; setEditing: (value: SalaryStructure | "new" | null) => void }) {
  const toast = useToast();
  const structures = useOptions(useCallback(() => payrollService().structures(), []));
  const assignments = useOptions(useCallback(() => payrollService().assignments(), []));
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [removing, setRemoving] = useState<SalaryStructure | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [pending, setPending] = useState(false);

  const columns: Column<SalaryStructure>[] = [
    { key: "name", label: "Structure", render: (row) => <strong>{row.name}</strong> },
    { key: "basic", label: "Basic", render: (row) => money(row.basic) },
    { key: "allowances", label: "Allowances", render: (row) => <div>{money(row.gross - row.basic)}<div className="muted">{row.allowances.map((line) => line.name).join(", ") || "None"}</div></div> },
    { key: "deductions", label: "Deductions", render: (row) => <div>{money(row.gross - row.net)}<div className="muted">{row.deductions.map((line) => line.name).join(", ") || "None"}</div></div> },
    { key: "net", label: "Net / month", render: (row) => <strong>{money(row.net)}</strong> },
    { key: "assigned", label: "Employees", render: (row) => row.assigned },
  ];
  const assigned = people.options.map((person) => ({ ...person, id: person.staff_id, assignment: assignments.options.find((row) => row.staff_id === person.staff_id) }));
  const assignedColumns: Column<(typeof assigned)[number]>[] = [
    { key: "name", label: "Employee", render: (row) => <div><strong>{row.name}</strong><div className="muted">{row.designation}</div></div> },
    { key: "department", label: "Department", render: (row) => row.department || "—" },
    { key: "structure", label: "Structure", render: (row) => (row.assignment ? row.assignment.structure_name : <Chip tone="amber">Not assigned</Chip>) },
    { key: "from", label: "From", render: (row) => row.assignment?.effective_from ?? "—" },
  ];

  return (
    <>
      <ErrorAlert error={structures.error ?? assignments.error} onRetry={() => void structures.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={structures.options}
          loading={structures.loading}
          emptyText="No salary structures yet."
          actions={(row) => (
            <>
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>Edit</button>
              <button className="link-btn danger" type="button" onClick={() => setRemoving(row)}>Delete</button>
            </>
          )}
        />
      </div>
      <div className="resource-card">
        <div className="page-actions">
          <h2>Who is on which structure</h2>
          <button className="btn-pill btn-pill-green-soft" type="button" disabled={!structures.options.length} onClick={() => setAssigning(true)}>Assign a structure</button>
        </div>
        <DataTable columns={assignedColumns} rows={assigned} loading={people.loading || assignments.loading} emptyText="No teachers or staff yet." />
      </div>
      {editing ? (
        <StructureForm
          structure={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? "Structure added." : "Structure saved.");
            void structures.reload();
          }}
        />
      ) : null}
      {assigning ? (
        <AssignForm
          structures={structures.options}
          people={people.options}
          current={assignments.options}
          onClose={() => setAssigning(false)}
          onSaved={(count) => {
            setAssigning(false);
            toast("success", `Structure assigned to ${count} employee${count === 1 ? "" : "s"}.`);
            void assignments.reload();
            void structures.reload();
          }}
        />
      ) : null}
      {removing ? (
        <ConfirmDialog
          title="Delete this structure?"
          body={`${removing.name} will be removed. Employees on it must be moved first.`}
          confirmLabel="Delete"
          tone="danger"
          pending={pending}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await payrollService().removeStructure(removing.id);
              toast("success", "Structure deleted.");
              void structures.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete the structure."));
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

type Draft = { name: string; amount: string };

function LinesEditor({ legend, lines, onChange, error, prefix }: { legend: string; lines: Draft[]; onChange: (lines: Draft[]) => void; error?: Record<string, string>; prefix: string }) {
  return (
    <fieldset className="form-field field-span ops-lines">
      <legend>{legend}</legend>
      {lines.map((line, index) => (
        <div key={index} className="ops-line">
          <input aria-label={`${legend} ${index + 1} name`} placeholder="Name" maxLength={60} value={line.name} onChange={(event) => onChange(lines.map((row, i) => (i === index ? { ...row, name: event.target.value } : row)))} />
          <input aria-label={`${legend} ${index + 1} amount`} type="number" min={0} step="0.01" placeholder="Amount (₹)" value={line.amount} onChange={(event) => onChange(lines.map((row, i) => (i === index ? { ...row, amount: event.target.value } : row)))} />
          <button className="link-btn danger" type="button" onClick={() => onChange(lines.filter((_, i) => i !== index))}>
            Remove<span className="acad-sr"> {line.name || `line ${index + 1}`}</span>
          </button>
          {error?.[`${prefix}.${index}`] ? <p className="field-error ops-line-error">{error[`${prefix}.${index}`]}</p> : null}
        </div>
      ))}
      <div className="ops-line-foot">
        <button className="link-btn" type="button" onClick={() => onChange([...lines, { name: "", amount: "" }])}>+ Add line</button>
      </div>
    </fieldset>
  );
}

function StructureForm({ structure, onClose, onSaved }: { structure: SalaryStructure | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const toDraft = (lines: SalaryLine[]) => lines.map((line) => ({ name: line.name, amount: String(line.amount) }));
  const [name, setName] = useState(structure?.name ?? "");
  const [basic, setBasic] = useState(structure ? String(structure.basic) : "");
  const [allowances, setAllowances] = useState<Draft[]>(structure ? toDraft(structure.allowances) : [{ name: "HRA", amount: "" }]);
  const [deductions, setDeductions] = useState<Draft[]>(structure ? toDraft(structure.deductions) : [{ name: "PF", amount: "" }]);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const components = useOptions(useCallback(() => salaryComponents().catch(() => []), []));
  const input = {
    name,
    basic: Number(basic),
    allowances: allowances.map((line) => ({ name: line.name, amount: Number(line.amount) || 0 })),
    deductions: deductions.map((line) => ({ name: line.name, amount: Number(line.amount) || 0 })),
  };
  const totals = structureTotals(input);
  async function submit() {
    const problems = structureProblems(input);
    if (Object.keys(problems).length) {
      errors.setFieldErrors(problems);
      errors.setFormError(problems.deductions ?? "");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await payrollService().saveStructure(input, structure?.id);
      onSaved(!structure);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the structure.");
      setSaving(false);
    }
  }
  return (
    <FormModal title={structure ? "Edit salary structure" : "Add salary structure"} error={errors.formError} saving={saving} submitLabel="Save structure" wide onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="ss-name" label="Name" required maxLength={80} value={name} onChange={setName} error={errors.fieldErrors.name} placeholder="Teacher – standard" />
      <TextField id="ss-basic" label="Basic salary (₹ / month)" type="number" min="0" required value={basic} onChange={setBasic} error={errors.fieldErrors.basic} />
      {components.options.length ? (
        <SelectField
          id="ss-component"
          label="Add a salary component"
          placeholder="Choose a component"
          value=""
          onChange={(value) => {
            const component = components.options.find((row) => String(row.id) === value);
            if (!component) return;
            const amount = component.calc_type === "percent" ? Math.round((Number(basic) || 0) * component.default_value) / 100 : component.default_value;
            const line = { name: component.name, amount: String(amount) };
            if (component.kind === "deduction") setDeductions((list) => [...list.filter((row) => row.name !== component.name), line]);
            else setAllowances((list) => [...list.filter((row) => row.name !== component.name), line]);
          }}
          options={components.options.map((row) => ({ value: String(row.id), label: `${row.name} · ${row.kind === "deduction" ? "deduction" : "earning"} · ${row.calc_type === "percent" ? `${row.default_value}% of basic` : money(row.default_value)}` }))}
          hint="From Salary components; percentages use the basic salary entered above."
          span
        />
      ) : null}
      <LinesEditor legend="Allowances" lines={allowances} onChange={setAllowances} error={errors.fieldErrors} prefix="allowances" />
      <LinesEditor legend="Deductions" lines={deductions} onChange={setDeductions} error={errors.fieldErrors} prefix="deductions" />
      <div className="field-span payroll-totals">
        <span>Gross <strong>{money(totals.gross)}</strong></span>
        <span>Deductions <strong>{money(totals.deductions)}</strong></span>
        <span>Net <strong>{money(totals.net)}</strong></span>
      </div>
    </FormModal>
  );
}

function AssignForm({
  structures,
  people,
  current,
  onClose,
  onSaved,
}: {
  structures: SalaryStructure[];
  people: Awaited<ReturnType<typeof staffDirectory>>;
  current: { staff_id: number; structure_id: number }[];
  onClose: () => void;
  onSaved: (count: number) => void;
}) {
  const [structureId, setStructureId] = useState(String(structures[0]?.id ?? ""));
  const [from, setFrom] = useState(`${thisMonth()}-01`);
  const [picked, setPicked] = useState<Set<number>>(new Set(people.filter((person) => !current.some((row) => row.staff_id === person.staff_id)).map((person) => person.staff_id)));
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    if (!picked.size) {
      errors.setFormError("Choose at least one employee.");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await payrollService().assign([...picked], Number(structureId), from);
      onSaved(picked.size);
    } catch (caught) {
      errors.fromError(caught, "Unable to assign the structure.");
      setSaving(false);
    }
  }
  return (
    <FormModal title="Assign a salary structure" description="Employees already on another structure move to this one from the date chosen." error={errors.formError} saving={saving} submitLabel={`Assign to ${picked.size}`} wide onSubmit={() => void submit()} onClose={onClose}>
      <SelectField id="as-structure" label="Structure" required value={structureId} onChange={setStructureId} options={structures.map((row) => ({ value: String(row.id), label: `${row.name} · ${money(row.net)} net` }))} />
      <TextField id="as-from" label="Starts on" type="date" required value={from} onChange={setFrom} error={errors.fieldErrors.effective_from} />
      <fieldset className="form-field field-span">
        <legend>Employees</legend>
        <div className="payroll-pick">
          {people.map((person) => {
            const on = current.find((row) => row.staff_id === person.staff_id);
            return (
              <label key={person.staff_id} className="acad-check">
                <input
                  type="checkbox"
                  checked={picked.has(person.staff_id)}
                  onChange={(event) =>
                    setPicked((set) => {
                      const next = new Set(set);
                      if (event.target.checked) next.add(person.staff_id);
                      else next.delete(person.staff_id);
                      return next;
                    })
                  }
                />
                <span>
                  {person.name} <span className="muted">{person.designation}{on ? ` · now on ${structures.find((row) => row.id === on.structure_id)?.name ?? "another structure"}` : ""}</span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
    </FormModal>
  );
}

// ---------- Process payroll ----------

export function PayrollProcessPage() {
  return (
    <ExtrasPage title="Process payroll" description="Check each employee's pay for the month, then process it once." icon={icon} tabs={PAYROLL_TABS} note={note()}>
      <ProcessBody />
    </ExtrasPage>
  );
}

function ProcessBody() {
  const toast = useToast();
  const [month, setMonth] = useState(thisMonth());
  const preview = useOptions(useCallback(() => (isMonth(month) ? payrollService().preview(month).then((row) => [row]) : Promise.resolve([])), [month]));
  const data = preview.options[0];
  const [confirming, setConfirming] = useState(false);
  const submit = useSubmitOnce();
  // One key per attempt: a retry after a network error can't process the month twice.
  const key = useRef(newIdempotencyKey());
  useEffect(() => {
    key.current = newIdempotencyKey();
  }, [month]);

  const lines = (data?.lines ?? []).map((row) => ({ ...row, id: row.staff_id }));
  const eligible = lines.filter((row) => row.eligible);
  const columns: Column<(typeof lines)[number]>[] = [
    { key: "name", label: "Employee", render: (row) => <div><strong>{row.name}</strong><div className="muted">{row.department || "—"}{row.structure_name ? ` · ${row.structure_name}` : ""}</div></div> },
    { key: "basic", label: "Basic", render: (row) => (row.eligible ? money(row.basic) : "—") },
    { key: "allowances", label: "Allowances", render: (row) => (row.eligible ? money(row.allowances) : "—") },
    { key: "deductions", label: "Deductions", render: (row) => (row.eligible ? money(row.deductions) : "—") },
    { key: "attendance", label: "Attendance", render: (row) => (row.eligible ? <div>{row.paid_days} / {row.working_days} days{row.attendance_adjustment ? <div className="field-error">− {money(row.attendance_adjustment)}</div> : null}</div> : "—") },
    { key: "net", label: "Net pay", render: (row) => (row.eligible ? <strong>{money(row.net)}</strong> : <Chip tone="amber">{row.problem ?? "Not eligible"}</Chip>) },
  ];

  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">
          Payroll month
          <input type="month" value={month} max={thisMonth()} onChange={(event) => setMonth(event.target.value)} />
        </label>
        <button className="btn-pill btn-pill-green" type="button" disabled={!data || data.already_processed || !eligible.length || submit.busy} onClick={() => setConfirming(true)}>
          {submit.busy ? "Processing…" : data?.already_processed ? "Already processed" : `Process ${eligible.length} payslip${eligible.length === 1 ? "" : "s"}`}
        </button>
      </div>
      {data?.already_processed ? <div className="alert alert-info">Payroll for {monthLabel(month)} has been processed. See the payslips.</div> : null}
      {data && !data.already_processed && lines.length > eligible.length ? (
        <div className="alert alert-info">
          {lines.length - eligible.length} employee{lines.length - eligible.length === 1 ? " has" : "s have"} no salary structure and won't be paid. <a href="/school/salary-structure">Assign one under Salary structures</a>.
        </div>
      ) : null}
      {data ? (
        <div className="teach-stats">
          <Stat label="Eligible employees" value={eligible.length} tone="green" />
          <Stat label="Need a salary structure" value={lines.length - eligible.length} tone={lines.length - eligible.length ? "amber" : "grey"} />
          <Stat label="Total net pay" value={money(data.total_net)} tone="blue" />
        </div>
      ) : null}
      <ErrorAlert error={preview.error} onRetry={() => void preview.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={lines} loading={preview.loading} emptyText="No teachers or staff yet." />
      </div>
      <p className="muted">Amounts come from the server's payroll calculation, including deductions for unpaid absence.</p>
      {confirming && data ? (
        <ConfirmDialog
          title={`Process payroll for ${monthLabel(month)}?`}
          body={`${eligible.length} payslip${eligible.length === 1 ? "" : "s"} totalling ${money(data.total_net)} will be created. This can only be done once for the month.`}
          confirmLabel="Process payroll"
          pending={submit.busy}
          onCancel={() => setConfirming(false)}
          onConfirm={() =>
            void submit.run(async () => {
              try {
                const result = await payrollService().process(month, key.current);
                toast(result.failed ? "error" : "success", `${result.processed} payslip${result.processed === 1 ? "" : "s"} processed${result.failed ? `, ${result.failed} failed` : ""}.`);
                key.current = newIdempotencyKey();
                void preview.reload();
              } catch (caught) {
                toast("error", errorMessage(caught, "Unable to process the payroll."));
              } finally {
                setConfirming(false);
              }
            })
          }
        />
      ) : null}
    </>
  );
}

// ---------- Payslips ----------

export function PayslipsPage() {
  return (
    <ExtrasPage title="Payslips" description="Every processed payslip. Open one to view, print or save it as a PDF." icon={icon} tabs={PAYROLL_TABS} note={note()}>
      <PayslipsBody />
    </ExtrasPage>
  );
}

function PayslipsBody() {
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [month, setMonth] = useState("");
  const [staffId, setStaffId] = useState("");
  const [status, setStatus] = useState<PayrollStatus | "">("");
  const [department, setDepartment] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<Payslip | null>(null);
  const list = usePagedList(useCallback(() => payrollService().payslips({ page, pageSize: 20, month, staffId: staffId ? Number(staffId) : "", status, department }), [page, month, staffId, status, department]));
  const departments = useMemo(() => [...new Set(people.options.map((row) => row.department ?? "").filter(Boolean))].sort(), [people.options]);
  const columns: Column<Payslip>[] = [
    { key: "month", label: "Month", render: (row) => monthLabel(row.month) },
    { key: "name", label: "Employee", render: (row) => <div><strong>{row.name}</strong><div className="muted">{row.employee_code || row.designation}</div></div> },
    { key: "department", label: "Department", render: (row) => row.department || "—" },
    { key: "gross", label: "Gross", render: (row) => money(row.gross) },
    { key: "net", label: "Net", render: (row) => <strong>{money(row.net)}</strong> },
    { key: "status", label: "Status", render: (row) => <div><Chip tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Chip>{row.failure_reason ? <div className="muted">{row.failure_reason}</div> : null}</div> },
  ];
  const reset = () => setPage(1);
  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">Month <input type="month" value={month} onChange={(event) => { setMonth(event.target.value); reset(); }} /></label>
        <select aria-label="Employee" value={staffId} onChange={(event) => { setStaffId(event.target.value); reset(); }}>
          <option value="">All employees</option>
          {people.options.map((row) => <option key={row.staff_id} value={row.staff_id}>{row.name}</option>)}
        </select>
        <select aria-label="Department" value={department} onChange={(event) => { setDepartment(event.target.value); reset(); }}>
          <option value="">All departments</option>
          {departments.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <select aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value as PayrollStatus | ""); reset(); }}>
          <option value="">Any status</option>
          {(Object.keys(STATUS) as PayrollStatus[]).map((key) => <option key={key} value={key}>{STATUS[key].label}</option>)}
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.data?.items ?? []}
          loading={list.loading}
          emptyText={list.error ? "Payslips couldn't be loaded." : "No payslips yet. Process a month's payroll to create them."}
          actions={(row) => <button className="link-btn" type="button" onClick={() => setOpen(row)} disabled={row.status !== "processed"}>View</button>}
        />
        <Pagination page={page} pageSize={20} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {open ? <PayslipDialog payslip={open} onClose={() => setOpen(null)} /> : null}
    </>
  );
}

export function PayslipView({ payslip, schoolName }: { payslip: Payslip; schoolName: string }) {
  return (
    <article className="payslip" aria-label={`Payslip for ${payslip.name}, ${monthLabel(payslip.month)}`}>
      <header className="payslip-head">
        <div>
          <h2>{schoolName}</h2>
          <p className="muted">Payslip for {monthLabel(payslip.month)}</p>
        </div>
        <Chip tone={STATUS[payslip.status].tone}>{STATUS[payslip.status].label}</Chip>
      </header>
      <dl className="teach-facts">
        <div><dt>Employee</dt><dd>{payslip.name}</dd></div>
        <div><dt>Employee ID</dt><dd>{payslip.employee_code || "—"}</dd></div>
        <div><dt>Designation</dt><dd>{payslip.designation || "—"}</dd></div>
        <div><dt>Department</dt><dd>{payslip.department || "—"}</dd></div>
        <div><dt>Paid days</dt><dd>{payslip.paid_days} of {payslip.working_days}</dd></div>
      </dl>
      <div className="payslip-grid">
        <table className="data-table">
          <thead><tr><th scope="col">Earnings</th><th scope="col">Amount</th></tr></thead>
          <tbody>
            <tr><td>Basic</td><td>{money(payslip.basic)}</td></tr>
            {payslip.allowances.map((line) => <tr key={line.name}><td>{line.name}</td><td>{money(line.amount)}</td></tr>)}
            <tr className="ops-report-total"><th scope="row">Gross</th><td>{money(payslip.gross)}</td></tr>
          </tbody>
        </table>
        <table className="data-table">
          <thead><tr><th scope="col">Deductions</th><th scope="col">Amount</th></tr></thead>
          <tbody>
            {payslip.deductions.map((line) => <tr key={line.name}><td>{line.name}</td><td>{money(line.amount)}</td></tr>)}
            {payslip.attendance_adjustment ? <tr><td>Unpaid absence</td><td>{money(payslip.attendance_adjustment)}</td></tr> : null}
            <tr className="ops-report-total"><th scope="row">Total</th><td>{money(payslip.deductions.reduce((sum, line) => sum + line.amount, 0) + payslip.attendance_adjustment)}</td></tr>
          </tbody>
        </table>
      </div>
      <p className="payslip-net">Net pay <strong>{money(payslip.net)}</strong></p>
      <p className="muted">{payslip.processed_at ? `Processed ${new Date(payslip.processed_at).toLocaleDateString("en-IN")}. ` : ""}This is a computer-generated payslip.</p>
    </article>
  );
}

function PayslipDialog({ payslip, onClose }: { payslip: Payslip; onClose: () => void }) {
  const school = useCardSchool();
  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card acad-modal payslip-modal extras-print" role="dialog" aria-modal="true" aria-label="Payslip">
        <PayslipView payslip={payslip} schoolName={school.name} />
        <div className="resource-actions acad-modal-actions ops-no-print">
          <button className="btn-pill btn-pill-green" type="button" onClick={() => window.print()}>Download PDF / print</button>
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ---------- Reports ----------

export function PayrollReportsPage() {
  return (
    <ExtrasPage title="Payroll reports" description="Each month's payroll: how many payslips were processed, pending or failed, and the total paid." icon={icon} tabs={PAYROLL_TABS} note={note()}>
      <ReportsBody />
    </ExtrasPage>
  );
}

function ReportsBody() {
  const toast = useToast();
  const [year, setYear] = useState(new Date().getFullYear());
  const summary = useOptions(useCallback(() => payrollService().summary(year), [year]));
  const rows = summary.options.map((row) => ({ ...row, id: Number(row.month.replace("-", "")) }));
  const columns: Column<(typeof rows)[number]>[] = [
    { key: "month", label: "Month", render: (row) => <strong>{monthLabel(row.month)}</strong> },
    { key: "processed", label: "Processed", render: (row) => <Chip tone="green">{row.processed}</Chip> },
    { key: "pending", label: "Pending", render: (row) => <Chip tone={row.pending ? "amber" : "grey"}>{row.pending}</Chip> },
    { key: "failed", label: "Failed", render: (row) => <Chip tone={row.failed ? "red" : "grey"}>{row.failed}</Chip> },
    { key: "total", label: "Total net paid", render: (row) => money(row.total_net) },
  ];
  return (
    <>
      <div className="school-filters">
        <select aria-label="Year" value={year} onChange={(event) => setYear(Number(event.target.value))}>
          {[0, 1, 2].map((back) => new Date().getFullYear() - back).map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          disabled={!rows.length}
          onClick={() => {
            downloadText(`payroll-${year}.csv`, toCsv(rows, [
              { label: "Month", value: (row) => row.month },
              { label: "Processed", value: (row) => row.processed },
              { label: "Pending", value: (row) => row.pending },
              { label: "Failed", value: (row) => row.failed },
              { label: "Total net paid", value: (row) => row.total_net },
            ]));
            toast("success", "Report downloaded.");
          }}
        >
          Export CSV
        </button>
      </div>
      <div className="teach-stats">
        <Stat label={`Paid in ${year}`} value={money(rows.reduce((sum, row) => sum + row.total_net, 0))} tone="green" />
        <Stat label="Failed payslips" value={rows.reduce((sum, row) => sum + row.failed, 0)} tone="red" />
      </div>
      <ErrorAlert error={summary.error} onRetry={() => void summary.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={rows} loading={summary.loading} emptyText="No payroll for this year yet." />
      </div>
      <p className="muted">For one employee's or department's payslips, use the filters on the Payslips tab.</p>
    </>
  );
}
