"use client";

import { useParams } from "next/navigation";
import SchoolModulePage from "@/components/school-admin/SchoolModulePage";

export default function SchoolModuleRoute() {
  const params = useParams<{ module: string }>();
  return <SchoolModulePage moduleKey={params.module} />;
}
