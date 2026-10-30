"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextField } from "@/components/academics/Fields";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage, StudentSearch } from "@/components/extras/Frame";
import { IdCardView, useCardSchool, type CardData } from "@/components/extras/IdCard";
import { cardOf, fillTemplate } from "@/components/extras/Tools";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { errorMessage, listAll } from "@/lib/academics";
import { create, displayValue, getOne, listRows, staffDirectory, type Raw, type StaffRef } from "@/lib/extras/api";
import { peopleService, type StudentRow } from "@/lib/people";
import { num, optNum, optStr, settleLimited, str } from "@/lib/teaching/client";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { Chip } from "@/components/teaching/Frame";
import { PdfDownload } from "@/components/operations/PdfDownload";
import { refNames } from "@/lib/extras/refs";
import { IconBook } from "@/lib/icons";

const icon = <IconBook width={18} height={18} />;

export const DOCUMENT_TABS = [
  { href: "/school/certificate-assign", label: "Issue certificates" },
  { href: "/school/certificate-template", label: "Certificate templates" },
  { href: "/school/student-id-card", label: "Student ID card" },
  { href: "/school/staff-id-card", label: "Staff ID card" },
  { href: "/school/bulk-id-cards", label: "Bulk ID cards" },
  { href: "/school/id-card-settings", label: "ID card settings" },
];

function today() {
  return new Date().toISOString().slice(0, 10);
}

/** Placeholder values for a student's certificate. */
export function studentValues(student: Pick<StudentRow, "name" | "admission_no" | "class_name" | "section_name" | "roll_number" | "guardian_name" | "session_name">): Record<string, string> {
  return {
    name: student.name,
    student_name: student.name,
    admission_no: student.admission_no,
    class: student.class_name,
    section: student.section_name,
    roll_number: student.roll_number ? String(student.roll_number) : "",
    guardian: student.guardian_name ?? "",
    session: student.session_name ?? "",
    date: today(),
  };
}

/** Placeholder values for a staff member's certificate. */
export function staffValues(person: Pick<StaffRef, "name" | "designation" | "employee_code" | "department">): Record<string, string> {
  return { name: person.name, staff_name: person.name, designation: person.designation, employee_id: person.employee_code ?? "", department: person.department ?? "", date: today() };
}

type Issued = { key: string; title: string; text: string; number: string | null; person: string; id?: number; verifyUrl?: string | null };

function CertificateSheet({ items, schoolName }: { items: Issued[]; schoolName: string }) {
  return (
    <div className="cert-sheet">
      {items.map((item) => (
        <article key={item.key} className="cert-page">
          <p className="cert-school">{schoolName}</p>
          <h2>{item.title}</h2>
          {item.number ? <p className="muted">Certificate no. {item.number}</p> : null}
          <p className="cert-text">{item.text || "This template has no text."}</p>
          {item.verifyUrl ? <p className="cert-verify muted">Check this certificate at {item.verifyUrl}</p> : null}
          <div className="cert-sign">
            <span>Date: {today()}</span>
            <span>Principal</span>
          </div>
        </article>
      ))}
    </div>
  );
}

// ---------- Certificates ----------

export function CertificatesPage() {
  return (
    <ExtrasPage
      title="Issue certificates"
      description="Pick a template and a student or staff member, check the preview, then issue and print. Or issue for a whole section at once."
      icon={icon}
      tabs={DOCUMENT_TABS}
      note="Placeholders: {name}, {admission_no}, {class}, {section}, {roll_number}, {guardian}, {session} for students; {name}, {designation}, {employee_id}, {department} for staff; {certificate_no} and {date} for both."
    >
      <CertificatesBody />
    </ExtrasPage>
  );
}

function CertificatesBody() {
  const [mode, setMode] = useState<"one" | "bulk" | "issued">("one");
  const templates = useOptions(useCallback(() => listRows("/certificate-templates") as Promise<(Raw & { id: number })[]>, []));
  return (
    <>
      <nav className="acad-tabs" aria-label="How many">
        <button type="button" className={`acad-tab${mode === "one" ? " is-active" : ""}`} aria-pressed={mode === "one"} onClick={() => setMode("one")}>One person</button>
        <button type="button" className={`acad-tab${mode === "bulk" ? " is-active" : ""}`} aria-pressed={mode === "bulk"} onClick={() => setMode("bulk")}>A whole section</button>
        <button type="button" className={`acad-tab${mode === "issued" ? " is-active" : ""}`} aria-pressed={mode === "issued"} onClick={() => setMode("issued")}>Issued certificates</button>
      </nav>
      <ErrorAlert error={templates.error} onRetry={() => void templates.reload()} />
      {!templates.loading && !templates.options.length ? <div className="alert alert-info">Add a certificate template first, under Certificate templates.</div> : null}
      {mode === "one" ? <OneCertificate templates={templates.options} loading={templates.loading} /> : mode === "bulk" ? <BulkCertificates templates={templates.options} loading={templates.loading} /> : <IssuedCertificates templates={templates.options} />}
    </>
  );
}

function TemplatePicker({ templates, loading, value, onChange }: { templates: Raw[]; loading: boolean; value: string; onChange: (value: string) => void }) {
  return <SelectField id="ct-template" label="Template" required placeholder="Choose a template" loading={loading} value={value} onChange={onChange} options={templates.map((row) => ({ value: str(row.id), label: `${str(row.name)}${row.template_type ? ` (${str(row.template_type)})` : ""}` }))} />;
}

function OneCertificate({ templates, loading }: { templates: Raw[]; loading: boolean }) {
  const toast = useToast();
  const school = useCardSchool();
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [kind, setKind] = useState<"student" | "staff">("student");
  const [templateId, setTemplateId] = useState("");
  const [student, setStudent] = useState<StudentRow | null>(null);
  const [staffId, setStaffId] = useState("");
  const [number, setNumber] = useState("");
  const [issued, setIssued] = useState<Issued | null>(null);
  const [busy, setBusy] = useState(false);
  const template = templates.find((row) => str(row.id) === templateId);
  const person = people.options.find((row) => String(row.staff_id) === staffId);
  const values = kind === "student" ? (student ? studentValues(student) : null) : person ? staffValues(person) : null;
  const preview = template && values ? fillTemplate(str(template.body_text), { ...values, certificate_no: number.trim() || "(given when issued)" }) : "";

  async function issue() {
    if (!template || !values) return;
    setBusy(true);
    try {
      if (kind === "student" && student) {
        const row = await create("/certificates/issue", { template_id: Number(templateId), student_id: student.id, certificate_no: number.trim() || null, data: values });
        const certificateNo = str(row.certificate_no);
        setIssued({ key: certificateNo, id: num(row.id), verifyUrl: optStr(row.verify_url), title: str(template.name), number: certificateNo, person: student.name, text: fillTemplate(str(template.body_text), { ...values, certificate_no: certificateNo }) });
        toast("success", `Certificate ${certificateNo} issued to ${student.name}.`);
      } else if (person) {
        const row = await create("/certificates/issue-staff", { template_id: Number(templateId), staff_id: person.staff_id, certificate_no: number.trim() || null, data: values });
        const certificateNo = str(row.certificate_no);
        setIssued({ key: certificateNo, id: num(row.id), verifyUrl: optStr(row.verify_url), title: str(template.name), number: certificateNo, person: person.name, text: fillTemplate(str(template.body_text), { ...values, certificate_no: certificateNo }) });
        toast("success", `Certificate ${certificateNo} issued to ${person.name}.`);
      }
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to issue the certificate."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cert-layout">
      <section className="resource-card resource-fields ops-no-print" aria-label="Certificate details">
        <SelectField id="ct-kind" label="For" required value={kind} onChange={(value) => { setKind(value as "student" | "staff"); setIssued(null); }} options={[{ value: "student", label: "A student" }, { value: "staff", label: "A staff member" }]} />
        <TemplatePicker templates={templates} loading={loading} value={templateId} onChange={(value) => { setTemplateId(value); setIssued(null); }} />
        {kind === "student" ? (
          <StudentSearch id="ct-student" label="Student" required value={student} onChange={(next) => { setStudent(next); setIssued(null); }} />
        ) : (
          <SelectField id="ct-staff" label="Staff member" required placeholder="Choose someone" loading={people.loading} value={staffId} onChange={(value) => { setStaffId(value); setIssued(null); }} options={people.options.map((row) => ({ value: String(row.staff_id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }))} />
        )}
        <TextField id="ct-number" label="Certificate number" maxLength={64} value={number} onChange={setNumber} hint="Leave empty to number it automatically." />
        <div className="field-span page-actions">
          <button className="btn-pill btn-pill-green" type="button" disabled={!template || !values || busy} onClick={() => void issue()}>
            {busy ? "Issuing…" : "Issue certificate"}
          </button>
          {issued?.id ? <PdfDownload path={`/school-admin/certificates/${issued.id}/pdf`} fileName={`certificate-${issued.number ?? issued.id}.pdf`} /> : null}
          {issued ? <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => window.print()}>Print</button> : null}
        </div>
      </section>
      <section className={`resource-card cert-preview${issued ? " extras-print" : ""}`} aria-label="Preview">
        {issued ? (
          <CertificateSheet items={[issued]} schoolName={school.name} />
        ) : preview ? (
          <>
            <p className="field-label ops-no-print">Preview</p>
            <CertificateSheet items={[{ key: "preview", title: str(template?.name), number: number.trim() || null, person: "", text: preview }]} schoolName={school.name} />
          </>
        ) : (
          <div className="empty-state">Choose a template and a person to see the certificate.</div>
        )}
      </section>
    </div>
  );
}

function BulkCertificates({ templates, loading }: { templates: Raw[]; loading: boolean }) {
  const toast = useToast();
  const school = useCardSchool();
  const [filter, setFilter] = usePlacementFilter();
  const [templateId, setTemplateId] = useState("");
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [issued, setIssued] = useState<Issued[]>([]);
  const [failures, setFailures] = useState<string[]>([]);
  const ready = Boolean(filter.sessionId && filter.sectionId);
  const students = useOptions(
    useCallback(
      () => (ready ? listAll((page) => peopleService("students").listStudents({ page, pageSize: 50, sessionYearId: filter.sessionId, classSectionId: filter.sectionId, status: "1", sort: "name" })) : Promise.resolve([] as StudentRow[])),
      [ready, filter.sessionId, filter.sectionId],
    ),
  );
  const template = templates.find((row) => str(row.id) === templateId);

  async function run() {
    if (!template) return;
    const list = students.options;
    setIssued([]);
    setFailures([]);
    setProgress({ done: 0, total: list.length });
    const done: Issued[] = [];
    const failed: string[] = [];
    // One at a time: the server numbers certificates in order.
    for (const [index, student] of list.entries()) {
      const values = studentValues(student);
      try {
        const row = await create("/certificates/issue", { template_id: Number(templateId), student_id: student.id, data: values });
        done.push({ key: str(row.certificate_no) || `s-${student.id}`, title: str(template.name), number: str(row.certificate_no) || null, person: student.name, text: fillTemplate(str(template.body_text), { ...values, certificate_no: str(row.certificate_no) }) });
      } catch (caught) {
        failed.push(`${student.name}: ${errorMessage(caught, "Couldn't be issued.")}`);
      }
      setProgress({ done: index + 1, total: list.length });
    }
    setIssued(done);
    setFailures(failed);
    setProgress(null);
    toast(failed.length ? "error" : "success", `${done.length} of ${list.length} certificates issued.`);
  }

  return (
    <>
      <div className="resource-card ops-no-print">
        <div className="school-filters">
          <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={setFilter} />
        </div>
        <div className="resource-fields">
          <TemplatePicker templates={templates} loading={loading} value={templateId} onChange={setTemplateId} />
        </div>
        <div className="page-actions">
          <button className="btn-pill btn-pill-green" type="button" disabled={!template || !students.options.length || progress !== null} onClick={() => void run()}>
            {progress ? `Issuing ${progress.done} of ${progress.total}…` : `Issue for ${students.options.length} student${students.options.length === 1 ? "" : "s"}`}
          </button>
          {issued.length ? <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => window.print()}>Download PDF / print all</button> : null}
        </div>
        {progress ? <progress className="bulk-progress" value={progress.done} max={progress.total} /> : null}
        {!ready ? <p className="muted">Choose a session, class and section.</p> : null}
        <ErrorAlert error={students.error} onRetry={() => void students.reload()} />
        {failures.length ? (
          <div className="alert alert-danger">
            <ul className="teach-list">{failures.map((line) => <li key={line}>{line}</li>)}</ul>
          </div>
        ) : null}
      </div>
      {issued.length ? (
        <section className="resource-card bulk-print-sheet extras-print" aria-label="Issued certificates">
          <CertificateSheet items={issued} schoolName={school.name} />
        </section>
      ) : null}
    </>
  );
}

// ---------- Bulk ID cards ----------

export function BulkIdCardsPage() {
  return (
    <ExtrasPage title="Bulk ID cards" description="Make ID cards for a whole section or for all staff, then print them together." icon={icon} tabs={DOCUMENT_TABS}>
      <BulkCardsBody />
    </ExtrasPage>
  );
}

/** Student card front lines and placeholder values. */
export function studentCard(student: StudentRow, payload: Raw): CardData {
  return cardOf(
    "student",
    payload,
    [
      ["Class", `${student.class_name} ${student.section_name}`],
      ["Roll no.", student.roll_number ? String(student.roll_number) : "—"],
      ["Admission no.", student.admission_no],
      ["Guardian", student.guardian_name ?? ""],
      ["Session", student.session_name ?? ""],
    ],
    studentValues(student),
  );
}

export function staffCard(person: StaffRef, payload: Raw): CardData {
  return cardOf(
    "staff",
    payload,
    [
      ["Designation", str(payload.designation) || person.designation],
      ["Employee ID", str(payload.employee_id) || person.employee_code || ""],
      ["Department", str(payload.department) || person.department || ""],
    ],
    staffValues(person),
  );
}

function BulkCardsBody() {
  const toast = useToast();
  const school = useCardSchool();
  const [kind, setKind] = useState<"student" | "staff">("student");
  const [filter, setFilter] = usePlacementFilter();
  const [department, setDepartment] = useState("");
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const ready = kind === "staff" || Boolean(filter.sessionId && filter.sectionId);
  const students = useOptions(
    useCallback(
      () => (kind === "student" && filter.sessionId && filter.sectionId ? listAll((page) => peopleService("students").listStudents({ page, pageSize: 50, sessionYearId: filter.sessionId, classSectionId: filter.sectionId, status: "1", sort: "name" })) : Promise.resolve([] as StudentRow[])),
      [kind, filter.sessionId, filter.sectionId],
    ),
  );
  const departments = useMemo(() => [...new Set(people.options.map((row) => row.department ?? "").filter(Boolean))].sort(), [people.options]);
  const staffList = people.options.filter((row) => !department || row.department === department);
  const count = kind === "student" ? students.options.length : staffList.length;
  const [cards, setCards] = useState<{ key: string; card: CardData }[]>([]);
  const [failures, setFailures] = useState<string[]>([]);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);

  async function generate() {
    setCards([]);
    setFailures([]);
    const jobs =
      kind === "student"
        ? students.options.map((student) => ({ label: student.name, key: `s-${student.id}`, load: () => getOne(`/students/${student.id}/id-card`).then((payload) => studentCard(student, payload)) }))
        : staffList.map((person) => ({ label: person.name, key: `t-${person.staff_id}`, load: () => getOne(`/staff/${person.staff_id}/id-card`).then((payload) => staffCard(person, payload)) }));
    let done = 0;
    setProgress({ done, total: jobs.length });
    const results = await settleLimited(
      jobs.map((job) => async () => {
        try {
          return await job.load();
        } finally {
          done += 1;
          setProgress({ done, total: jobs.length });
        }
      }),
      4,
    );
    const made: { key: string; card: CardData }[] = [];
    const failed: string[] = [];
    results.forEach((result, index) => {
      if (result.ok) made.push({ key: jobs[index].key, card: result.value });
      else failed.push(`${jobs[index].label}: ${errorMessage(result.error, "Couldn't be loaded.")}`);
    });
    setCards(made);
    setFailures(failed);
    setProgress(null);
    toast(failed.length ? "error" : "success", `${made.length} of ${jobs.length} ID cards ready.`);
  }

  return (
    <>
      <div className="resource-card ops-no-print">
        <div className="school-filters">
          <select aria-label="Cards for" value={kind} onChange={(event) => { setKind(event.target.value as "student" | "staff"); setCards([]); setFailures([]); }}>
            <option value="student">Students in a section</option>
            <option value="staff">Staff</option>
          </select>
          {kind === "student" ? (
            <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={setFilter} />
          ) : (
            <select aria-label="Department" value={department} onChange={(event) => setDepartment(event.target.value)}>
              <option value="">All departments</option>
              {departments.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          )}
        </div>
        <div className="page-actions">
          <button className="btn-pill btn-pill-green" type="button" disabled={!ready || !count || progress !== null} onClick={() => void generate()}>
            {progress ? `Making ${progress.done} of ${progress.total}…` : `Make ${count} ID card${count === 1 ? "" : "s"}`}
          </button>
          {cards.length ? <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => window.print()}>Download PDF / print all</button> : null}
        </div>
        {progress ? <progress className="bulk-progress" value={progress.done} max={progress.total} /> : null}
        {!ready ? <p className="muted">Choose a session, class and section.</p> : null}
        <ErrorAlert error={students.error ?? people.error} onRetry={() => void students.reload()} />
        {failures.length ? (
          <div className="alert alert-danger">
            <ul className="teach-list">{failures.map((line) => <li key={line}>{line}</li>)}</ul>
          </div>
        ) : null}
      </div>
      {cards.length ? (
        <section className="resource-card bulk-print-sheet extras-print" aria-label="ID cards">
          <div className="bulk-cards">
            {cards.map((item) => <IdCardView key={item.key} card={item.card} school={school} />)}
          </div>
        </section>
      ) : null}
    </>
  );
}

// ---------- Issued certificates ----------

type IssuedRow = Raw & { id: number };

function IssuedCertificates({ templates }: { templates: Raw[] }) {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const list = useOptions(useCallback(() => listRows("/certificates", { status: status || undefined }) as Promise<IssuedRow[]>, [status]));
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [students, setStudents] = useState<Map<number, string>>(new Map());
  const [revoking, setRevoking] = useState<IssuedRow | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const ids = list.options.map((row) => num(row.student_id)).filter(Boolean);
    if (!ids.length) return;
    void refNames("student", ids).then(setStudents).catch(() => undefined);
  }, [list.options]);

  const who = (row: IssuedRow) =>
    optNum(row.student_id) ? students.get(num(row.student_id)) ?? `Student #${num(row.student_id)}` : people.options.find((person) => person.staff_id === num(row.staff_id))?.name ?? `Staff #${num(row.staff_id)}`;
  const columns: Column<IssuedRow>[] = [
    { key: "no", label: "Certificate no.", render: (row) => <strong>{str(row.certificate_no)}</strong> },
    { key: "who", label: "Issued to", render: (row) => <div>{who(row)}<div className="muted">{optNum(row.student_id) ? "Student" : "Staff"}</div></div> },
    { key: "template", label: "Template", render: (row) => str(templates.find((item) => num(item.id) === num(row.template_id))?.name, "—") },
    { key: "issued", label: "Issued", render: (row) => displayValue(row.issued_at) },
    { key: "status", label: "Status", render: (row) => (optStr(row.revoked_at) || str(row.status) === "revoked" ? <Chip tone="red">Revoked</Chip> : <Chip tone="green">Valid</Chip>) },
  ];
  return (
    <>
      <div className="school-filters">
        <select aria-label="Status" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All certificates</option>
          <option value="issued">Valid</option>
          <option value="revoked">Revoked</option>
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.options}
          loading={list.loading}
          emptyText="No certificates issued yet."
          actions={(row) => (
            <>
              <PdfDownload className="link-btn" label="PDF" path={`/school-admin/certificates/${row.id}/pdf`} fileName={`certificate-${str(row.certificate_no) || row.id}.pdf`} />
              {optStr(row.revoked_at) || str(row.status) === "revoked" ? null : (
                <button className="link-btn danger" type="button" onClick={() => setRevoking(row)}>Revoke</button>
              )}
            </>
          )}
        />
      </div>
      {revoking ? (
        <ConfirmDialog
          title="Revoke this certificate?"
          body={`${str(revoking.certificate_no)} will show as revoked to anyone who checks it. This can't be undone.`}
          confirmLabel="Revoke"
          tone="danger"
          pending={pending}
          onCancel={() => setRevoking(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await create(`/certificates/${revoking.id}/revoke`, {});
              toast("success", "Certificate revoked.");
              void list.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to revoke the certificate."));
            } finally {
              setPending(false);
              setRevoking(null);
            }
          }}
        />
      ) : null}
    </>
  );
}
