"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { ChildrenManager } from "@/components/people/Links";
import { PeoplePage, routeId } from "@/components/people/PeoplePage";
import { InfoCard, ProfileHeader, ProfileSkeleton, useRecord } from "@/components/people/Profile";
import { StatusAction } from "@/components/people/StatusAction";
import { peopleService, peopleSupport } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const service = peopleService("parents");
const support = peopleSupport("parents");

export default function ParentProfilePage() {
  const id = routeId(useParams<{ id: string }>().id);
  return (
    <PeoplePage module="parents" title="Parent profile" icon={<IconUsers width={18} height={18} />} back={{ href: "/school/parents", label: "Parents and guardians" }}>
      {id ? <ParentProfile id={id} /> : <div className="alert alert-danger" role="alert">Parent not found</div>}
    </PeoplePage>
  );
}

function ParentProfile({ id }: { id: number }) {
  const loader = useCallback(() => service.getParent(id), [id]);
  const { record: parent, setRecord, loading, error, reload } = useRecord(loader);

  if (error) return <ErrorAlert error={error} onRetry={() => void reload()} />;
  if (loading && !parent) return <ProfileSkeleton />;
  if (!parent) return null;

  return (
    <div className="people-grid">
      <ProfileHeader
        name={parent.name}
        photoUrl={null}
        active={parent.status === 1}
        meta={`${parent.children.length} linked ${parent.children.length === 1 ? "student" : "students"}`}
        actions={
          <>
            {support.edit ? (
              <Link className="btn-pill btn-pill-green" href={`/school/parents/${parent.id}/edit`}>
                Edit parent
              </Link>
            ) : null}
            {support.status ? (
              <StatusAction
                name={parent.name}
                noun="parent"
                active={parent.status === 1}
                deactivateEffect={`${parent.name} won't be able to sign in to the parent app. Their links to students are kept.`}
                change={(next) => service.setParentStatus(parent.id, next)}
                onChanged={setRecord}
              />
            ) : null}
          </>
        }
      />
      <div className="people-columns">
        <InfoCard
          title="Personal information"
          rows={[
            { label: "First name", value: parent.first_name },
            { label: "Last name", value: parent.last_name },
            { label: "Occupation", value: parent.occupation },
            { label: "Account status", value: parent.status === 1 ? "Active" : "Inactive" },
          ]}
        />
        <InfoCard
          title="Contact details"
          rows={[
            { label: "Email", value: <a href={`mailto:${parent.email}`}>{parent.email}</a> },
            { label: "Phone", value: <a href={`tel:${parent.mobile}`}>{parent.mobile}</a> },
            { label: "Address", value: parent.current_address },
          ]}
        />
      </div>
      <ChildrenManager parent={parent} onChanged={reload} editable={false} manageHref={support.edit ? `/school/parents/${parent.id}/edit` : undefined} />
    </div>
  );
}
