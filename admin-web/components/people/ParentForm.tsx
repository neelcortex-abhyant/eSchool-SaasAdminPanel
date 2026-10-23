"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { SelectField, StatusToggle, TextAreaField, TextField } from "@/components/academics/Fields";
import { useFormErrors } from "@/components/academics/hooks";
import { StudentSearch, useDuplicateParent } from "@/components/people/Pickers";
import { FormSection } from "@/components/people/Profile";
import { RELATIONSHIPS, type Parent, type ParentCreateInput, type ParentInput, type Relationship, type StudentRow } from "@/lib/people";
import { email, focusFirstError, phone, required, type Errors } from "@/lib/people/validate";

type PendingLink = { student: StudentRow; relationship: Relationship | "" };

/**
 * Create form (no `parent`, with student links) and edit form (with `parent`; links are
 * managed with the Linked children card next to it).
 */
export function ParentForm({
  parent,
  cancelHref,
  onSave,
}: {
  parent: Parent | null;
  cancelHref: string;
  onSave: (input: ParentInput | ParentCreateInput) => Promise<void>;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [firstName, setFirstName] = useState(parent?.first_name ?? "");
  const [lastName, setLastName] = useState(parent?.last_name ?? "");
  const [emailValue, setEmail] = useState(parent?.email ?? "");
  const [mobile, setMobile] = useState(parent?.mobile ?? "");
  const [occupation, setOccupation] = useState(parent?.occupation ?? "");
  const [address, setAddress] = useState(parent?.current_address ?? "");
  const [active, setActive] = useState(parent ? parent.status === 1 : true);
  const [links, setLinks] = useState<PendingLink[]>([]);
  const [saving, setSaving] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const errors = useFormErrors();
  const fe = errors.fieldErrors;
  const duplicate = useDuplicateParent(emailValue, mobile, parent?.id);

  function check(): Errors {
    const invalid: Errors = {};
    required(invalid, "first_name", firstName, "Enter the first name.");
    required(invalid, "last_name", lastName, "Enter the last name.");
    email(invalid, "email", emailValue, true);
    phone(invalid, "mobile", mobile, true);
    if (links.some((link) => !link.relationship)) invalid.students = "Choose the relationship for each linked student.";
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
    if (parent?.status === 1 && !active) setConfirmDeactivate(true);
    else void save();
  }

  async function save() {
    setConfirmDeactivate(false);
    errors.clear();
    setSaving(true);
    const input: ParentInput = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: emailValue.trim(),
      mobile: mobile.trim(),
      occupation: occupation.trim() || null,
      current_address: address.trim() || null,
      status: active ? 1 : 0,
    };
    try {
      await onSave(parent ? input : { ...input, students: links.map((link) => ({ student_id: link.student.id, relationship: link.relationship as Relationship })) });
    } catch (caught) {
      errors.fromError(caught, "Unable to save the parent.");
      setSaving(false);
      focusFirstError(formRef.current);
    }
  }

  return (
    <form ref={formRef} className="people-form" onSubmit={onSubmit} noValidate aria-busy={saving}>
      {errors.formError ? (
        <div className="alert alert-danger" role="alert">
          {errors.formError}
        </div>
      ) : null}

      <FormSection title="Personal and contact details">
        <TextField id="parent-first-name" label="First name" required maxLength={128} value={firstName} onChange={setFirstName} error={fe.first_name} />
        <TextField id="parent-last-name" label="Last name" required maxLength={128} value={lastName} onChange={setLastName} error={fe.last_name} />
        <TextField id="parent-email" label="Email" type="email" required autoComplete="off" value={emailValue} onChange={setEmail} error={fe.email} hint="Used to sign in to the parent app. Must be unique in your school." />
        <TextField id="parent-mobile" label="Phone" type="tel" required value={mobile} onChange={setMobile} error={fe.mobile} />
        {duplicate ? (
          <div className="alert alert-info field-span people-duplicate" role="status">
            <span>
              <strong>{duplicate.name}</strong> already has this email or phone number. Avoid a duplicate by linking students on their record.
            </span>
            <Link className="link-btn" href={`/school/parents/${duplicate.id}`}>
              Open {duplicate.name}
            </Link>
          </div>
        ) : null}
        <TextField id="parent-occupation" label="Occupation" maxLength={255} value={occupation} onChange={setOccupation} error={fe.occupation} />
        <TextAreaField id="parent-address" label="Address" span maxLength={512} value={address} onChange={setAddress} error={fe.current_address} />
        <div className="form-field field-span">
          <StatusToggle id="parent-active" checked={active} onChange={setActive} label="Active account" />
        </div>
      </FormSection>

      {!parent ? (
        <FormSection title="Linked students" description="A parent can be linked to several children, and a student can have up to 4 guardians.">
          <StudentSearch
            id="parent-student-search"
            label="Add a student"
            excludeIds={links.map((link) => link.student.id)}
            onPick={(student) => setLinks((current) => [...current, { student, relationship: "" }])}
            error={!links.length ? fe.students : undefined}
          />
          {links.length ? (
            <ul className="people-link-list field-span" aria-label="Students to link">
              {links.map((link, index) => (
                <li key={link.student.id}>
                  <span>
                    <strong>{link.student.name}</strong>
                    <span className="muted">
                      {" "}
                      · {link.student.admission_no} · {link.student.class_name} {link.student.section_name}
                    </span>
                  </span>
                  <SelectField
                    id={`link-relationship-${link.student.id}`}
                    label="Relationship"
                    required
                    placeholder="Choose"
                    value={link.relationship}
                    onChange={(value) => setLinks((current) => current.map((item, i) => (i === index ? { ...item, relationship: value as Relationship } : item)))}
                    options={RELATIONSHIPS.map((r) => ({ value: r, label: r }))}
                    error={!link.relationship ? fe.students : undefined}
                  />
                  <button className="link-btn acad-danger-link" type="button" onClick={() => setLinks((current) => current.filter((_, i) => i !== index))}>
                    Remove<span className="acad-sr"> {link.student.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </FormSection>
      ) : null}

      <div className="people-form-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
          {saving ? "Saving…" : parent ? "Save changes" : "Add parent"}
        </button>
        <Link className="btn-pill btn-pill-green-soft" href={cancelHref}>
          Cancel
        </Link>
      </div>

      {confirmDeactivate && parent ? (
        <ConfirmDialog
          title={`Deactivate ${parent.name}?`}
          body={`${parent.name} won't be able to sign in to the parent app. Their links to students are kept.`}
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
