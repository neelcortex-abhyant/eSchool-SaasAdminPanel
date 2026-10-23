"use client";

import { useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { useToast } from "@/components/academics/Toasts";
import { errorMessage, type RecordStatus } from "@/lib/people";

/**
 * Activate/Deactivate button with a confirmation step. `change` calls the status API and
 * returns the saved record; `onChanged` gets it so the page shows fresh data.
 */
export function StatusAction<T>({
  name,
  active,
  noun,
  deactivateEffect,
  change,
  onChanged,
  variant = "button",
}: {
  name: string;
  active: boolean;
  noun: string;
  /** What deactivating does, shown in the confirmation. */
  deactivateEffect: string;
  change: (status: RecordStatus) => Promise<T>;
  onChanged: (saved: T) => void | Promise<void>;
  variant?: "button" | "link";
}) {
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const next: RecordStatus = active ? 0 : 1;

  async function confirm() {
    setPending(true);
    try {
      const saved = await change(next);
      setConfirming(false);
      toast("success", `${name} is now ${next === 1 ? "active" : "inactive"}.`);
      await onChanged(saved);
    } catch (caught) {
      setConfirming(false);
      toast("error", errorMessage(caught, `Unable to change the ${noun}'s status.`));
    } finally {
      setPending(false);
    }
  }

  const label = active ? "Deactivate" : "Activate";
  return (
    <>
      <button
        className={variant === "link" ? `link-btn${active ? " acad-danger-link" : ""}` : `btn-pill ${active ? "btn-pill-danger" : "btn-pill-green-soft"}`}
        type="button"
        onClick={() => setConfirming(true)}
      >
        {label}
        {variant === "link" ? <span className="acad-sr"> {name}</span> : null}
      </button>
      {confirming ? (
        <ConfirmDialog
          title={`${label} ${name}?`}
          body={active ? deactivateEffect : `${name} will be active again and can sign in and appear in lists and dropdowns.`}
          confirmLabel={label}
          tone={active ? "danger" : "default"}
          pending={pending}
          onConfirm={() => void confirm()}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
    </>
  );
}
