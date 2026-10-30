"use client";

import { Suspense } from "react";
import { ReportsDashboard } from "@/components/reports/ReportsDashboard";

export default function ReportsAnalyticsPage() {
  return (
    <Suspense fallback={null}>
      <ReportsDashboard />
    </Suspense>
  );
}
