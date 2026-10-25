"use client";

import { useCallback, useRef, useState } from "react";

/** A new idempotency key for one attempt at saving something (e.g. a payment). */
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Runs an action at most once at a time. A second click while the first is still running is
 * ignored (the button should also be disabled with `busy`), so a payment can't be sent twice.
 */
export function useSubmitOnce() {
  const running = useRef(false);
  const [busy, setBusy] = useState(false);
  const run = useCallback(async <T,>(action: () => Promise<T>): Promise<T | undefined> => {
    if (running.current) return undefined;
    running.current = true;
    setBusy(true);
    try {
      return await action();
    } finally {
      running.current = false;
      setBusy(false);
    }
  }, []);
  return { busy, run };
}
