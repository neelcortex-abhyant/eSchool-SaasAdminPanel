import type { ReactNode } from "react";

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  pending,
  tone = "default",
  onConfirm,
  onCancel,
}: {
  title: string;
  /** Text, or content such as a confirmation field. */
  body: ReactNode;
  confirmLabel: string;
  pending: boolean;
  tone?: "default" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">{title}</h2>
        {typeof body === "string" ? <p>{body}</p> : <div className="confirm-body">{body}</div>}
        <div className="page-actions">
          <button className={`btn-pill ${tone === "danger" ? "btn-pill-danger" : "btn-pill-green"}`} type="button" disabled={pending} onClick={onConfirm}>
            {pending ? "Saving…" : confirmLabel}
          </button>
          <button className="btn-pill btn-pill-green-soft" type="button" disabled={pending} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
