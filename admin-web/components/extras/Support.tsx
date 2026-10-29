"use client";

import { useCallback, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { FormModal } from "@/components/academics/FormModal";
import { SelectField, TextAreaField, TextField } from "@/components/academics/Fields";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { Chip, type ChipTone } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { create, displayValue, getOne, listRows, replace, update, type Raw } from "@/lib/extras/api";
import { str } from "@/lib/teaching/client";
import { IconSettings, IconSupport } from "@/lib/icons";

// ---------- Support tickets (/school-admin/support-tickets) ----------

export const TICKET_STATUS: { value: string; label: string; tone: ChipTone }[] = [
  { value: "open", label: "Open", tone: "blue" },
  { value: "pending", label: "Waiting for reply", tone: "amber" },
  { value: "resolved", label: "Resolved", tone: "green" },
  { value: "closed", label: "Closed", tone: "grey" },
];

const PRIORITIES = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

type Ticket = Raw & { id: number };

function statusChip(value: unknown) {
  const status = TICKET_STATUS.find((item) => item.value === value);
  return <Chip tone={status?.tone ?? "grey"}>{status?.label ?? str(value, "—")}</Chip>;
}

export function SupportPage() {
  const [adding, setAdding] = useState(false);
  return (
    <ExtrasPage
      title="Support"
      description="Ask the eSchool team for help and follow the conversation."
      icon={<IconSupport width={18} height={18} />}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setAdding(true)}>
          New ticket
        </button>
      }
    >
      <SupportBody adding={adding} setAdding={setAdding} />
    </ExtrasPage>
  );
}

function SupportBody({ adding, setAdding }: { adding: boolean; setAdding: (value: boolean) => void }) {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const tickets = useOptions(useCallback(() => listRows("/support-tickets", { status_filter: status || undefined }).then((rows) => (rows as Ticket[]).sort((a, b) => str(b.updated_at).localeCompare(str(a.updated_at)))), [status]));
  const [open, setOpen] = useState<Ticket | null>(null);

  const columns: Column<Ticket>[] = [
    { key: "subject", label: "Subject", render: (row) => <strong>{str(row.subject)}</strong> },
    { key: "priority", label: "Priority", render: (row) => PRIORITIES.find((item) => item.value === row.priority)?.label ?? str(row.priority) },
    { key: "status", label: "Status", render: (row) => statusChip(row.status) },
    { key: "updated", label: "Last update", render: (row) => displayValue(row.updated_at) },
  ];

  return (
    <>
      <div className="school-filters">
        <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All tickets</option>
          {TICKET_STATUS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={tickets.error} onRetry={() => void tickets.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={tickets.options}
          loading={tickets.loading}
          emptyText={tickets.error ? "Tickets couldn't be loaded." : "No support tickets yet."}
          actions={(row) => (
            <button className="link-btn" type="button" onClick={() => setOpen(row)}>
              Open
            </button>
          )}
        />
      </div>
      {adding ? (
        <NewTicket
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            toast("success", "Ticket sent to the eSchool team.");
            void tickets.reload();
          }}
        />
      ) : null}
      {open ? <TicketDialog ticketId={open.id} onClose={() => setOpen(null)} onChanged={() => void tickets.reload()} /> : null}
    </>
  );
}

function NewTicket({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    const invalid: Record<string, string> = {};
    if (!subject.trim()) invalid.subject = "Enter a subject.";
    if (!body.trim()) invalid.body = "Describe the problem.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await create("/support-tickets", { subject: subject.trim(), body: body.trim(), priority });
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to send the ticket.");
      setSaving(false);
    }
  }
  return (
    <FormModal title="New support ticket" error={errors.formError} saving={saving} submitLabel="Send ticket" onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="st-subject" label="Subject" required maxLength={255} value={subject} onChange={setSubject} error={errors.fieldErrors.subject} span />
      <SelectField id="st-priority" label="Priority" value={priority} onChange={setPriority} options={PRIORITIES} />
      <TextAreaField id="st-body" label="What do you need help with?" required rows={6} value={body} onChange={setBody} error={errors.fieldErrors.body} span />
    </FormModal>
  );
}

function TicketDialog({ ticketId, onClose, onChanged }: { ticketId: number; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const ticket = useOptions(useCallback(() => getOne(`/support-tickets/${ticketId}`).then((row) => [row]), [ticketId]));
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const row = ticket.options[0];
  const messages = Array.isArray(row?.messages) ? (row.messages as Raw[]) : [];

  async function act(work: () => Promise<unknown>, done: string) {
    setBusy(true);
    try {
      await work();
      toast("success", done);
      void ticket.reload();
      onChanged();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to update the ticket."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card acad-modal" role="dialog" aria-modal="true" aria-labelledby="ticket-title">
        {!row ? (
          ticket.error ? <ErrorAlert error={ticket.error} onRetry={() => void ticket.reload()} /> : <div className="skeleton" style={{ height: 160 }} />
        ) : (
          <>
            <h2 id="ticket-title">{str(row.subject)}</h2>
            <p className="ticket-meta">
              {statusChip(row.status)} <span className="muted">Opened {displayValue(row.created_at)}</span>
            </p>
            <ol className="ticket-thread">
              <li className="is-mine">
                <p>{str(row.body)}</p>
                <small className="muted">You · {displayValue(row.created_at)}</small>
              </li>
              {messages.map((message) => (
                <li key={str(message.id)} className={str(message.author_type) === "school_admin" ? "is-mine" : undefined}>
                  <p>{str(message.body)}</p>
                  <small className="muted">
                    {str(message.author_type) === "school_admin" ? "You" : "eSchool team"} · {displayValue(message.created_at)}
                  </small>
                </li>
              ))}
            </ol>
            {row.status !== "closed" ? (
              <TextAreaField id="ticket-reply" label="Reply" rows={3} value={reply} onChange={setReply} span />
            ) : null}
            <div className="resource-actions acad-modal-actions">
              {row.status !== "closed" ? (
                <button
                  className="btn-pill btn-pill-green"
                  type="button"
                  disabled={busy || !reply.trim()}
                  onClick={() =>
                    void act(async () => {
                      await create(`/support-tickets/${ticketId}/messages`, { body: reply.trim(), author_type: "school_admin" });
                      setReply("");
                    }, "Reply sent.")
                  }
                >
                  Send reply
                </button>
              ) : null}
              {row.status === "closed" || row.status === "resolved" ? (
                <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={() => void act(() => update(`/support-tickets/${ticketId}`, { status: "open" }), "Ticket reopened.")}>
                  Reopen
                </button>
              ) : (
                <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={() => void act(() => update(`/support-tickets/${ticketId}`, { status: "resolved" }), "Marked as resolved.")}>
                  Mark resolved
                </button>
              )}
              <button className="btn-pill btn-pill-green-soft" type="button" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ---------- Third party API (/school-admin/third-party-integrations) ----------

/** "name=value" lines → an object; blank lines and lines without "=" are skipped. */
export function parseConfigLines(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const at = line.indexOf("=");
    if (at <= 0) continue;
    const key = line.slice(0, at).trim();
    if (key) out[key] = line.slice(at + 1).trim();
  }
  return out;
}

export function configLines(config: unknown): string {
  if (!config || typeof config !== "object") return "";
  return Object.entries(config as Record<string, unknown>)
    .map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : String(value ?? "")}`)
    .join("\n");
}

type Integration = Raw & { id: number };

export function ThirdPartyPage() {
  const [editing, setEditing] = useState<Integration | "new" | null>(null);
  return (
    <ExtrasPage
      title="Third party API"
      description="Keys for other services the school uses, such as SMS or maps."
      icon={<IconSettings width={18} height={18} />}
      note="Secret keys are stored encrypted on the server and are never shown again. WhatsApp and the payment gateway have their own pages."
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add service
        </button>
      }
    >
      <ThirdPartyBody editing={editing} setEditing={setEditing} />
    </ExtrasPage>
  );
}

function ThirdPartyBody({ editing, setEditing }: { editing: Integration | "new" | null; setEditing: (value: Integration | "new" | null) => void }) {
  const toast = useToast();
  const list = useOptions(useCallback(() => getOne("/third-party-integrations").then((data) => (Array.isArray(data.items) ? (data.items as Raw[]) : []).map((row, index) => ({ ...row, id: index + 1 }) as Integration)), []));
  const columns: Column<Integration>[] = [
    { key: "provider", label: "Service", render: (row) => <strong>{str(row.provider)}</strong> },
    { key: "secret", label: "Secret key", render: (row) => (row.configured ? <Chip tone="green">Saved</Chip> : <Chip tone="grey">Not saved</Chip>) },
    { key: "settings", label: "Settings", render: (row) => Object.keys((row.public_config as Raw | null) ?? {}).join(", ") || "—" },
    { key: "updated", label: "Updated", render: (row) => displayValue(row.updated_at) },
  ];
  return (
    <>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.options}
          loading={list.loading}
          emptyText="No services added yet."
          actions={(row) => (
            <button className="link-btn" type="button" onClick={() => setEditing(row)}>
              Edit
            </button>
          )}
        />
      </div>
      {editing ? (
        <IntegrationForm
          row={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            toast("success", "Service saved.");
            void list.reload();
          }}
        />
      ) : null}
    </>
  );
}

function IntegrationForm({ row, onClose, onSaved }: { row: Integration | null; onClose: () => void; onSaved: () => void }) {
  const [provider, setProvider] = useState(row ? str(row.provider) : "");
  const [settings, setSettings] = useState(row ? configLines(row.public_config) : "");
  const [secret, setSecret] = useState("");
  const [clear, setClear] = useState(false);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    const name = provider.trim().toLowerCase().replace(/\s+/g, "_");
    if (!name) {
      errors.setFieldErrors({ provider: "Enter the service name." });
      return;
    }
    if (name === "whatsapp_meta" || name === "fee_payment_gateway") {
      errors.setFieldErrors({ provider: "Use the WhatsApp or Payment settings page for this." });
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await replace(`/third-party-integrations/${encodeURIComponent(name)}`, { public_config: parseConfigLines(settings), ...(secret.trim() ? { secret: secret.trim() } : {}), clear_secret: clear });
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to save the service.");
      setSaving(false);
    }
  }
  return (
    <FormModal title={row ? `Edit ${str(row.provider)}` : "Add service"} error={errors.formError} saving={saving} submitLabel="Save" onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="tp-provider" label="Service name" required maxLength={64} value={provider} onChange={setProvider} disabled={Boolean(row)} error={errors.fieldErrors.provider} hint="For example sms_gateway or google_maps." span />
      <TextAreaField id="tp-settings" label="Settings (not secret)" rows={4} value={settings} onChange={setSettings} placeholder={"sender_id=SCHOOL\nregion=in"} hint="One per line as name=value." span />
      <TextField id="tp-secret" label={row?.configured ? "New secret key (leave empty to keep the saved one)" : "Secret key"} type="password" autoComplete="new-password" value={secret} onChange={setSecret} span />
      {row?.configured ? (
        <label className="acad-check">
          <input type="checkbox" checked={clear} onChange={(event) => setClear(event.target.checked)} />
          <span>Remove the saved secret key</span>
        </label>
      ) : null}
    </FormModal>
  );
}
