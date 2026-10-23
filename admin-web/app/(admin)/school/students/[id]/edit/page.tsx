"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useToast } from "@/components/academics/Toasts";
import { uploadFiles } from "@/components/people/Files";
import { GuardianManager } from "@/components/people/Links";
import { PeoplePage, flashMessage, routeId } from "@/components/people/PeoplePage";
import { ProfileSkeleton, useRecord } from "@/components/people/Profile";
import { StudentForm } from "@/components/people/StudentForm";
import { peopleService, peopleSupport } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const service = peopleService("students");
const support = peopleSupport("students");

export default function EditStudentPage() {
  const id = routeId(useParams<{ id: string }>().id);
  return (
    <PeoplePage
      module="students"
      title="Edit student"
      icon={<IconUsers width={18} height={18} />}
      back={id ? { href: `/school/students/${id}`, label: "Student profile" } : { href: "/school/students", label: "Students" }}
    >
      {id ? <EditStudent id={id} /> : <div className="alert alert-danger" role="alert">Student not found</div>}
    </PeoplePage>
  );
}

function EditStudent({ id }: { id: number }) {
  const router = useRouter();
  const toast = useToast();
  const loader = useCallback(() => service.getStudent(id), [id]);
  const { record: student, setRecord, loading, error, reload } = useRecord(loader);

  if (error) return <ErrorAlert error={error} onRetry={() => void reload()} />;
  if (loading && !student) return <ProfileSkeleton />;
  if (!student) return null;

  return (
    <div className="people-grid">
      <StudentForm
        key={student.id}
        student={student}
        cancelHref={`/school/students/${student.id}`}
        onRemoveDocument={async (document) => {
          await service.deleteDocument("students", student.id, document.id);
          toast("success", `${document.title} removed.`);
          await reload();
        }}
        onSave={async ({ input, photo, documents }) => {
          const saved = await service.updateStudent(student.id, input);
          const failures = await uploadFiles(service, "students", saved.id, photo, documents);
          if (failures.length) flashMessage(`Changes saved, but some files didn't upload. ${failures.join(" ")}`, "error");
          else flashMessage(`${saved.name} updated.`);
          router.push(`/school/students/${saved.id}`);
        }}
      />
      <GuardianManager student={student} onChange={setRecord} editable={support.guardianLinks} />
    </div>
  );
}
