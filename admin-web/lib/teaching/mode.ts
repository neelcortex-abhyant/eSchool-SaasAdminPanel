/**
 * Picks live or sample data for each teaching module.
 *
 * NEXT_PUBLIC_TEACHING_API_MODE:
 *   "mock" (default)  every module uses sample data kept in this browser
 *   "live"            every module calls the backend's /api/v1/school-admin routes
 *   per module        e.g. "timetable:live,homework:live,attendance:mock"
 *
 * Modules: attendance, timetable (class timetable and teacher schedules), homework,
 * materials (study materials), exams (online exams) and offline (offline exams: timetable,
 * marks and results).
 */
export type TeachingModule = "attendance" | "timetable" | "homework" | "materials" | "exams" | "offline";
export type ApiSource = "live" | "mock";

export const TEACHING_MODULES: TeachingModule[] = ["attendance", "timetable", "homework", "materials", "exams", "offline"];

export function parseTeachingMode(raw: string | undefined): Record<TeachingModule, ApiSource> {
  const value = (raw || "").trim().toLowerCase();
  const all = (source: ApiSource) => Object.fromEntries(TEACHING_MODULES.map((m) => [m, source])) as Record<TeachingModule, ApiSource>;
  if (value === "live") return all("live");
  const sources = all("mock");
  for (const part of value.split(",")) {
    const [module, source] = part.split(":").map((s) => s.trim());
    if ((TEACHING_MODULES as string[]).includes(module) && (source === "live" || source === "mock")) {
      sources[module as TeachingModule] = source;
    }
  }
  return sources;
}

const SOURCES = parseTeachingMode(process.env.NEXT_PUBLIC_TEACHING_API_MODE);

export function teachingSource(module: TeachingModule): ApiSource {
  return SOURCES[module];
}

export function isLive(module: TeachingModule): boolean {
  return SOURCES[module] === "live";
}
