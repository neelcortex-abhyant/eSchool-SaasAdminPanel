"use client";

/**
 * Teacher and staff pages share these components. `kind` picks the API path and the few
 * differences: teachers need a qualification and show their class/subject assignments.
 */
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useMemo, useRef, useState, type FormEvent } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, StatusToggle, TextAreaField, TextField } from "@/components/academics/Fields";
import { StatusBadge } from "@/components/academics/StatusBadge";
import { useToast } from "@/components/academics/Toasts";
import { useDebounced, useFormErrors, useOptions, usePagedList } from "@/components/academics/hooks";
import { DocumentPicker, PhotoPicker, StoredDocuments, uploadFiles, type PendingDocument } from "@/components/people/Files";
import { PasswordField } from "@/components/people/PasswordField";
import { PeoplePage, flashMessage, routeId } from "@/components/people/PeoplePage";
import { Avatar, FormSection, InfoCard, ProfileHeader, ProfileSkeleton, useRecord } from "@/components/people/Profile";
import { StatusAction } from "@/components/people/StatusAction";
import { academicsService, listAll } from "@/lib/academics";
import {
  GENDERS,
  formatDate,
  peopleService,
  peopleSupport,
  type Employee,
  type EmployeeInput,
  type EmployeeKind,
  type EmployeeRow,
  type EmploymentType,
  type PeopleSupport,
  type Gender,
} from "@/lib/people";
import { email, focusFirstError, phone, required, todayIso, type Errors } from "@/lib/people/validate";
import { IconStaff, IconTeacher } from "@/lib/icons";

const PAGE_SIZE = 10;
const assignmentService = academicsService("assignments");

type Copy = {
  plural: string;
  singular: string;
  title: string;
  description: string;
  addLabel: string;
  base: string;
  documents: string[];
  deactivateEffect: (name: string) => string;
};

export const EMPLOYEE_COPY: Record<EmployeeKind, Copy> = {
  teachers: {
    plural: "teachers",
    singular: "teacher",
    title: "Teachers",
    description: "Teaching staff, their departments and the classes they teach.",
    addLabel: "Add teacher",
    base: "/school/teachers",
    documents: ["Resume", "Degree certificate", "B.Ed. certificate", "ID proof", "Address proof", "Experience letter"],
    deactivateEffect: (name) => `${name} won't be able to sign in or get new class assignments. Their existing assignments and records are kept.`,
  },
  staff: {
    plural: "staff",
    singular: "staff member",
    title: "Staff",
    description: "Non-teaching employees such as office, accounts, library and transport staff.",
    addLabel: "Add staff member",
    base: "/school/staff",
    documents: ["Resume", "ID proof", "Address proof", "Driving licence", "Experience letter"],
    deactivateEffect: (name) => `${name} won't be able to sign in. Their records are kept.`,
  },
};

function KindIcon({ kind }: { kind: EmployeeKind }) {
  return kind === "teachers" ? <IconTeacher width={18} height={18} /> : <IconStaff width={18} height={18} />;
}

// ---------- Listing ----------

export function EmployeeListPage({ kind }: { kind: EmployeeKind }) {
  const copy = EMPLOYEE_COPY[kind];
  return (
    <PeoplePage
      module={kind}
      title={copy.title}
      description={copy.description}
      icon={<KindIcon kind={kind} />}
      actions={
        <Link className="btn-pill btn-pill-green" href={`${copy.base}/new`}>
          {copy.addLabel}
        </Link>
      }
    >
      <EmployeeList kind={kind} />
    </PeoplePage>
  );
}

function EmployeeList({ kind }: { kind: EmployeeKind }) {
  const copy = EMPLOYEE_COPY[kind];
  const service = peopleService(kind);
  const support = peopleSupport(kind);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [department, setDepartment] = useState("");
  const [employmentType, setEmploymentType] = useState<EmploymentType | "">("");
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [page, setPage] = useState(1);

  const departments = useOptions(useCallback(() => service.listDepartments(kind), [service, kind]));
  const loader = useCallback(
    () => service.listEmployees(kind, { page, pageSize: PAGE_SIZE, q: search, status, department, employmentType }),
    [service, kind, page, search, status, department, employmentType],
  );
  const { data, loading, error, reload } = usePagedList(loader);
  const filtered = Boolean(search || status || department || employmentType);

  const columns = useMemo<Column<EmployeeRow>[]>(
    () => [
      ...(support.details ? [{ key: "code", label: "Employee ID", render: (row: EmployeeRow) => <code className="people-code">{row.employee_code}</code> }] : []),
      {
        key: "name",
        label: "Name",
        render: (row) => (
          <Link className="people-name-cell" href={`${copy.base}/${row.id}`}>
            <Avatar name={row.name} photoUrl={row.photo_url} size={32} />
            <span>{row.name}</span>
          </Link>
        ),
      },
      ...(support.details
        ? [{ key: "role", label: "Department", render: (row: EmployeeRow) => <span>{row.department}<span className="muted people-sub">{row.designation}</span></span> }]
        : []),
      { key: "contact", label: "Contact", render: (row) => <span>{row.email}<span className="muted people-sub">{row.mobile}</span></span> },
      ...(support.details
        ? [
            { key: "joined", label: "Joined", render: (row: EmployeeRow) => formatDate(row.joining_date) },
            { key: "type", label: "Employment", render: (row: EmployeeRow) => employmentText(support, row.employment_type) },
          ]
        : []),
      { key: "status", label: "Status", render: (row) => <StatusBadge active={row.status === 1} /> },
    ],
    [copy.base, support],
  );

  return (
    <>
      <div className="school-filters">
        <input
          type="search"
          aria-label={`Search ${copy.plural}`}
          placeholder="Search by name, employee ID, email or phone"
          value={searchInput}
          onChange={(event) => {
            setSearchInput(event.target.value);
            setPage(1);
          }}
        />
        {support.employeeFilters ? (
          <>
            <select aria-label="Filter by department" value={department} onChange={(event) => { setDepartment(event.target.value); setPage(1); }}>
              <option value="">{departments.loading ? "Loading departments…" : "All departments"}</option>
              {departments.options.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <select aria-label={`Filter by ${support.employmentLabel.toLowerCase()}`} value={employmentType} onChange={(event) => { setEmploymentType(event.target.value as EmploymentType | ""); setPage(1); }}>
              <option value="">{`All ${support.employmentLabel.toLowerCase()}es`.replace("typees", "types")}</option>
              {support.employmentOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </>
        ) : null}
        <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as "" | "0" | "1"); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
      </div>

      <ErrorAlert error={error ?? departments.error} onRetry={() => { void reload(); void departments.reload(); }} />

      {!error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={loading}
            emptyText={filtered ? `No ${copy.plural} match these filters.` : `No ${copy.plural} yet. Use ${copy.addLabel} to add the first one.`}
            actions={(row) => (
              <>
                <Link className="link-btn" href={`${copy.base}/${row.id}`}>
                  View<span className="acad-sr"> {row.name}</span>
                </Link>
                {support.edit ? (
                  <Link className="link-btn" href={`${copy.base}/${row.id}/edit`}>
                    Edit<span className="acad-sr"> {row.name}</span>
                  </Link>
                ) : null}
                {support.status ? (
                  <StatusAction
                    variant="link"
                    name={row.name}
                    noun={copy.singular}
                    active={row.status === 1}
                    deactivateEffect={copy.deactivateEffect(row.name)}
                    change={(next) => service.setEmployeeStatus(kind, row.id, next)}
                    onChanged={() => reload()}
                  />
                ) : null}
              </>
            )}
          />
          <Pagination page={data?.page ?? page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
        </div>
      ) : null}
    </>
  );
}

/** The label for an employment value: "On leave" for on_leave, or the value itself. */
function employmentText(support: PeopleSupport, value: string): string {
  return support.employmentOptions.find((option) => option.value === value)?.label ?? value;
}

// ---------- Form ----------

type FormValues = {
  employee_code: string;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  gender: Gender | "";
  dob: string;
  qualification: string;
  department: string;
  designation: string;
  joining_date: string;
  employment_type: EmploymentType | "";
  password: string;
  current_address: string;
  active: boolean;
};

function initialValues(employee: Employee | null): FormValues {
  return {
    employee_code: employee?.employee_code ?? "",
    first_name: employee?.first_name ?? "",
    last_name: employee?.last_name ?? "",
    email: employee?.email ?? "",
    mobile: employee?.mobile ?? "",
    gender: employee?.gender ?? "",
    dob: employee?.dob ?? "",
    qualification: employee?.qualification ?? "",
    department: employee?.department ?? "",
    designation: employee?.designation ?? "",
    joining_date: employee?.joining_date ?? todayIso(),
    employment_type: employee?.employment_type ?? "",
    password: "",
    current_address: employee?.current_address ?? "",
    active: employee ? employee.status === 1 : true,
  };
}

export type EmployeeFormResult = { input: EmployeeInput; photo: File | null; documents: PendingDocument[] };

export function EmployeeForm({
  kind,
  employee,
  departments,
  onSave,
  onRemoveDocument,
}: {
  kind: EmployeeKind;
  employee: Employee | null;
  departments: string[];
  onSave: (result: EmployeeFormResult) => Promise<void>;
  onRemoveDocument?: Parameters<typeof StoredDocuments>[0]["onRemove"];
}) {
  const copy = EMPLOYEE_COPY[kind];
  const support = peopleSupport(kind);
  const formRef = useRef<HTMLFormElement>(null);
  const [values, setValues] = useState<FormValues>(() => initialValues(employee));
  const [photo, setPhoto] = useState<File | null>(null);
  const [documents, setDocuments] = useState<PendingDocument[]>([]);
  const [saving, setSaving] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const errors = useFormErrors();
  const fe = errors.fieldErrors;
  const listId = `${kind}-departments`;

  function set<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function check(): Errors {
    const invalid: Errors = {};
    // The live backend allows employees without an ID, so only the sample data requires one on edit.
    if (employee && support.details && !support.password) required(invalid, "employee_code", values.employee_code, "Enter the employee ID.");
    if (!employee && support.password && values.password.length < 8) invalid.password = "Enter a password of at least 8 characters.";
    required(invalid, "first_name", values.first_name, "Enter the first name.");
    required(invalid, "last_name", values.last_name, "Enter the last name.");
    email(invalid, "email", values.email, true);
    phone(invalid, "mobile", values.mobile, true);
    if (kind === "teachers") required(invalid, "qualification", values.qualification, "Enter the teacher's qualification.");
    if (!support.details) return invalid; // the live server stores only name, contact and qualification
    required(invalid, "department", values.department, "Enter or choose a department.");
    required(invalid, "designation", values.designation, "Enter the designation.");
    if (!values.joining_date) invalid.joining_date = "Enter the joining date.";
    if (!values.employment_type) invalid.employment_type = `Choose the ${support.employmentLabel.toLowerCase()}.`;
    if (values.dob && values.dob > todayIso()) invalid.dob = "Date of birth can't be in the future.";
    else if (values.dob && values.joining_date && values.joining_date <= values.dob) invalid.joining_date = "Joining date must be after the date of birth.";
    return invalid;
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    const invalid = check();
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("Check the highlighted fields.");
      focusFirstError(formRef.current);
      return;
    }
    if (employee?.status === 1 && !values.active) setConfirmDeactivate(true);
    else void save();
  }

  async function save() {
    setConfirmDeactivate(false);
    errors.clear();
    setSaving(true);
    const input: EmployeeInput = {
      employee_code: values.employee_code.trim() || undefined,
      first_name: values.first_name.trim(),
      last_name: values.last_name.trim(),
      email: values.email.trim(),
      mobile: values.mobile.trim(),
      gender: values.gender || null,
      dob: values.dob || null,
      qualification: values.qualification.trim() || null,
      department: values.department.trim(),
      designation: values.designation.trim(),
      joining_date: values.joining_date,
      employment_type: values.employment_type as EmploymentType,
      password: !employee && support.password ? values.password : undefined,
      current_address: values.current_address.trim() || null,
      status: values.active ? 1 : 0,
    };
    try {
      await onSave({ input, photo, documents });
    } catch (caught) {
      errors.fromError(caught, `Unable to save the ${copy.singular}.`);
      setSaving(false);
      focusFirstError(formRef.current);
    }
  }

  const name = `${values.first_name} ${values.last_name}`.trim();
  return (
    <form ref={formRef} className="people-form" onSubmit={onSubmit} noValidate aria-busy={saving}>
      {errors.formError ? (
        <div className="alert alert-danger" role="alert">
          {errors.formError}
        </div>
      ) : null}

      <FormSection title="Personal details">
        <TextField id="emp-first-name" label="First name" required maxLength={128} value={values.first_name} onChange={(v) => set("first_name", v)} error={fe.first_name} />
        <TextField id="emp-last-name" label="Last name" required maxLength={128} value={values.last_name} onChange={(v) => set("last_name", v)} error={fe.last_name} />
        {support.details ? (
          <>
            <SelectField id="emp-gender" label="Gender" placeholder="Choose" value={values.gender} onChange={(v) => set("gender", v as Gender)} options={GENDERS.map((g) => ({ value: g.value, label: g.label }))} error={fe.gender} />
            <TextField id="emp-dob" label="Date of birth" type="date" max={todayIso()} value={values.dob} onChange={(v) => set("dob", v)} error={fe.dob} hint="Optional." />
          </>
        ) : null}
        {support.files ? <PhotoPicker id="emp-photo" name={name} currentUrl={employee?.photo_url ?? null} file={photo} onChange={setPhoto} error={fe.file} /> : null}
      </FormSection>

      <FormSection title="Contact">
        <TextField id="emp-email" label="Email" type="email" required autoComplete="off" value={values.email} onChange={(v) => set("email", v)} error={fe.email} hint="Used to sign in. Must be unique in your school." />
        <TextField id="emp-mobile" label="Phone" type="tel" required value={values.mobile} onChange={(v) => set("mobile", v)} error={fe.mobile} />
        {!employee && support.password ? (
          <PasswordField
            id="emp-password"
            label="Sign-in password"
            value={values.password}
            onChange={(v) => set("password", v)}
            error={fe.password}
            hint={`At least 8 characters. Copy it and give it to the ${copy.singular}; they sign in with their email and this password.`}
          />
        ) : null}
        {support.details ? (
          <TextAreaField id="emp-address" label="Address" span maxLength={512} value={values.current_address} onChange={(v) => set("current_address", v)} error={fe.current_address} />
        ) : null}
      </FormSection>

      <FormSection title="Employment">
        {support.details ? (
          <>
            <TextField
              id="emp-code"
              label="Employee ID"
              required={Boolean(employee) && !support.password}
              maxLength={32}
              placeholder={employee ? undefined : "Generated automatically"}
              value={values.employee_code}
              onChange={(v) => set("employee_code", v)}
              error={fe.employee_code}
              hint={employee ? undefined : "Leave blank to use the next ID."}
            />
            <TextField id="emp-joining" label="Joining date" type="date" required value={values.joining_date} onChange={(v) => set("joining_date", v)} error={fe.joining_date} />
            <div className="form-field">
              <label htmlFor="emp-department">Department *</label>
              <input
                id="emp-department"
                list={listId}
                value={values.department}
                maxLength={128}
                className={fe.department ? "invalid" : undefined}
                aria-invalid={Boolean(fe.department)}
                aria-describedby={fe.department ? "emp-department-error" : undefined}
                onChange={(event) => set("department", event.target.value)}
              />
              <datalist id={listId}>
                {departments.map((department) => (
                  <option key={department} value={department} />
                ))}
              </datalist>
              {fe.department ? (
                <p className="field-error" id="emp-department-error">
                  {fe.department}
                </p>
              ) : null}
            </div>
            <TextField id="emp-designation" label="Designation" required maxLength={128} value={values.designation} onChange={(v) => set("designation", v)} error={fe.designation} />
          </>
        ) : null}
        <TextField
          id="emp-qualification"
          label="Qualification"
          required={kind === "teachers"}
          maxLength={255}
          value={values.qualification}
          onChange={(v) => set("qualification", v)}
          error={fe.qualification}
          hint={kind === "teachers" ? "For example: M.Sc. Mathematics, B.Ed." : "Optional."}
        />
        {support.details ? (
          <SelectField
            id="emp-type"
            label={support.employmentLabel}
            required
            placeholder="Choose"
            value={values.employment_type}
            onChange={(v) => set("employment_type", v as EmploymentType)}
            options={support.employmentOptions}
            error={fe.employment_type}
          />
        ) : null}
        {support.status ? (
          <div className="form-field field-span">
            <StatusToggle id="emp-active" checked={values.active} onChange={(v) => set("active", v)} label="Active account" />
          </div>
        ) : null}
      </FormSection>

      {support.files ? (
        <FormSection title="Documents" description="Files upload after the record is saved.">
          {employee ? (
            <div className="form-field field-span">
              <span className="people-label">Uploaded</span>
              <StoredDocuments documents={employee.documents} onRemove={onRemoveDocument} />
            </div>
          ) : null}
          <DocumentPicker id="emp-documents" pending={documents} onChange={setDocuments} existingCount={employee?.documents.length ?? 0} suggestions={support.documentTitles ?? copy.documents} />
        </FormSection>
      ) : null}

      <div className="people-form-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
          {saving ? "Saving…" : employee ? "Save changes" : copy.addLabel}
        </button>
        <Link className="btn-pill btn-pill-green-soft" href={employee ? `${copy.base}/${employee.id}` : copy.base}>
          Cancel
        </Link>
      </div>

      {confirmDeactivate && employee ? (
        <ConfirmDialog
          title={`Deactivate ${employee.name}?`}
          body={copy.deactivateEffect(employee.name)}
          confirmLabel="Save and deactivate"
          tone="danger"
          pending={saving}
          onConfirm={() => void save()}
          onCancel={() => setConfirmDeactivate(false)}
        />
      ) : null}
    </form>
  );
}

// ---------- Create / edit pages ----------

export function EmployeeCreatePage({ kind }: { kind: EmployeeKind }) {
  const copy = EMPLOYEE_COPY[kind];
  return (
    <PeoplePage module={kind} title={copy.addLabel} description="Fields marked * are required." icon={<KindIcon kind={kind} />} back={{ href: copy.base, label: copy.title }}>
      <EmployeeCreate kind={kind} />
    </PeoplePage>
  );
}

function EmployeeCreate({ kind }: { kind: EmployeeKind }) {
  const router = useRouter();
  const copy = EMPLOYEE_COPY[kind];
  const service = peopleService(kind);
  const departments = useOptions(useCallback(() => service.listDepartments(kind), [service, kind]));
  return (
    <EmployeeForm
      kind={kind}
      employee={null}
      departments={departments.options}
      onSave={async ({ input, photo, documents }) => {
        const saved = await service.createEmployee(kind, input);
        const failures = await uploadFiles(service, kind, saved.id, photo, documents);
        if (failures.length) flashMessage(`${saved.name} was added (${saved.employee_code}), but some files didn't upload. ${failures.join(" ")} Upload them again from Edit.`, "error");
        else flashMessage(saved.employee_code ? `${saved.name} was added with employee ID ${saved.employee_code}.` : `${saved.name} was added.`);
        router.push(`${copy.base}/${saved.id}`);
      }}
    />
  );
}

export function EmployeeEditPage({ kind }: { kind: EmployeeKind }) {
  const copy = EMPLOYEE_COPY[kind];
  const id = routeId(useParamsId());
  return (
    <PeoplePage
      module={kind}
      title={`Edit ${copy.singular}`}
      icon={<KindIcon kind={kind} />}
      back={id ? { href: `${copy.base}/${id}`, label: "Profile" } : { href: copy.base, label: copy.title }}
    >
      {id ? <EmployeeEdit kind={kind} id={id} /> : <NotFound kind={kind} />}
    </PeoplePage>
  );
}

function EmployeeEdit({ kind, id }: { kind: EmployeeKind; id: number }) {
  const router = useRouter();
  const toast = useToast();
  const copy = EMPLOYEE_COPY[kind];
  const service = peopleService(kind);
  const loader = useCallback(() => service.getEmployee(kind, id), [service, kind, id]);
  const { record: employee, loading, error, reload } = useRecord(loader);
  const departments = useOptions(useCallback(() => service.listDepartments(kind), [service, kind]));

  if (!peopleSupport(kind).edit) {
    return (
      <div className="alert alert-info" role="status">
        Editing {copy.plural} isn&apos;t available on the school&apos;s server yet.
      </div>
    );
  }
  if (error) return <ErrorAlert error={error} onRetry={() => void reload()} />;
  if (loading && !employee) return <ProfileSkeleton />;
  if (!employee) return null;

  return (
    <EmployeeForm
      key={employee.id}
      kind={kind}
      employee={employee}
      departments={departments.options}
      onRemoveDocument={async (document) => {
        await service.deleteDocument(kind, employee.id, document.id);
        toast("success", `${document.title} removed.`);
        await reload();
      }}
      onSave={async ({ input, photo, documents }) => {
        const saved = await service.updateEmployee(kind, employee.id, input);
        const failures = await uploadFiles(service, kind, saved.id, photo, documents);
        if (failures.length) flashMessage(`Changes saved, but some files didn't upload. ${failures.join(" ")}`, "error");
        else flashMessage(`${saved.name} updated.`);
        router.push(`${copy.base}/${saved.id}`);
      }}
    />
  );
}

// ---------- Profile ----------

export function EmployeeProfilePage({ kind }: { kind: EmployeeKind }) {
  const copy = EMPLOYEE_COPY[kind];
  const id = routeId(useParamsId());
  return (
    <PeoplePage module={kind} title={kind === "teachers" ? "Teacher profile" : "Staff profile"} icon={<KindIcon kind={kind} />} back={{ href: copy.base, label: copy.title }}>
      {id ? <EmployeeProfile kind={kind} id={id} /> : <NotFound kind={kind} />}
    </PeoplePage>
  );
}

function EmployeeProfile({ kind, id }: { kind: EmployeeKind; id: number }) {
  const copy = EMPLOYEE_COPY[kind];
  const service = peopleService(kind);
  const loader = useCallback(() => service.getEmployee(kind, id), [service, kind, id]);
  const { record: employee, setRecord, loading, error, reload } = useRecord(loader);
  const support = peopleSupport(kind);

  if (error) return <ErrorAlert error={error} onRetry={() => void reload()} />;
  if (loading && !employee) return <ProfileSkeleton />;
  if (!employee) return null;

  const gender = GENDERS.find((g) => g.value === employee.gender)?.label;
  return (
    <div className="people-grid">
      <ProfileHeader
        name={employee.name}
        photoUrl={employee.photo_url}
        active={employee.status === 1}
        meta={support.details ? `${employee.employee_code} · ${employee.designation}, ${employee.department}` : employee.email}
        actions={
          <>
            {support.edit ? (
              <Link className="btn-pill btn-pill-green" href={`${copy.base}/${employee.id}/edit`}>
                Edit {copy.singular}
              </Link>
            ) : null}
            {support.status ? (
              <StatusAction
                name={employee.name}
                noun={copy.singular}
                active={employee.status === 1}
                deactivateEffect={copy.deactivateEffect(employee.name)}
                change={(next) => service.setEmployeeStatus(kind, employee.id, next)}
                onChanged={setRecord}
              />
            ) : null}
          </>
        }
      />
      <div className="people-columns">
        <InfoCard
          title="Personal and contact"
          rows={[
            { label: "Email", value: <a href={`mailto:${employee.email}`}>{employee.email}</a> },
            { label: "Phone", value: <a href={`tel:${employee.mobile}`}>{employee.mobile}</a> },
            { label: "Gender", value: gender },
            { label: "Date of birth", value: employee.dob ? formatDate(employee.dob) : null },
            { label: "Address", value: employee.current_address },
          ]}
        />
        <InfoCard
          title="Employment"
          rows={[
            { label: "Employee ID", value: employee.employee_code },
            { label: "Department", value: employee.department },
            { label: "Designation", value: employee.designation },
            { label: "Qualification", value: employee.qualification },
            { label: "Joining date", value: formatDate(employee.joining_date) },
            { label: support.employmentLabel, value: employmentText(support, employee.employment_type) },
            { label: "Account status", value: employee.status === 1 ? "Active" : "Inactive" },
          ]}
        />
      </div>
      {kind === "teachers" ? <TeacherAssignments teacherId={employee.id} /> : null}
      {support.files ? (
        <InfoCard title="Documents" action={<Link className="link-btn" href={`${copy.base}/${employee.id}/edit`}>Upload</Link>}>
          <StoredDocuments documents={employee.documents} />
        </InfoCard>
      ) : null}
    </div>
  );
}

/** The teacher's class and subject assignments, from the academic structure module. */
function TeacherAssignments({ teacherId }: { teacherId: number }) {
  const assignments = useOptions(
    useCallback(() => listAll((page) => assignmentService.listAssignments({ page, pageSize: 50, teacherId })), [teacherId]),
  );
  return (
    <InfoCard title="Classes and subjects" action={<Link className="link-btn" href="/school/academics/teacher-assignments">Manage assignments</Link>}>
      {assignments.loading ? <div className="skeleton" style={{ height: 40 }} /> : null}
      {assignments.error ? <p className="muted people-empty">Assignments couldn&apos;t load right now.</p> : null}
      {!assignments.loading && !assignments.error && assignments.options.length === 0 ? <p className="muted people-empty">No classes assigned yet.</p> : null}
      {assignments.options.length ? (
        <ul className="people-link-list">
          {assignments.options.map((row) => (
            <li key={row.id}>
              <span>
                <strong>{row.subject_name}</strong>
                <span className="muted">
                  {" "}
                  · {row.class_name} {row.section_name} · {row.session_name}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </InfoCard>
  );
}

function NotFound({ kind }: { kind: EmployeeKind }) {
  return (
    <div className="alert alert-danger" role="alert">
      {kind === "teachers" ? "Teacher" : "Staff member"} not found
    </div>
  );
}

function useParamsId() {
  return useParams<{ id: string }>().id;
}
