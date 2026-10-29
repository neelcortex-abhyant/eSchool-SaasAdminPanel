"use client";

import { useCallback, useEffect, useState } from "react";
import { useDebounced, useOptions } from "@/components/academics/hooks";
import { errorMessage, peopleService, type Parent, type StudentRow } from "@/lib/people";

const parentService = peopleService("parents");
const studentService = peopleService("students");

/**
 * Search box with a short result list. Picking a result calls onPick; rows in `excludeIds`
 * (already linked) are shown but can't be picked.
 */
function SearchPicker<T extends { id: number }>({
  id,
  label,
  placeholder,
  search,
  describe,
  excludeIds = [],
  excludedNote,
  onPick,
  error,
}: {
  id: string;
  label: string;
  placeholder: string;
  search: (q: string) => Promise<T[]>;
  describe: (row: T) => { title: string; detail: string };
  excludeIds?: number[];
  excludedNote: string;
  onPick: (row: T) => void;
  error?: string;
}) {
  const [input, setInput] = useState("");
  const q = useDebounced(input.trim(), 250);
  const loader = useCallback(() => search(q), [search, q]);
  const results = useOptions(q.length >= 2 ? loader : null);

  return (
    <div className="form-field field-span people-search-picker">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="search"
        value={input}
        placeholder={placeholder}
        autoComplete="off"
        className={error ? "invalid" : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : `${id}-hint`}
        onChange={(event) => setInput(event.target.value)}
      />
      {error ? (
        <p className="field-error" id={`${id}-error`}>
          {error}
        </p>
      ) : (
        <p className="field-hint" id={`${id}-hint`}>
          Type at least 2 characters.
        </p>
      )}
      {q.length >= 2 ? (
        <ul className="people-results" aria-label={`${label} results`} aria-busy={results.loading}>
          {results.loading ? <li className="muted">Searching…</li> : null}
          {results.error ? <li className="field-error">{errorMessage(results.error)}</li> : null}
          {!results.loading && !results.error && results.options.length === 0 ? <li className="muted">No matches.</li> : null}
          {results.options.map((row) => {
            const text = describe(row);
            const taken = excludeIds.includes(row.id);
            return (
              <li key={row.id}>
                <button
                  type="button"
                  disabled={taken}
                  onClick={() => {
                    onPick(row);
                    setInput("");
                  }}
                >
                  <strong>{text.title}</strong>
                  <span className="muted">{taken ? excludedNote : text.detail}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

const searchParents = async (q: string) => (await parentService.listParents({ q, pageSize: 6 })).items;
const searchStudents = async (q: string) => (await studentService.listStudents({ q, pageSize: 6 })).items;

export function ParentSearch(props: { id: string; excludeIds?: number[]; onPick: (parent: Parent) => void; error?: string; label?: string }) {
  return (
    <SearchPicker<Parent>
      id={props.id}
      label={props.label ?? "Find a parent or guardian"}
      placeholder="Name, email or phone"
      search={searchParents}
      describe={(row) => ({ title: `${row.name}${row.status === 1 ? "" : " (inactive)"}`, detail: [row.email, row.mobile].filter(Boolean).join(" · ") })}
      excludeIds={props.excludeIds}
      excludedNote="Already linked"
      onPick={props.onPick}
      error={props.error}
    />
  );
}

export function StudentSearch(props: { id: string; excludeIds?: number[]; onPick: (student: StudentRow) => void; error?: string; label?: string }) {
  return (
    <SearchPicker<StudentRow>
      id={props.id}
      label={props.label ?? "Find a student"}
      placeholder="Name or admission number"
      search={searchStudents}
      describe={(row) => ({ title: `${row.name}${row.status === 1 ? "" : " (inactive)"}`, detail: `${row.admission_no} · ${row.class_name} ${row.section_name}` })}
      excludeIds={props.excludeIds}
      excludedNote="Already linked"
      onPick={props.onPick}
      error={props.error}
    />
  );
}

/**
 * Looks for an existing parent with the same email or phone while a new one is being typed,
 * so the admin can reuse that record instead of creating a duplicate.
 */
export function useDuplicateParent(email: string, mobile: string, exceptId?: number): Parent | null {
  const debouncedEmail = useDebounced(email.trim(), 400);
  const debouncedMobile = useDebounced(mobile.trim(), 400);
  const [match, setMatch] = useState<Parent | null>(null);

  useEffect(() => {
    let cancelled = false;
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(debouncedEmail);
    const mobileOk = debouncedMobile.replace(/\D/g, "").length >= 7;
    if (!emailOk && !mobileOk) {
      setMatch(null);
      return;
    }
    void (async () => {
      try {
        const [byEmail, byMobile] = await Promise.all([
          emailOk ? parentService.listParents({ email: debouncedEmail, pageSize: 1 }) : null,
          mobileOk ? parentService.listParents({ mobile: debouncedMobile, pageSize: 1 }) : null,
        ]);
        const found = [...(byEmail?.items ?? []), ...(byMobile?.items ?? [])].find((row) => row.id !== exceptId) ?? null;
        if (!cancelled) setMatch(found);
      } catch {
        // The server repeats this check on save, so a failed lookup only skips the early warning.
        if (!cancelled) setMatch(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [debouncedEmail, debouncedMobile, exceptId]);

  return match;
}
