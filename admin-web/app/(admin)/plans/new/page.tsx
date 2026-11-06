"use client";

import { PageHeading } from "@/components/ui/PageHeading";
import { PlanForm } from "@/components/billing/PlanForm";
import { IconPackage } from "@/lib/icons";

export default function NewPlanPage() {
  return (
    <div>
      <PageHeading title="Create subscription plan" description="Set prices, limits, and status" icon={<IconPackage width={20} height={20} />} />
      <PlanForm mode="create" />
    </div>
  );
}
