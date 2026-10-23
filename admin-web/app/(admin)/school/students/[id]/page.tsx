"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { StoredDocuments } from "@/components/people/Files";
import { GuardianManager } from "@/components/people/Links";
import { PeoplePage, routeId } from "@/components/people/PeoplePage";
import { InfoCard, ProfileHeader, ProfileSkeleton, useRecord } from "@/components/people/Profile";
import { StatusAction } from "@/components/people/StatusAction";
import { formatDate, GENDERS, peopleService } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const service = peopleService("students");

export default function StudentProfilePage() {
  const id = routeId(useParams<{ id: string }>().id);
  return (
    <PeoplePage module="students" title="Student profile" icon={<IconUsers width={18} height={18} />} back={{ href: "/school/students", label: "Students" }}>
      {id ? <StudentProfile id={id} /> : <div className="alert alert-danger" role="alert">Student not found</div>}
    </PeoplePage>
  );
}

function StudentProfile({ id }: { id: number }) {
  const loader = useCallback(() => service.getStudent(id), [id]);
  const { record: student, setRecord, loading, error, reload } = useRecord(loader);

  if (error) return <ErrorAlert error={error} onRetry={() => void reload()} />;
  if (loading && !student) return <ProfileSkeleton />;
  if (!student) return null;

  const gender = GENDERS.find((g) => g.value === student.gender)?.label;
  return (
    <div className="people-grid">
      <ProfileHeader
        name={student.name}
        photoUrl={student.photo_url}
        active={student.status === 1}
        meta={`${student.admission_no} · ${student.class_name} ${student.section_name} · ${student.session_name}`}
        actions={
          <>
            <Link className="btn-pill btn-pill-green" href={`/school/students/${student.id}/edit`}>
              Edit student
            </Link>
            <StatusAction
              name={student.name}
              noun="student"
              active={student.status === 1}
              deactivateEffect={`${student.name} stays in your records but is hidden from attendance, exams and fee lists, and their parents can't see them in the app.`}
              change={(next) => service.setStudentStatus(student.id, next)}
              onChanged={setRecord}
            />
          </>
        }
      />
      <div className="people-columns">
        <InfoCard
          title="Personal information"
          rows={[
            { label: "First name", value: student.first_name },
            { label: "Last name", value: student.last_name },
            { label: "Date of birth", value: formatDate(student.dob) },
            { label: "Gender", value: gender },
            { label: "Email", value: student.email },
            { label: "Phone", value: student.mobile },
            { label: "Current address", value: student.current_address },
            { label: "Permanent address", value: student.permanent_address },
          ]}
        />
        <InfoCard
          title="Academic and admission"
          rows={[
            { label: "Admission / GR number", value: student.admission_no },
            { label: "Admission date", value: formatDate(student.admission_date) },
            { label: "Session", value: student.session_name },
            { label: "Class", value: student.class_name },
            { label: "Section", value: student.section_name },
            { label: "Roll number", value: student.roll_number },
            { label: "Account status", value: student.status === 1 ? "Active" : "Inactive" },
          ]}
        />
      </div>
      <GuardianManager student={student} onChange={setRecord} editable={false} manageHref={`/school/students/${student.id}/edit`} />
      <InfoCard title="Documents" action={<Link className="link-btn" href={`/school/students/${student.id}/edit`}>Upload</Link>}>
        <StoredDocuments documents={student.documents} />
      </InfoCard>
    </div>
  );
}
