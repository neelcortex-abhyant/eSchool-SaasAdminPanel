"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { ChildrenManager } from "@/components/people/Links";
import { ParentForm } from "@/components/people/ParentForm";
import { PeoplePage, flashMessage, routeId } from "@/components/people/PeoplePage";
import { ProfileSkeleton, useRecord } from "@/components/people/Profile";
import { peopleService, peopleSupport } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const service = peopleService("parents");
const support = peopleSupport("parents");

export default function EditParentPage() {
  const id = routeId(useParams<{ id: string }>().id);
  return (
    <PeoplePage
      module="parents"
      title="Edit parent or guardian"
      icon={<IconUsers width={18} height={18} />}
      back={id ? { href: `/school/parents/${id}`, label: "Parent profile" } : { href: "/school/parents", label: "Parents and guardians" }}
    >
      {id ? <EditParent id={id} /> : <div className="alert alert-danger" role="alert">Parent not found</div>}
    </PeoplePage>
  );
}

function EditParent({ id }: { id: number }) {
  const router = useRouter();
  const loader = useCallback(() => service.getParent(id), [id]);
  const { record: parent, loading, error, reload } = useRecord(loader);

  if (!support.edit) {
    return (
      <div className="alert alert-info" role="status">
        Editing parents isn&apos;t available on the school&apos;s server yet.
      </div>
    );
  }
  if (error) return <ErrorAlert error={error} onRetry={() => void reload()} />;
  if (loading && !parent) return <ProfileSkeleton />;
  if (!parent) return null;

  return (
    <div className="people-grid">
      <ParentForm
        key={parent.id}
        parent={parent}
        cancelHref={`/school/parents/${parent.id}`}
        onSave={async (input) => {
          const saved = await service.updateParent(parent.id, input);
          flashMessage(`${saved.name} updated.`);
          router.push(`/school/parents/${saved.id}`);
        }}
      />
      <ChildrenManager parent={parent} onChanged={reload} />
    </div>
  );
}
