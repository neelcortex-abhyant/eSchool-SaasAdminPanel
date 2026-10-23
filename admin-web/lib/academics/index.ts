/**
 * Picks the live or mock academics client for each page.
 *
 * NEXT_PUBLIC_ACADEMICS_API_MODE:
 *   "mock" (default)  every page uses mock-data.json
 *   "live"            every page calls /api/v1/school-admin/academics
 *   per feature       e.g. "sessions:live,classes:live,sections:mock"
 *                     (also attendance, exams, fees, expenses, notices, leaves for the school module pages)
 *
 * Features left out of a per-feature list use mock. Switch a feature to live once its
 * endpoints in backend/docs/ACADEMICS_API_CONTRACT.md are deployed.
 */
import { httpAcademicsService } from "@/lib/academics/http";
import { mockAcademicsService } from "@/lib/academics/mock";
import type { AcademicsService } from "@/lib/academics/types";

export type AcademicFeature =
  | "sessions"
  | "mediums"
  | "classes"
  | "sections"
  | "subjects"
  | "assignments"
  // School module pages served by components/school-admin/SchoolModulePage.tsx.
  | "attendance"
  | "exams"
  | "fees"
  | "expenses"
  | "notices"
  | "leaves";
export type ApiSource = "live" | "mock";

export const ACADEMIC_FEATURES: AcademicFeature[] = [
  "sessions",
  "mediums",
  "classes",
  "sections",
  "subjects",
  "assignments",
  "attendance",
  "exams",
  "fees",
  "expenses",
  "notices",
  "leaves",
];

export function parseApiMode(raw: string | undefined): Record<AcademicFeature, ApiSource> {
  const value = (raw || "").trim().toLowerCase();
  const all = (source: ApiSource) => Object.fromEntries(ACADEMIC_FEATURES.map((f) => [f, source])) as Record<AcademicFeature, ApiSource>;
  if (value === "live") return all("live");
  const sources = all("mock");
  for (const part of value.split(",")) {
    const [feature, source] = part.split(":").map((s) => s.trim());
    if ((ACADEMIC_FEATURES as string[]).includes(feature) && (source === "live" || source === "mock")) {
      sources[feature as AcademicFeature] = source;
    }
  }
  return sources;
}

const SOURCES = parseApiMode(process.env.NEXT_PUBLIC_ACADEMICS_API_MODE);

export function academicsSource(feature: AcademicFeature): ApiSource {
  return SOURCES[feature];
}

export function academicsService(feature: AcademicFeature): AcademicsService {
  return SOURCES[feature] === "live" ? httpAcademicsService : mockAcademicsService;
}

/** What a page can store. The mock stores everything in the contract. */
export type AcademicsSupport = {
  /** Active/inactive on classes, sections and subjects. */
  status: boolean;
  /** A class tied to one session instead of every session. */
  classSession: boolean;
  /** Compulsory or elective on a subject's class mapping. */
  subjectKind: boolean;
};

/** The live backend has no columns for these yet (backend/docs/ACADEMICS_API_CONTRACT.md). */
export const LIVE_ACADEMICS_LIMITS: AcademicsSupport = { status: false, classSession: false, subjectKind: false };
const FULL_SUPPORT: AcademicsSupport = { status: true, classSession: true, subjectKind: true };

export function academicsSupport(feature: AcademicFeature): AcademicsSupport {
  return SOURCES[feature] === "live" ? LIVE_ACADEMICS_LIMITS : FULL_SUPPORT;
}

export * from "@/lib/academics/types";
export { AcademicApiError, errorMessage } from "@/lib/academics/errors";
export { resetMockAcademics } from "@/lib/academics/mock";
export { formatDate, toId } from "@/lib/academics/format";

/** Reads every page of a list for a dropdown. Stops after 20 pages (1,000 rows at the API's 50-row cap). */
export async function listAll<T>(load: (page: number) => Promise<import("@/lib/academics/types").Page<T>>): Promise<T[]> {
  const rows: T[] = [];
  for (let page = 1; page <= 20; page += 1) {
    const result = await load(page);
    rows.push(...result.items);
    if (result.items.length === 0 || rows.length >= result.total) break;
  }
  return rows;
}
