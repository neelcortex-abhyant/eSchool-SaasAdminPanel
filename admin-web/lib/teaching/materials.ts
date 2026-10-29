/**
 * Study materials.
 * Live: /school-admin/study-materials (list, JSON create for video and document links),
 * /study-materials/upload (multipart file), /study-materials/{id} (get, PATCH, DELETE),
 * /study-materials/{id}/file (replace) and /study-materials/{id}/download (needs the sign-in
 * token, so files open through auth: links). Uploads need document storage configured on the server.
 */
import { get, num, optStr, pageOf, send, str, uploadWithProgress, type Raw } from "@/lib/teaching/client";
import { isLive } from "@/lib/teaching/mode";
import { placementOf, sectionMap, subjectName, teacherName } from "@/lib/teaching/lookups";
import { db, delay, invalid, matches, nextId, notFound, nowIso, paginate, save } from "@/lib/teaching/store";
import type { Material, MaterialInput, MaterialQuery, MaterialType, Page, Placement } from "@/lib/teaching/types";

export interface MaterialService {
  list(query?: MaterialQuery): Promise<Page<Material>>;
  /** Video or document link (no file). */
  createLink(input: MaterialInput): Promise<Material>;
  /** File upload; onProgress gets 0–100. */
  createFile(input: MaterialInput, file: File, onProgress: (percent: number) => void): Promise<Material>;
  update(id: number, input: MaterialInput): Promise<Material>;
  replaceFile(id: number, file: File, onProgress: (percent: number) => void): Promise<Material>;
  remove(id: number): Promise<void>;
}

const BASE = "/school-admin/study-materials";

/** File types the server accepts for study materials. */
export const MATERIAL_FILE_ACCEPT = ".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.ppt,.pptx,.xls,.xlsx";
export const MATERIAL_MAX_BYTES = 10 * 1024 * 1024;

export function materialFileProblem(file: File): string {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!MATERIAL_FILE_ACCEPT.split(",").includes(`.${extension}`)) return `${file.name} isn't a PDF, image or Office document.`;
  if (file.size > MATERIAL_MAX_BYTES) return `${file.name} is larger than 10 MB.`;
  if (file.size === 0) return `${file.name} is empty.`;
  return "";
}

function materialOf(row: Raw, sections: Map<number, Placement>): Material {
  const place = sections.get(num(row.class_section_id));
  const id = num(row.id);
  return {
    id,
    session_year_id: num(row.session_year_id),
    class_section_id: num(row.class_section_id),
    class_id: place?.class_id ?? 0,
    class_name: place?.class_name ?? `Section #${num(row.class_section_id)}`,
    section_name: place?.section_name ?? "",
    subject_id: num(row.subject_id),
    subject_name: str(row.subject_name),
    teacher_user_id: num(row.teacher_user_id),
    teacher_name: str(row.teacher_name),
    resource_type: str(row.resource_type, "file") as MaterialType,
    title: str(row.title),
    description: optStr(row.description),
    chapter: optStr(row.chapter),
    topic: optStr(row.topic),
    external_url: optStr(row.external_url),
    file: row.has_file
      ? { original_filename: str(row.original_filename, "file"), content_type: str(row.content_type), size_bytes: num(row.size_bytes), url: `auth:${BASE}/${id}/download` }
      : null,
    created_at: str(row.created_at),
  };
}

function metadata(input: MaterialInput) {
  return {
    session_year_id: input.session_year_id,
    class_section_id: input.class_section_id,
    subject_id: input.subject_id,
    teacher_user_id: input.teacher_user_id,
    title: input.title.trim(),
    description: input.description?.trim() || null,
    chapter: input.chapter?.trim() || null,
    topic: input.topic?.trim() || null,
  };
}

function check(input: MaterialInput, file: File | null) {
  const errors: Record<string, string> = {};
  if (!input.session_year_id) errors.session_year_id = "Choose an academic session.";
  if (!input.class_section_id) errors.class_section_id = "Choose a section.";
  if (!input.subject_id) errors.subject_id = "Choose a subject.";
  if (!input.teacher_user_id) errors.teacher_user_id = "Choose a teacher.";
  if (!input.title.trim()) errors.title = "Enter a title.";
  if (input.resource_type !== "file") {
    const url = input.external_url?.trim() ?? "";
    if (!/^https?:\/\/\S+$/i.test(url)) errors.external_url = "Enter a link starting with https://.";
  }
  if (file) {
    const problem = materialFileProblem(file);
    if (problem) errors.file = problem;
  }
  if (Object.keys(errors).length) invalid(errors);
}

export const liveMaterials: MaterialService = {
  async list(query = {}) {
    const [data, sections] = await Promise.all([
      get(BASE, {
        page: query.page ?? 1,
        page_size: Math.min(query.pageSize ?? 20, 50),
        q: query.q?.trim(),
        session_year_id: query.sessionYearId,
        class_section_id: query.classSectionId,
        subject_id: query.subjectId,
        resource_type: query.resourceType,
      }, "Unable to load study materials."),
      sectionMap(),
    ]);
    return pageOf(data, (row) => materialOf(row, sections));
  },
  async createLink(input) {
    check(input, null);
    const [row, sections] = await Promise.all([
      send("POST", BASE, { ...metadata(input), resource_type: input.resource_type, external_url: input.external_url?.trim() || null }, "Unable to add the material."),
      sectionMap(),
    ]);
    return materialOf(row, sections);
  },
  async createFile(input, file, onProgress) {
    check(input, file);
    const form = new FormData();
    for (const [key, value] of Object.entries(metadata(input))) if (value !== null) form.set(key, String(value));
    form.set("file", file);
    const [row, sections] = await Promise.all([uploadWithProgress<Raw>(`${BASE}/upload`, form, "Unable to upload the material.", onProgress), sectionMap()]);
    return materialOf(row, sections);
  },
  async update(id, input) {
    check(input, null);
    const patch = input.resource_type === "file" ? metadata(input) : { ...metadata(input), external_url: input.external_url?.trim() || null };
    const [row, sections] = await Promise.all([send("PATCH", `${BASE}/${id}`, patch, "Unable to save the material."), sectionMap()]);
    return materialOf(row, sections);
  },
  async replaceFile(id, file, onProgress) {
    const problem = materialFileProblem(file);
    if (problem) invalid({ file: problem });
    const form = new FormData();
    form.set("file", file);
    const [row, sections] = await Promise.all([uploadWithProgress<Raw>(`${BASE}/${id}/file`, form, "Unable to replace the file.", onProgress), sectionMap()]);
    return materialOf(row, sections);
  },
  async remove(id) {
    await send("DELETE", `${BASE}/${id}`, undefined, "Unable to delete the material.");
  },
};

// ---------- sample data ----------

function rows(): Material[] {
  return db().materials as Material[];
}

function readFile(file: File): Promise<string | null> {
  if (file.size > 400 * 1024) return Promise.resolve(URL.createObjectURL(file));
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : null);
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(file);
  });
}

/** Fakes upload progress so the sample flow looks like the live one. */
async function fakeProgress(onProgress: (percent: number) => void) {
  for (const percent of [20, 55, 85, 100]) {
    onProgress(percent);
    await new Promise((resolve) => window.setTimeout(resolve, 80));
  }
}

async function build(input: MaterialInput, id: number, file: Material["file"], createdAt: string): Promise<Material> {
  const [placement, subject, teacher] = await Promise.all([
    placementOf(input.session_year_id, input.class_section_id),
    subjectName(input.subject_id),
    teacherName(input.teacher_user_id),
  ]);
  return {
    id,
    ...placement,
    subject_id: input.subject_id,
    subject_name: subject,
    teacher_user_id: input.teacher_user_id,
    teacher_name: teacher,
    resource_type: input.resource_type,
    title: input.title.trim(),
    description: input.description?.trim() || null,
    chapter: input.chapter?.trim() || null,
    topic: input.topic?.trim() || null,
    external_url: input.resource_type === "file" ? null : input.external_url?.trim() || null,
    file,
    created_at: createdAt,
  };
}

export const mockMaterials: MaterialService = {
  async list(query = {}) {
    const list = rows()
      .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
      .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
      .filter((row) => !query.subjectId || row.subject_id === query.subjectId)
      .filter((row) => !query.resourceType || row.resource_type === query.resourceType)
      .filter((row) => matches(query.q, row.title, row.description, row.chapter, row.topic))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    return delay(paginate(list, query.page, query.pageSize));
  },
  async createLink(input) {
    check(input, null);
    const row = await build(input, nextId(rows()), null, nowIso());
    rows().push(row);
    save();
    return delay(row);
  },
  async createFile(input, file, onProgress) {
    check(input, file);
    await fakeProgress(onProgress);
    const row = await build(input, nextId(rows()), { original_filename: file.name, content_type: file.type, size_bytes: file.size, url: await readFile(file) }, nowIso());
    rows().push(row);
    save();
    return delay(row);
  },
  async update(id, input) {
    const index = rows().findIndex((row) => row.id === id);
    if (index < 0) notFound("Study material");
    check(input, null);
    const current = rows()[index];
    const row = await build({ ...input, resource_type: current.resource_type }, id, current.file, current.created_at);
    rows()[index] = row;
    save();
    return delay(row);
  },
  async replaceFile(id, file, onProgress) {
    const row = rows().find((item) => item.id === id) ?? notFound("Study material");
    if (row.resource_type !== "file") invalid({ file: "Only file materials have a file to replace." });
    const problem = materialFileProblem(file);
    if (problem) invalid({ file: problem });
    await fakeProgress(onProgress);
    row.file = { original_filename: file.name, content_type: file.type, size_bytes: file.size, url: await readFile(file) };
    save();
    return delay(row);
  },
  async remove(id) {
    if (!rows().some((row) => row.id === id)) notFound("Study material");
    db().materials = rows().filter((row) => row.id !== id);
    save();
    await delay(null);
  },
};

export function materialService(): MaterialService {
  return isLive("materials") ? liveMaterials : mockMaterials;
}
