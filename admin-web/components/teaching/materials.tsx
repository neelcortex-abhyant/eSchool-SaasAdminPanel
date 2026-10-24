"use client";

import { useCallback, useState } from "react";
import { SelectField, TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors } from "@/components/academics/hooks";
import { formatBytes } from "@/components/teaching/Frame";
import { EMPTY_PLACEMENT, PlacementFields, SubjectTeacherFields, type PlacementValue } from "@/components/teaching/Pickers";
import { MATERIAL_FILE_ACCEPT, materialFileProblem, materialService } from "@/lib/teaching/materials";
import type { Material, MaterialInput, MaterialType } from "@/lib/teaching/types";

export const MATERIAL_TYPE_LABEL: Record<MaterialType, string> = {
  file: "File",
  video_link: "Video link",
  document_reference: "Document link",
};

export const MATERIALS_LIVE_NOTE = "Connected to the school's server. File uploads need document storage to be set up on the server; links work without it.";

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="teach-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Upload progress">
      <span style={{ width: `${percent}%` }} />
      <em>{percent}%</em>
    </div>
  );
}

function FileInput({ id, label, file, onFile, error }: { id: string; label: string; file: File | null; onFile: (file: File | null, problem: string) => void; error?: string }) {
  return (
    <div className="form-field field-span">
      <label htmlFor={id}>{label} *</label>
      <input
        id={id}
        type="file"
        accept={MATERIAL_FILE_ACCEPT}
        className={error ? "invalid" : undefined}
        aria-invalid={Boolean(error)}
        onChange={(event) => {
          const picked = event.target.files?.[0] ?? null;
          onFile(picked, picked ? materialFileProblem(picked) : "");
        }}
      />
      {error ? <p className="field-error">{error}</p> : <p className="field-hint">{file ? `${file.name} (${formatBytes(file.size)})` : "PDF, images or Office files, up to 10 MB."}</p>}
    </div>
  );
}

/** Add a material (file upload or link) or edit its details. */
export function MaterialForm({ material, onClose, onSaved }: { material: Material | null; onClose: () => void; onSaved: (saved: Material, created: boolean) => void }) {
  const [placement, setPlacement] = useState<PlacementValue>(
    material ? { session_year_id: String(material.session_year_id), class_id: String(material.class_id), class_section_id: String(material.class_section_id) } : EMPTY_PLACEMENT,
  );
  const [subjectId, setSubjectId] = useState(material ? String(material.subject_id) : "");
  const [teacherId, setTeacherId] = useState(material ? String(material.teacher_user_id) : "");
  const [type, setType] = useState<MaterialType>(material?.resource_type ?? "file");
  const [title, setTitle] = useState(material?.title ?? "");
  const [description, setDescription] = useState(material?.description ?? "");
  const [chapter, setChapter] = useState(material?.chapter ?? "");
  const [topic, setTopic] = useState(material?.topic ?? "");
  const [url, setUrl] = useState(material?.external_url ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const onPlacement = useCallback((value: PlacementValue) => setPlacement(value), []);
  const onTeacher = useCallback((value: string) => setTeacherId(value), []);

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!placement.session_year_id) invalid.session_year_id = "Choose an academic session.";
    if (!placement.class_id) invalid.class_id = "Choose a class.";
    if (!placement.class_section_id) invalid.class_section_id = "Choose a section.";
    if (!subjectId) invalid.subject_id = "Choose a subject.";
    if (!teacherId) invalid.teacher_user_id = "Choose a teacher.";
    if (!title.trim()) invalid.title = "Enter a title.";
    if (type !== "file" && !/^https?:\/\/\S+$/i.test(url.trim())) invalid.external_url = "Enter a link starting with https://.";
    if (type === "file" && !material) {
      if (!file) invalid.file = "Choose a file to upload.";
      else if (materialFileProblem(file)) invalid.file = materialFileProblem(file);
    }
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    const input: MaterialInput = {
      session_year_id: Number(placement.session_year_id),
      class_section_id: Number(placement.class_section_id),
      subject_id: Number(subjectId),
      teacher_user_id: Number(teacherId),
      resource_type: type,
      title: title.trim(),
      description: description.trim() || null,
      chapter: chapter.trim() || null,
      topic: topic.trim() || null,
      external_url: type === "file" ? null : url.trim(),
    };
    try {
      const service = materialService();
      let saved: Material;
      if (material) saved = await service.update(material.id, input);
      else if (type === "file" && file) {
        setProgress(0);
        saved = await service.createFile(input, file, setProgress);
      } else saved = await service.createLink(input);
      onSaved(saved, !material);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the material.");
      setProgress(null);
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={material ? "Edit study material" : "Add study material"}
      error={errors.formError}
      saving={saving}
      submitLabel={material ? "Save changes" : type === "file" ? "Upload" : "Add material"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <PlacementFields idPrefix="sm" value={placement} onChange={onPlacement} errors={errors.fieldErrors} />
      <SubjectTeacherFields idPrefix="sm" placement={placement} subjectId={subjectId} teacherId={teacherId} onSubject={setSubjectId} onTeacher={onTeacher} errors={errors.fieldErrors} />
      <SelectField
        id="sm-type"
        label="Type"
        required
        value={type}
        disabled={Boolean(material)}
        onChange={(value) => setType(value as MaterialType)}
        options={(Object.keys(MATERIAL_TYPE_LABEL) as MaterialType[]).map((value) => ({ value, label: MATERIAL_TYPE_LABEL[value] }))}
        hint={material ? "The type can't change after a material is added." : undefined}
      />
      <TextField id="sm-title" label="Title" required maxLength={200} value={title} onChange={setTitle} error={errors.fieldErrors.title} />
      <TextField id="sm-chapter" label="Chapter" maxLength={120} value={chapter} onChange={setChapter} error={errors.fieldErrors.chapter} />
      <TextField id="sm-topic" label="Topic" maxLength={120} value={topic} onChange={setTopic} error={errors.fieldErrors.topic} />
      <TextAreaField id="sm-description" label="Description" span maxLength={2000} value={description} onChange={setDescription} error={errors.fieldErrors.description} />
      {type !== "file" ? (
        <TextField
          id="sm-url"
          label={type === "video_link" ? "Video link" : "Document link"}
          required
          span
          placeholder="https://"
          value={url}
          onChange={setUrl}
          error={errors.fieldErrors.external_url}
        />
      ) : !material ? (
        <FileInput
          id="sm-file"
          label="File"
          file={file}
          error={errors.fieldErrors.file}
          onFile={(picked, problem) => {
            setFile(picked);
            errors.setFieldErrors({ ...errors.fieldErrors, file: problem });
          }}
        />
      ) : (
        <p className="field-hint field-span">Use Replace file in the list to upload a new version of the file.</p>
      )}
      {progress !== null ? <ProgressBar percent={progress} /> : null}
    </FormModal>
  );
}

/** Upload a new version of a file material. */
export function ReplaceFileForm({ material, onClose, onSaved }: { material: Material; onClose: () => void; onSaved: (saved: Material) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    if (!file) {
      setProblem("Choose a file to upload.");
      return;
    }
    if (problem) return;
    errors.clear();
    setSaving(true);
    setProgress(0);
    try {
      onSaved(await materialService().replaceFile(material.id, file, setProgress));
    } catch (caught) {
      errors.fromError(caught, "Unable to replace the file.");
      setProgress(null);
      setSaving(false);
    }
  }

  return (
    <FormModal
      title="Replace file"
      description={`${material.title}${material.file ? ` · now ${material.file.original_filename}` : ""}`}
      error={errors.formError || errors.fieldErrors.file}
      saving={saving}
      submitLabel="Upload new file"
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <FileInput
        id="sm-replace"
        label="New file"
        file={file}
        error={problem}
        onFile={(picked, reason) => {
          setFile(picked);
          setProblem(reason);
        }}
      />
      {progress !== null ? <ProgressBar percent={progress} /> : null}
    </FormModal>
  );
}
