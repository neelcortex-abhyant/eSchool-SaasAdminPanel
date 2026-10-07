import type { Metadata } from "next";
import LandingPage from "@/components/marketing/LandingPage";

export const metadata: Metadata = {
  title: "SchoolSarthi — Smart school management platform",
  description:
    "Manage students, teachers, attendance, academics, fees, and school operations from one modern SaaS console.",
};

export default function HomePage() {
  return <LandingPage />;
}
