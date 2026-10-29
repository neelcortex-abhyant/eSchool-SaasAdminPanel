/**
 * Picks the live or mock people client for each module.
 *
 * NEXT_PUBLIC_PEOPLE_API_MODE:
 *   "mock" (default)  every module uses mock-data.json
 *   "live"            every module calls /api/v1/school-admin
 *   per module        e.g. "students:live,parents:live,teachers:mock"
 *
 * Modules left out of a per-module list use mock. Switch a module to live once its
 * endpoints in backend/docs/PEOPLE_API_CONTRACT.md are deployed.
 */
import { httpPeopleService } from "@/lib/people/http";
import { mockPeopleService } from "@/lib/people/mock";
import { EMPLOYMENT_STATUSES, EMPLOYMENT_TYPES, type PeopleService } from "@/lib/people/types";

export type PeopleModule = "students" | "parents" | "teachers" | "staff";
export type ApiSource = "live" | "mock";

export const PEOPLE_MODULES: PeopleModule[] = ["students", "parents", "teachers", "staff"];

export function parsePeopleMode(raw: string | undefined): Record<PeopleModule, ApiSource> {
  const value = (raw || "").trim().toLowerCase();
  const all = (source: ApiSource) => Object.fromEntries(PEOPLE_MODULES.map((m) => [m, source])) as Record<PeopleModule, ApiSource>;
  if (value === "live") return all("live");
  const sources = all("mock");
  for (const part of value.split(",")) {
    const [module, source] = part.split(":").map((s) => s.trim());
    if ((PEOPLE_MODULES as string[]).includes(module) && (source === "live" || source === "mock")) {
      sources[module as PeopleModule] = source;
    }
  }
  return sources;
}

const SOURCES = parsePeopleMode(process.env.NEXT_PUBLIC_PEOPLE_API_MODE);

export function peopleSource(module: PeopleModule): ApiSource {
  return SOURCES[module];
}

export function peopleService(module: PeopleModule): PeopleService {
  return SOURCES[module] === "live" ? httpPeopleService : mockPeopleService;
}

/** What a module can do. The mock does everything in backend/docs/PEOPLE_API_CONTRACT.md. */
export type PeopleSupport = {
  /** Date of birth, gender, phone, addresses, occupation, and employee details beyond name and contact. */
  details: boolean;
  /** Several guardians per student with relationships, linked and unlinked from profiles. */
  guardianLinks: boolean;
  /** Photos and documents. */
  files: boolean;
  /** Editing a record after it's created. */
  edit: boolean;
  /** Activating and deactivating. */
  status: boolean;
  /** Department and employment type for teachers and staff. */
  employeeFilters: boolean;
  /** Choices for the employment field: employment type (sample data) or employment status (live). */
  employmentOptions: { value: string; label: string }[];
  /** "Employment type" (sample data) or "Employment status" (live). */
  employmentLabel: string;
  /** The live backend needs a sign-in password when a teacher or staff member is added. */
  password: boolean;
  /** Document titles the backend keeps (as categories); null allows any title. */
  documentTitles: string[] | null;
};

const FULL_SUPPORT: PeopleSupport = {
  details: true,
  guardianLinks: true,
  files: true,
  edit: true,
  status: true,
  employeeFilters: true,
  employmentOptions: EMPLOYMENT_TYPES.map((type) => ({ value: type, label: type })),
  employmentLabel: "Employment type",
  password: false,
  documentTitles: null,
};

const EMPLOYEES_LIVE: PeopleSupport = { ...FULL_SUPPORT, guardianLinks: false, employmentOptions: EMPLOYMENT_STATUSES, employmentLabel: "Employment status", password: true };

/**
 * Live: students and parents use /school-admin/students and /school-admin/parents (profiles,
 * guardians, status, photos and documents); teachers and staff use /school-admin/teachers and
 * /school-admin/staff. New parents get a server-generated password, so no password is asked
 * for them; teachers and staff still need one.
 */
const LIVE_SUPPORT: Record<PeopleModule, PeopleSupport> = {
  students: FULL_SUPPORT,
  parents: FULL_SUPPORT,
  teachers: EMPLOYEES_LIVE,
  staff: EMPLOYEES_LIVE,
};

export function peopleSupport(module: PeopleModule): PeopleSupport {
  return SOURCES[module] === "live" ? LIVE_SUPPORT[module] : FULL_SUPPORT;
}

/** Shown on live pages: what the server can't do yet for this module. */
export const LIVE_LIMITS_NOTE: Record<PeopleModule, string> = {
  students:
    "Connected to the school's server. A student can have up to 4 guardians and must keep at least one. Photos and documents are PDF, JPG or PNG (photos up to 2 MB, documents up to 5 MB).",
  parents:
    "Connected to the school's server. New parents don't get a password here: they set one with “Forgot password” on the sign-in page.",
  teachers:
    "Connected to the school's server. Employment shows the employee's status (active, on leave, resigned or terminated).",
  staff:
    "Connected to the school's server. Employment shows the employee's status (active, on leave, resigned or terminated).",
};

export * from "@/lib/people/types";
export { resetMockPeople } from "@/lib/people/mock";
export { errorMessage, formatDate, toId, AcademicApiError } from "@/lib/academics";
