"use client";

import { useRouter } from "next/navigation";
import { ParentForm } from "@/components/people/ParentForm";
import { PeoplePage, flashMessage } from "@/components/people/PeoplePage";
import { peopleService, type ParentCreateInput } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const service = peopleService("parents");

export default function AddParentPage() {
  const router = useRouter();
  return (
    <PeoplePage
      module="parents"
      title="Add parent or guardian"
      description="Fields marked * are required."
      icon={<IconUsers width={18} height={18} />}
      back={{ href: "/school/parents", label: "Parents and guardians" }}
    >
      <ParentForm
        parent={null}
        cancelHref="/school/parents"
        onSave={async (input) => {
          const parent = await service.createParent(input as ParentCreateInput);
          flashMessage(`${parent.name} was added${parent.children.length ? ` and linked to ${parent.children.map((c) => c.name).join(", ")}` : ""}.`);
          router.push(`/school/parents/${parent.id}`);
        }}
      />
    </PeoplePage>
  );
}
