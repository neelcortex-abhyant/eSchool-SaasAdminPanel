"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AcademicApiError, type Page } from "@/lib/academics";

export function useDebounced<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * Loads one page of records whenever `loader` changes. Responses that arrive after a newer
 * request started are dropped, so fast filter changes never show stale rows.
 */
export function usePagedList<T>(loader: () => Promise<Page<T>>) {
  const [data, setData] = useState<Page<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const requestId = useRef(0);
  // reload() is often called after an await (e.g. once a save finishes). Reading the loader
  // from a ref makes that call use the current filters, not the ones from when the save began.
  const latest = useRef(loader);
  latest.current = loader;

  const reload = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const result = await latest.current();
      if (id === requestId.current) setData(result);
    } catch (caught) {
      if (id === requestId.current) {
        setError(caught);
        setData(null);
      }
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [loader, reload]);

  return { data, loading, error, reload };
}

/** Loads a dropdown's options. Pass `null` as the loader to keep the list empty (e.g. no parent picked yet). */
export function useOptions<T>(loader: (() => Promise<T[]>) | null) {
  const [options, setOptions] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const requestId = useRef(0);

  const reload = useCallback(async () => {
    const id = ++requestId.current;
    if (!loader) {
      setOptions([]);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await loader();
      if (id === requestId.current) setOptions(result);
    } catch (caught) {
      if (id === requestId.current) {
        setOptions([]);
        setError(caught);
      }
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { options, loading, error, reload };
}

/** Field errors and a top-level message for one form. */
export function useFormErrors() {
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");

  const clear = useCallback(() => {
    setFieldErrors({});
    setFormError("");
  }, []);

  const fromError = useCallback((error: unknown, fallback: string) => {
    if (error instanceof AcademicApiError) {
      setFieldErrors(error.fieldErrors);
      setFormError(error.message);
    } else {
      setFieldErrors({});
      setFormError(error instanceof Error && error.message ? error.message : fallback);
    }
  }, []);

  return { fieldErrors, formError, setFieldErrors, setFormError, clear, fromError };
}
