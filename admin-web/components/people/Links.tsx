"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { SelectField, StatusToggle } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { StatusBadge } from "@/components/academics/StatusBadge";
import { useToast } from "@/components/academics/Toasts";
import { useFormErrors } from "@/components/academics/hooks";
import { ParentSearch, StudentSearch } from "@/components/people/Pickers";
import { InfoCard } from "@/components/people/Profile";
import { errorMessage, peopleService, RELATIONSHIPS, type ChildLink, type GuardianLink, type Parent, type Relationship, type Student, type StudentRow } from "@/lib/people";

/** Linking always goes through the student guardian endpoints, whichever page starts it. */
const linkService = peopleService("students");

/** The student's parents and guardians, with link and remove. Used on the student profile and edit page. */
export function GuardianManager({
  student,
  onChange,
  editable = true,
  manageHref,
}: {
  student: Student;
  onChange: (student: Student) => void;
  editable?: boolean;
  manageHref?: string;
}) {
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<GuardianLink | null>(null);
  const [pending, setPending] = useState(false);

  async function remove(link: GuardianLink) {
    setPending(true);
    try {
      const saved = await linkService.unlinkGuardian(student.id, link.parent_id);
      toast("success", `${link.name} is no longer linked to ${student.name}.`);
      onChange(saved);
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to remove the guardian."));
    } finally {
      setPending(false);
      setRemoving(null);
    }
  }

  return (
    <InfoCard
      title="Parents and guardians"
      action={
        editable && student.guardians.length < 4 ? (
          <button className="link-btn" type="button" onClick={() => setAdding(true)}>
            Link guardian
          </button>
        ) : !editable && manageHref ? (
          <Link className="link-btn" href={manageHref}>
            Manage
          </Link>
        ) : null
      }
    >
      {student.guardians.length === 0 ? <p className="muted people-empty">No parent or guardian linked.</p> : null}
      <ul className="people-link-list">
        {student.guardians.map((link) => (
          <li key={link.parent_id}>
            <span>
              <Link href={`/school/parents/${link.parent_id}`}>
                <strong>{link.name}</strong>
              </Link>
              <span className="muted">
                {" "}
                · {link.relationship}
                {link.is_primary ? " · Primary contact" : ""}
              </span>
              <span className="muted people-link-contact">{[link.mobile, link.email].filter(Boolean).join(" · ")}</span>
            </span>
            {editable ? (
              <button className="link-btn acad-danger-link" type="button" onClick={() => setRemoving(link)}>
                Remove<span className="acad-sr"> {link.name}</span>
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      {adding ? (
        <LinkModal
          title={`Link a guardian to ${student.name}`}
          picker={(onPick, error) => <ParentSearch id="link-parent" excludeIds={student.guardians.map((g) => g.parent_id)} onPick={onPick} error={error} />}
          describe={(parent: Parent) => parent.name}
          showPrimary
          onClose={() => setAdding(false)}
          save={async (parent, relationship, isPrimary) => {
            const saved = await linkService.linkGuardian(student.id, { parent_id: parent.id, relationship, is_primary: isPrimary });
            setAdding(false);
            toast("success", `${parent.name} is now linked to ${student.name}.`);
            onChange(saved);
          }}
        />
      ) : null}

      {removing ? (
        <ConfirmDialog
          title={`Remove ${removing.name} from ${student.name}?`}
          body={`${removing.name} will no longer see ${student.name} in the parent app or get notices about them. The parent record itself isn't deleted.`}
          confirmLabel="Remove link"
          tone="danger"
          pending={pending}
          onConfirm={() => void remove(removing)}
          onCancel={() => setRemoving(null)}
        />
      ) : null}
    </InfoCard>
  );
}

/** The parent's children, with link and remove. Used on the parent profile and edit page. */
export function ChildrenManager({
  parent,
  onChanged,
  editable = true,
  manageHref,
}: {
  parent: Parent;
  onChanged: () => Promise<void>;
  editable?: boolean;
  manageHref?: string;
}) {
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<ChildLink | null>(null);
  const [pending, setPending] = useState(false);

  async function remove(child: ChildLink) {
    setPending(true);
    try {
      await linkService.unlinkGuardian(child.student_id, parent.id);
      toast("success", `${child.name} is no longer linked to ${parent.name}.`);
      await onChanged();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to remove the link."));
    } finally {
      setPending(false);
      setRemoving(null);
    }
  }

  return (
    <InfoCard
      title="Linked children"
      action={
        editable ? (
          <button className="link-btn" type="button" onClick={() => setAdding(true)}>
            Link student
          </button>
        ) : manageHref ? (
          <Link className="link-btn" href={manageHref}>
            Manage
          </Link>
        ) : null
      }
    >
      {parent.children.length === 0 ? <p className="muted people-empty">No students linked yet.</p> : null}
      <ul className="people-link-list">
        {parent.children.map((child) => (
          <li key={child.student_id}>
            <span>
              <Link href={`/school/students/${child.student_id}`}>
                <strong>{child.name}</strong>
              </Link>
              <span className="muted">
                {" "}
                · {child.class_name} {child.section_name} · {child.relationship}
                {child.is_primary ? " · Primary contact" : ""}
              </span>
              <span className="muted people-link-contact">
                {child.admission_no} <StatusBadge active={child.status === 1} />
              </span>
            </span>
            {editable ? (
              <button className="link-btn acad-danger-link" type="button" onClick={() => setRemoving(child)}>
                Remove<span className="acad-sr"> {child.name}</span>
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      {adding ? (
        <LinkModal
          title={`Link a student to ${parent.name}`}
          picker={(onPick, error) => <StudentSearch id="link-student" excludeIds={parent.children.map((c) => c.student_id)} onPick={onPick} error={error} />}
          describe={(student: StudentRow) => `${student.name} (${student.class_name} ${student.section_name})`}
          onClose={() => setAdding(false)}
          save={async (student, relationship) => {
            await linkService.linkGuardian(student.id, { parent_id: parent.id, relationship });
            setAdding(false);
            toast("success", `${student.name} is now linked to ${parent.name}.`);
            await onChanged();
          }}
        />
      ) : null}

      {removing ? (
        <ConfirmDialog
          title={`Remove ${removing.name} from ${parent.name}?`}
          body={`${parent.name} will no longer see ${removing.name} in the parent app. A student must keep at least one guardian, so link another one first if this is the only one.`}
          confirmLabel="Remove link"
          tone="danger"
          pending={pending}
          onConfirm={() => void remove(removing)}
          onCancel={() => setRemoving(null)}
        />
      ) : null}
    </InfoCard>
  );
}

/** Pick one record, choose the relationship, then save. */
function LinkModal<T extends { id: number }>({
  title,
  picker,
  describe,
  showPrimary,
  onClose,
  save,
}: {
  title: string;
  picker: (onPick: (row: T) => void, error?: string) => ReactNode;
  describe: (row: T) => string;
  showPrimary?: boolean;
  onClose: () => void;
  save: (row: T, relationship: Relationship, isPrimary: boolean) => Promise<void>;
}) {
  const [chosen, setChosen] = useState<T | null>(null);
  const [relationship, setRelationship] = useState<Relationship | "">("");
  const [primary, setPrimary] = useState(false);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!chosen) invalid.pick = "Search and choose a record.";
    if (!relationship) invalid.relationship = "Choose the relationship.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await save(chosen as T, relationship as Relationship, primary);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the link.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={title} error={errors.formError} saving={saving} submitLabel="Link" onSubmit={() => void submit()} onClose={onClose}>
      {chosen ? (
        <div className="form-field field-span">
          <span className="people-label">Selected</span>
          <div className="people-chosen">
            <strong>{describe(chosen)}</strong>
            <button className="link-btn" type="button" onClick={() => setChosen(null)}>
              Change
            </button>
          </div>
        </div>
      ) : (
        picker(setChosen, errors.fieldErrors.pick ?? errors.fieldErrors.parent_id ?? errors.fieldErrors.student_id)
      )}
      <SelectField
        id="link-relationship"
        label="Relationship"
        required
        placeholder="Choose"
        value={relationship}
        onChange={(v) => setRelationship(v as Relationship)}
        options={RELATIONSHIPS.map((r) => ({ value: r, label: r }))}
        error={errors.fieldErrors.relationship}
      />
      {showPrimary ? (
        <div className="form-field field-span">
          <StatusToggle id="link-primary" checked={primary} onChange={setPrimary} label="Make this the primary contact" />
        </div>
      ) : null}
    </FormModal>
  );
}
