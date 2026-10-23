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

export * from "@/lib/people/types";
export { resetMockPeople } from "@/lib/people/mock";
export { errorMessage, formatDate, toId, AcademicApiError } from "@/lib/academics";
