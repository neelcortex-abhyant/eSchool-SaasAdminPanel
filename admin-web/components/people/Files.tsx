"use client";

import { useEffect, useId, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { Avatar } from "@/components/people/Profile";
import { errorMessage } from "@/lib/academics";
import { apiBlobUrl } from "@/lib/api";
import {
  DOCUMENT_ACCEPT,
  DOCUMENT_MAX_BYTES,
  DOCUMENTS_PER_RECORD,
  PHOTO_ACCEPT,
  PHOTO_MAX_BYTES,
  documentProblem,
  formatBytes,
  photoProblem,
  titleFromFileName,
} from "@/lib/people/files";
import type { FileOwner, PeopleService, StoredFile } from "@/lib/people";

/** A document picked in a form that is uploaded after the record is saved. */
export type PendingDocument = { key: string; file: File; title: string };

/** Picks a profile photo with a preview. The photo uploads when the form is saved. */
export function PhotoPicker({
  id,
  name,
  currentUrl,
  file,
  onChange,
  error,
}: {
  id: string;
  name: string;
  currentUrl: string | null;
  file: File | null;
  onChange: (file: File | null) => void;
  error?: string;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [problem, setProblem] = useState("");

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const message = problem || error;
  return (
    <div className="form-field field-span">
      <label htmlFor={id}>Profile photo</label>
      <div className="people-photo-picker">
        <Avatar name={name || "?"} photoUrl={preview ?? currentUrl} size={64} />
        <div>
          <input
            id={id}
            type="file"
            accept={PHOTO_ACCEPT}
            aria-describedby={`${id}-hint`}
            aria-invalid={Boolean(message)}
            onChange={(event) => {
              const picked = event.target.files?.[0] ?? null;
              event.target.value = "";
              if (!picked) return;
              const reason = photoProblem(picked);
              setProblem(reason);
              onChange(reason ? null : picked);
            }}
          />
          {file ? (
            <button className="link-btn" type="button" onClick={() => onChange(null)}>
              Remove {file.name}
            </button>
          ) : null}
          {message ? (
            <p className="field-error" id={`${id}-hint`}>
              {message}
            </p>
          ) : (
            <p className="field-hint" id={`${id}-hint`}>
              JPG, PNG or WebP, up to {formatBytes(PHOTO_MAX_BYTES)}.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/** Picks documents to upload with a title for each. Nothing uploads until the form is saved. */
export function DocumentPicker({
  id,
  pending,
  onChange,
  existingCount = 0,
  suggestions = [],
}: {
  id: string;
  pending: PendingDocument[];
  onChange: (documents: PendingDocument[]) => void;
  existingCount?: number;
  suggestions?: string[];
}) {
  const [problems, setProblems] = useState<string[]>([]);
  const listId = useId();
  const room = DOCUMENTS_PER_RECORD - existingCount - pending.length;

  function add(files: FileList | null) {
    if (!files) return;
    const errors: string[] = [];
    const accepted: PendingDocument[] = [];
    for (const file of Array.from(files)) {
      const reason = documentProblem(file);
      if (reason) errors.push(reason);
      else if (accepted.length >= room) errors.push(`${file.name} wasn't added. A record can hold up to ${DOCUMENTS_PER_RECORD} documents.`);
      else accepted.push({ key: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`, file, title: titleFromFileName(file.name) });
    }
    setProblems(errors);
    if (accepted.length) onChange([...pending, ...accepted]);
  }

  return (
    <div className="form-field field-span">
      <label htmlFor={id}>Documents</label>
      <input id={id} type="file" multiple accept={DOCUMENT_ACCEPT} disabled={room <= 0} onChange={(event) => { add(event.target.files); event.target.value = ""; }} />
      <p className="field-hint">
        PDF, JPG or PNG, up to {formatBytes(DOCUMENT_MAX_BYTES)} each and {DOCUMENTS_PER_RECORD} per record.
        {suggestions.length ? ` Usually: ${suggestions.join(", ")}.` : ""}
      </p>
      {problems.map((problem) => (
        <p key={problem} className="field-error" role="alert">
          {problem}
        </p>
      ))}
      {pending.length ? (
        <ul className="people-doc-list" aria-label="Documents to upload">
          {pending.map((document, index) => (
            <li key={document.key}>
              <input
                aria-label={`Title for ${document.file.name}`}
                value={document.title}
                maxLength={120}
                list={listId}
                onChange={(event) => onChange(pending.map((item, i) => (i === index ? { ...item, title: event.target.value } : item)))}
              />
              <span className="muted">
                {document.file.name} · {formatBytes(document.file.size)}
              </span>
              <button className="link-btn acad-danger-link" type="button" onClick={() => onChange(pending.filter((_, i) => i !== index))}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {suggestions.length ? (
        <datalist id={listId}>
          {suggestions.map((suggestion) => (
            <option key={suggestion} value={suggestion} />
          ))}
        </datalist>
      ) : null}
    </div>
  );
}

/** Documents already stored for a record, with view and remove. */
export function StoredDocuments({
  documents,
  onRemove,
  emptyText = "No documents uploaded.",
}: {
  documents: StoredFile[];
  onRemove?: (document: StoredFile) => Promise<void>;
  emptyText?: string;
}) {
  const [confirm, setConfirm] = useState<StoredFile | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  if (documents.length === 0) return <p className="muted people-empty">{emptyText}</p>;
  return (
    <>
      {error ? (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      ) : null}
      <ul className="people-doc-list is-stored">
        {documents.map((document) => (
          <li key={document.id}>
            <span className="people-doc-icon" aria-hidden>
              {document.content_type === "application/pdf" ? "PDF" : "IMG"}
            </span>
            <span className="people-doc-name">
              <strong>{document.title}</strong>
              <span className="muted">
                {document.file_name} · {formatBytes(document.size)}
              </span>
            </span>
            {document.url && safeFileUrl(document.url) ? (
              <button
                className="link-btn"
                type="button"
                onClick={() => {
                  setError("");
                  openFile(document.url as string).catch(() => setError(`${document.title} couldn't be opened. Try again.`));
                }}
              >
                View
              </button>
            ) : (
              <span className="muted">Preview unavailable</span>
            )}
            {onRemove ? (
              <button className="link-btn acad-danger-link" type="button" onClick={() => setConfirm(document)}>
                Remove
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {confirm && onRemove ? (
        <ConfirmDialog
          title={`Remove ${confirm.title}?`}
          body="The file is deleted from this record. Upload it again if you need it back."
          confirmLabel="Remove document"
          tone="danger"
          pending={pending}
          onCancel={() => setConfirm(null)}
          onConfirm={async () => {
            setPending(true);
            setError("");
            try {
              await onRemove(confirm);
              setConfirm(null);
            } catch (caught) {
              setError(errorMessage(caught, "Unable to remove the document."));
              setConfirm(null);
            } finally {
              setPending(false);
            }
          }}
        />
      ) : null}
    </>
  );
}

/**
 * Only links the browser can safely open: the API's https links, API downloads that need the
 * sign-in token (auth:/path), or local previews in mock mode.
 */
export function safeFileUrl(url: string): boolean {
  return /^(https?:|blob:|auth:\/|data:(image\/(png|jpeg|webp)|application\/pdf);)/i.test(url) || url.startsWith("/");
}

/**
 * Opens a stored file in a new tab. auth: links are fetched with the sign-in token, and data:
 * URLs (blocked as tabs) are converted; both open as blob: URLs.
 */
export async function openFile(url: string) {
  if (!url.startsWith("data:") && !url.startsWith("auth:")) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  // Open the tab now, while the click still counts as a user action, then point it at the file.
  const tab = window.open("", "_blank");
  let objectUrl: string;
  try {
    objectUrl = url.startsWith("auth:") ? await apiBlobUrl(url.slice("auth:".length)) : URL.createObjectURL(await (await fetch(url)).blob());
  } catch (caught) {
    tab?.close();
    throw caught;
  }
  if (tab) tab.location.href = objectUrl;
  else window.open(objectUrl, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

/**
 * Uploads a saved form's photo and documents. Each file is tried even if an earlier one
 * fails, and the failures come back as messages so the page can say what didn't upload.
 */
export async function uploadFiles(
  service: PeopleService,
  owner: FileOwner,
  id: number,
  photo: File | null,
  documents: PendingDocument[],
): Promise<string[]> {
  const failures: string[] = [];
  if (photo) {
    try {
      await service.uploadPhoto(owner, id, photo);
    } catch (caught) {
      failures.push(`Photo: ${errorMessage(caught, "upload failed")}`);
    }
  }
  for (const document of documents) {
    try {
      await service.uploadDocument(owner, id, document.file, document.title.trim() || titleFromFileName(document.file.name));
    } catch (caught) {
      failures.push(`${document.file.name}: ${errorMessage(caught, "upload failed")}`);
    }
  }
  return failures;
}
