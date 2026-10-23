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
import type { PeopleService } from "@/lib/people/types";

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
};

const FULL_SUPPORT: PeopleSupport = { details: true, guardianLinks: true, files: true, edit: true, status: true, employeeFilters: true };

/**
 * The live backend serves people through the generic /school-admin/academics/{students,parents,
 * teachers} routes: students can be listed, admitted, edited and (de)activated; parents and
 * teachers only listed and created. Staff has no route yet.
 */
const LIVE_SUPPORT: Record<PeopleModule, PeopleSupport> = {
  students: { details: false, guardianLinks: false, files: false, edit: true, status: true, employeeFilters: false },
  parents: { details: false, guardianLinks: false, files: false, edit: false, status: false, employeeFilters: false },
  teachers: { details: false, guardianLinks: false, files: false, edit: false, status: false, employeeFilters: false },
  staff: { details: false, guardianLinks: false, files: false, edit: false, status: false, employeeFilters: false },
};

export function peopleSupport(module: PeopleModule): PeopleSupport {
  return SOURCES[module] === "live" ? LIVE_SUPPORT[module] : FULL_SUPPORT;
}

/** Shown on live pages: what the server can't do yet for this module. */
export const LIVE_LIMITS_NOTE: Record<PeopleModule, string> = {
  students:
    "Connected to the school's server. It keeps the name, email, admission details, class and one guardian per student. Date of birth, gender, phone, address, more guardians, photos and documents aren't stored yet.",
  parents:
    "Connected to the school's server. Parents can be listed and added with name, email and phone. Editing, deactivating, address and occupation aren't available yet.",
  teachers:
    "Connected to the school's server. Teachers can be listed and added with name, email, phone and qualification. Editing, deactivating, employee ID, department, photos and documents aren't available yet.",
  staff: "Staff isn't available on the school's server yet.",
};

export * from "@/lib/people/types";
export { resetMockPeople } from "@/lib/people/mock";
export { errorMessage, formatDate, toId, AcademicApiError } from "@/lib/academics";
