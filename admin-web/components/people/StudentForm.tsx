"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { SelectField, StatusToggle, TextAreaField, TextField } from "@/components/academics/Fields";
import { useFormErrors } from "@/components/academics/hooks";
import { classLabel, sectionLabel, sessionLabel, useClassesFor, useSectionsFor, useSessions } from "@/components/people/academicOptions";
import { DocumentPicker, PhotoPicker, StoredDocuments, type PendingDocument } from "@/components/people/Files";
import { PasswordField } from "@/components/people/PasswordField";
import { ParentSearch, useDuplicateParent } from "@/components/people/Pickers";
import { FormSection } from "@/components/people/Profile";
import { GENDERS, peopleSupport, RELATIONSHIPS, type Gender, type GuardianChoice, type Parent, type Relationship, type StoredFile, type Student, type StudentInput } from "@/lib/people";
import { email, focusFirstError, phone, required, todayIso, type Errors } from "@/lib/people/validate";

// The live server stores fewer student fields; the form hides what it can't save.
const support = peopleSupport("students");

export const STUDENT_DOCUMENTS = ["Birth certificate", "Transfer certificate", "Previous report card", "Aadhaar card", "Address proof", "Medical certificate"];

type Values = {
  first_name: string;
  last_name: string;
  dob: string;
  gender: Gender | "";
  admission_no: string;
  admission_date: string;
  session_year_id: string;
  class_id: string;
  class_section_id: string;
  roll_number: string;
  email: string;
  mobile: string;
  current_address: string;
  permanent_address: string;
  same_address: boolean;
  active: boolean;
};

type GuardianState = {
  mode: "existing" | "new";
  parent: Parent | null;
  relationship: Relationship | "";
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  /** Sign-in password for a new parent (live backend only). */
  password: string;
};

function initialValues(student: Student | null): Values {
  return {
    first_name: student?.first_name ?? "",
    last_name: student?.last_name ?? "",
    dob: student?.dob ?? "",
    gender: student?.gender ?? "",
    admission_no: student?.admission_no ?? "",
    admission_date: student?.admission_date ?? todayIso(),
    session_year_id: student ? String(student.session_year_id) : "",
    class_id: student ? String(student.class_id) : "",
    class_section_id: student ? String(student.class_section_id) : "",
    roll_number: student?.roll_number ? String(student.roll_number) : "",
    email: student?.email ?? "",
    mobile: student?.mobile ?? "",
    current_address: student?.current_address ?? "",
    permanent_address: student?.permanent_address ?? "",
    same_address: student ? !student.permanent_address || student.permanent_address === student.current_address : true,
    active: student ? student.status === 1 : true,
  };
}

export type StudentFormResult = {
  input: StudentInput & { guardian?: GuardianChoice };
  photo: File | null;
  documents: PendingDocument[];
};

/**
 * Admission form (no `student`) and edit form (with `student`). Creating a student also
 * picks or creates the first parent/guardian; on edit, guardians are managed separately.
 */
export function StudentForm({
  student,
  cancelHref,
  onSave,
  onRemoveDocument,
}: {
  student: Student | null;
  cancelHref: string;
  onSave: (result: StudentFormResult) => Promise<void>;
  onRemoveDocument?: (document: StoredFile) => Promise<void>;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [values, setValues] = useState<Values>(() => initialValues(student));
  const [guardian, setGuardian] = useState<GuardianState>({ mode: "existing", parent: null, relationship: "", first_name: "", last_name: "", email: "", mobile: "", password: "" });
  const [photo, setPhoto] = useState<File | null>(null);
  const [documents, setDocuments] = useState<PendingDocument[]>([]);
  const [saving, setSaving] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const errors = useFormErrors();
  const fe = errors.fieldErrors;

  const sessionId = values.session_year_id ? Number(values.session_year_id) : "";
  const classId = values.class_id ? Number(values.class_id) : "";
  const sessions = useSessions();
  const classes = useClassesFor(sessionId, true);
  const sections = useSectionsFor(classId);
  const duplicate = useDuplicateParent(guardian.mode === "new" ? guardian.email : "", guardian.mode === "new" ? guardian.mobile : "");

  // A new admission starts in the school's current session.
  useEffect(() => {
    if (student || values.session_year_id) return;
    const current = sessions.options.find((row) => row.is_active);
    if (current) setValues((v) => ({ ...v, session_year_id: String(current.id) }));
  }, [sessions.options, student, values.session_year_id]);

  function set<K extends keyof Values>(key: K, value: Values[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function setGuardianField<K extends keyof GuardianState>(key: K, value: GuardianState[K]) {
    setGuardian((g) => ({ ...g, [key]: value }));
  }

  // Inactive classes and sections can't take new students, but a student already in one keeps it.
  const classChoices = classes.options.filter((row) => row.status === 1 || (student && row.id === student.class_id));
  const sectionChoices = sections.options.filter((row) => row.status === 1 || (student && row.id === student.class_section_id));

  function check(): Errors {
    const invalid: Errors = {};
    required(invalid, "first_name", values.first_name, "Enter the student's first name.");
    required(invalid, "last_name", values.last_name, "Enter the student's last name.");
    if (support.details) {
      if (!values.dob) invalid.dob = "Enter the date of birth.";
      else if (values.dob > todayIso()) invalid.dob = "Date of birth can't be in the future.";
      if (!values.gender) invalid.gender = "Choose a gender.";
    }
    if (!values.admission_date) invalid.admission_date = "Enter the admission date.";
    else if (values.dob && values.admission_date <= values.dob) invalid.admission_date = "Admission date must be after the date of birth.";
    if (student && !values.admission_no.trim()) invalid.admission_no = "Enter the admission number.";
    if (!values.session_year_id) invalid.session_year_id = "Choose an academic session.";
    if (!values.class_id) invalid.class_id = "Choose a class.";
    if (!values.class_section_id) invalid.class_section_id = values.class_id ? "Choose a section." : "Choose a class first.";
    if (values.roll_number && (!/^\d+$/.test(values.roll_number) || Number(values.roll_number) < 1)) invalid.roll_number = "Roll number must be a whole number.";
    // The live server needs an email for every new student.
    email(invalid, "email", values.email, !support.details && !student);
    if (support.details) {
      phone(invalid, "mobile", values.mobile, false);
      required(invalid, "current_address", values.current_address, "Enter the address.");
      if (!values.same_address) required(invalid, "permanent_address", values.permanent_address, "Enter the permanent address or tick Same as current address.");
    }
    if (!student) {
      if (support.guardianLinks && !guardian.relationship) invalid["guardian.relationship"] = "Choose how this person is related to the student.";
      if (guardian.mode === "existing") {
        if (!guardian.parent) invalid["guardian.parent_id"] = "Find and choose a parent, or switch to Add a new parent.";
      } else {
        required(invalid, "guardian.first_name", guardian.first_name, "Enter the parent's first name.");
        required(invalid, "guardian.last_name", guardian.last_name, "Enter the parent's last name.");
        email(invalid, "guardian.email", guardian.email, true);
        phone(invalid, "guardian.mobile", guardian.mobile, true);
        if (support.password && guardian.password.length < 8) invalid["guardian.password"] = "Enter a password of at least 8 characters, or use Generate.";
      }
    }
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
    if (student?.status === 1 && !values.active) setConfirmDeactivate(true);
    else void save();
  }

  async function save() {
    setConfirmDeactivate(false);
    errors.clear();
    setSaving(true);
    const input: StudentFormResult["input"] = {
      first_name: values.first_name.trim(),
      last_name: values.last_name.trim(),
      dob: values.dob,
      gender: values.gender as Gender,
      admission_no: values.admission_no.trim() || undefined,
      admission_date: values.admission_date,
      session_year_id: Number(values.session_year_id),
      class_section_id: Number(values.class_section_id),
      roll_number: values.roll_number ? Number(values.roll_number) : null,
      email: values.email.trim() || null,
      mobile: values.mobile.trim() || null,
      current_address: values.current_address.trim(),
      permanent_address: values.same_address ? values.current_address.trim() : values.permanent_address.trim(),
      status: values.active ? 1 : 0,
    };
    if (!student) {
      const relationship = (guardian.relationship || "Guardian") as Relationship;
      input.guardian =
        guardian.mode === "existing" && guardian.parent
          ? { parent_id: guardian.parent.id, relationship }
          : {
              first_name: guardian.first_name.trim(),
              last_name: guardian.last_name.trim(),
              email: guardian.email.trim(),
              mobile: guardian.mobile.trim(),
              relationship,
              password: support.password ? guardian.password : undefined,
            };
    }
    try {
      await onSave({ input, photo, documents });
    } catch (caught) {
      errors.fromError(caught, student ? "Unable to save the student." : "Unable to admit the student.");
      setSaving(false);
      focusFirstError(formRef.current);
    }
  }

  const fullName = `${values.first_name} ${values.last_name}`.trim();

  return (
    <form ref={formRef} className="people-form" onSubmit={onSubmit} noValidate aria-busy={saving}>
      {errors.formError ? (
        <div className="alert alert-danger" role="alert">
          {errors.formError}
        </div>
      ) : null}

      <FormSection title="Student details">
        <TextField id="student-first-name" label="First name" required maxLength={128} autoComplete="off" value={values.first_name} onChange={(v) => set("first_name", v)} error={fe.first_name} />
        <TextField id="student-last-name" label="Last name" required maxLength={128} autoComplete="off" value={values.last_name} onChange={(v) => set("last_name", v)} error={fe.last_name} />
        {support.details ? (
          <>
            <TextField id="student-dob" label="Date of birth" type="date" required max={todayIso()} value={values.dob} onChange={(v) => set("dob", v)} error={fe.dob} />
            <SelectField id="student-gender" label="Gender" required placeholder="Choose" value={values.gender} onChange={(v) => set("gender", v as Gender)} options={GENDERS.map((g) => ({ value: g.value, label: g.label }))} error={fe.gender} />
          </>
        ) : null}
        {support.files ? <PhotoPicker id="student-photo" name={fullName} currentUrl={student?.photo_url ?? null} file={photo} onChange={setPhoto} error={fe.file} /> : null}
      </FormSection>

      <FormSection title="Admission" description="Session, class and section must be active. Classes depend on the session and sections depend on the class.">
        <TextField
          id="student-admission-no"
          label="Admission / GR number"
          required={Boolean(student)}
          maxLength={32}
          placeholder={student ? undefined : "Generated automatically"}
          value={values.admission_no}
          onChange={(v) => set("admission_no", v)}
          error={fe.admission_no}
          hint={student ? undefined : "Leave blank to use the next number, or enter the number from your register."}
        />
        <TextField id="student-admission-date" label="Admission date" type="date" required value={values.admission_date} onChange={(v) => set("admission_date", v)} error={fe.admission_date} />
        <SelectField
          id="student-session"
          label="Academic session"
          required
          placeholder="Choose a session"
          loading={sessions.loading}
          value={values.session_year_id}
          onChange={(v) => setValues((current) => ({ ...current, session_year_id: v, class_id: "", class_section_id: "" }))}
          options={sessions.options.map((row) => ({ value: String(row.id), label: sessionLabel(row) }))}
          error={fe.session_year_id}
        />
        <SelectField
          id="student-class"
          label="Class"
          required
          placeholder={values.session_year_id ? "Choose a class" : "Choose a session first"}
          loading={classes.loading}
          disabled={!values.session_year_id}
          value={values.class_id}
          onChange={(v) => setValues((current) => ({ ...current, class_id: v, class_section_id: "" }))}
          options={classChoices.map((row) => ({ value: String(row.id), label: classLabel(row) }))}
          error={fe.class_id}
        />
        <SelectField
          id="student-section"
          label="Section"
          required
          placeholder={values.class_id ? (sectionChoices.length || sections.loading ? "Choose a section" : "This class has no active sections") : "Choose a class first"}
          loading={sections.loading}
          disabled={!values.class_id}
          value={values.class_section_id}
          onChange={(v) => set("class_section_id", v)}
          options={sectionChoices.map((row) => ({ value: String(row.id), label: sectionLabel(row) }))}
          error={fe.class_section_id}
        />
        <TextField id="student-roll" label="Roll number" type="number" min="1" value={values.roll_number} onChange={(v) => set("roll_number", v)} error={fe.roll_number} hint="Optional. Must be unique within the section." />
        <div className="form-field field-span">
          <StatusToggle id="student-active" checked={values.active} onChange={(v) => set("active", v)} label="Active student" />
        </div>
        {sessions.error || classes.error || sections.error ? (
          <p className="field-error field-span" role="alert">
            Some dropdowns couldn&apos;t load. Reload the page to try again.
          </p>
        ) : null}
      </FormSection>

      {!student ? (
        <FormSection
          title="Parent or guardian"
          description={
            support.guardianLinks
              ? "Every student needs at least one parent or guardian. You can link more from the student's profile later."
              : "Every student needs a parent or guardian. The school's server keeps one per student."
          }
        >
          <div className="form-field field-span people-mode-switch" role="radiogroup" aria-label="Parent or guardian">
            <label className="acad-check">
              <input type="radio" name="guardian-mode" checked={guardian.mode === "existing"} onChange={() => setGuardianField("mode", "existing")} />
              <span>Choose an existing parent</span>
            </label>
            <label className="acad-check">
              <input type="radio" name="guardian-mode" checked={guardian.mode === "new"} onChange={() => setGuardianField("mode", "new")} />
              <span>Add a new parent</span>
            </label>
          </div>

          {guardian.mode === "existing" ? (
            guardian.parent ? (
              <div className="form-field field-span">
                <span className="people-label">Selected parent</span>
                <div className="people-chosen">
                  <span>
                    <strong>{guardian.parent.name}</strong>
                    <span className="muted"> · {[guardian.parent.email, guardian.parent.mobile].filter(Boolean).join(" · ")}</span>
                  </span>
                  <button className="link-btn" type="button" onClick={() => setGuardianField("parent", null)}>
                    Change
                  </button>
                </div>
              </div>
            ) : (
              <ParentSearch id="guardian-search" onPick={(parent) => setGuardianField("parent", parent)} error={fe["guardian.parent_id"]} />
            )
          ) : (
            <>
              <TextField id="guardian-first-name" label="First name" required maxLength={128} value={guardian.first_name} onChange={(v) => setGuardianField("first_name", v)} error={fe["guardian.first_name"]} />
              <TextField id="guardian-last-name" label="Last name" required maxLength={128} value={guardian.last_name} onChange={(v) => setGuardianField("last_name", v)} error={fe["guardian.last_name"]} />
              <TextField id="guardian-email" label="Email" type="email" required autoComplete="off" value={guardian.email} onChange={(v) => setGuardianField("email", v)} error={fe["guardian.email"]} hint="Used to sign in to the parent app." />
              <TextField id="guardian-mobile" label="Phone" type="tel" required value={guardian.mobile} onChange={(v) => setGuardianField("mobile", v)} error={fe["guardian.mobile"]} />
              {support.password ? (
                <PasswordField
                  id="guardian-password"
                  label="Parent sign-in password"
                  value={guardian.password}
                  onChange={(v) => setGuardianField("password", v)}
                  error={fe["guardian.password"]}
                  hint="At least 8 characters. Copy it and give it to the parent; they sign in to the parent app with their email and this password."
                />
              ) : null}
              {duplicate ? (
                <div className="alert alert-info field-span people-duplicate" role="status">
                  <span>
                    <strong>{duplicate.name}</strong> is already registered with this email or phone number.
                  </span>
                  <button
                    className="link-btn"
                    type="button"
                    onClick={() => setGuardian((g) => ({ ...g, mode: "existing", parent: duplicate }))}
                  >
                    Use {duplicate.name}
                  </button>
                </div>
              ) : null}
            </>
          )}
          {support.guardianLinks ? (
            <SelectField
              id="guardian-relationship"
              label="Relationship to student"
              required
              placeholder="Choose"
              value={guardian.relationship}
              onChange={(v) => setGuardianField("relationship", v as Relationship)}
              options={RELATIONSHIPS.map((r) => ({ value: r, label: r }))}
              error={fe["guardian.relationship"]}
            />
          ) : null}
        </FormSection>
      ) : null}

      <FormSection title={support.details ? "Contact and address" : "Contact"}>
        {support.details ? (
          <TextField id="student-email" label="Student email" type="email" autoComplete="off" value={values.email} onChange={(v) => set("email", v)} error={fe.email} hint="Optional. Needed only if the student signs in to the app." />
        ) : (
          <TextField
            id="student-email"
            label="Student email"
            type="email"
            required={!student}
            disabled={Boolean(student)}
            autoComplete="off"
            value={values.email}
            onChange={(v) => set("email", v)}
            error={fe.email}
            hint={student ? "The school's server can't change a student's email yet." : "The school's server needs an email for every student."}
          />
        )}
        {support.details ? (
          <>
            <TextField id="student-mobile" label="Student phone" type="tel" value={values.mobile} onChange={(v) => set("mobile", v)} error={fe.mobile} hint="Optional." />
            <TextAreaField id="student-address" label="Current address" required span maxLength={512} value={values.current_address} onChange={(v) => set("current_address", v)} error={fe.current_address} />
            <div className="form-field field-span">
              <StatusToggle id="student-same-address" checked={values.same_address} onChange={(v) => set("same_address", v)} label="Permanent address is the same as current address" />
            </div>
            {!values.same_address ? (
              <TextAreaField id="student-permanent-address" label="Permanent address" required span maxLength={512} value={values.permanent_address} onChange={(v) => set("permanent_address", v)} error={fe.permanent_address} />
            ) : null}
          </>
        ) : null}
      </FormSection>

      {support.files ? (
        <FormSection title="Documents" description="Files upload after the student is saved.">
          {student ? (
            <div className="form-field field-span">
              <span className="people-label">Uploaded</span>
              <StoredDocuments documents={student.documents} onRemove={onRemoveDocument} />
            </div>
          ) : null}
          <DocumentPicker id="student-documents" pending={documents} onChange={setDocuments} existingCount={student?.documents.length ?? 0} suggestions={STUDENT_DOCUMENTS} />
        </FormSection>
      ) : null}

      <div className="people-form-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
          {saving ? "Saving…" : student ? "Save changes" : "Admit student"}
        </button>
        <Link className="btn-pill btn-pill-green-soft" href={cancelHref} aria-disabled={saving}>
          Cancel
        </Link>
      </div>

      {confirmDeactivate && student ? (
        <ConfirmDialog
          title={`Deactivate ${student.name}?`}
          body={`${student.name} stays in your records but is hidden from attendance, exams and fee lists, and their parents can't see them in the app.`}
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
