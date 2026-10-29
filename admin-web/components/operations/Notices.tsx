"use client";

import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { Chip, Stat, type ChipTone } from "@/components/teaching/Frame";
import { useCurrentSessionId } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { displayValue } from "@/lib/extras/api";
import { refOptions } from "@/lib/extras/refs";
import { isOperationsLive, OPERATIONS_SAMPLE_NOTE } from "@/lib/operations/mode";
import { canChange, deleteAnnouncement, filterNotifications, listAnnouncements, listNotifications, saveAnnouncement, sendNotification } from "@/lib/operations/notices";
import { AUDIENCES, type Announcement, type Audience, type DeliveryStatus, type NoticeStatus, type NotificationRecord } from "@/lib/operations/types";
import { useSubmitOnce } from "@/lib/ops/submit";
import { IconBell } from "@/lib/icons";

export const NOTICE_TABS = [
  { href: "/school/announcement", label: "Announcements" },
  { href: "/school/notification", label: "Notifications" },
];

const icon = <IconBell width={18} height={18} />;
const note = () => (isOperationsLive("notices") ? undefined : OPERATIONS_SAMPLE_NOTE.notices);
const PAGE_SIZE = 20;

const STATUS: Record<NoticeStatus, { label: string; tone: ChipTone }> = {
  draft: { label: "Draft", tone: "grey" },
  scheduled: { label: "Scheduled", tone: "blue" },
  published: { label: "Published", tone: "green" },
};

const DELIVERY: Record<DeliveryStatus, { label: string; tone: ChipTone }> = {
  queued: { label: "Queued", tone: "blue" },
  sent: { label: "Delivered", tone: "green" },
  partial: { label: "Partly delivered", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
};

export function audienceLabel(audience: Audience[]): string {
  if (audience.includes("all")) return "Everyone";
  return audience.map((item) => AUDIENCES.find((row) => row.value === item)?.label ?? item).join(", ");
}

function AudiencePicker({ value, onChange, error }: { value: Audience[]; onChange: (value: Audience[]) => void; error?: string }) {
  const toggle = (item: Audience, on: boolean) => {
    if (item === "all") return onChange(on ? ["all"] : []);
    const next = value.filter((row) => row !== "all" && row !== item);
    onChange(on ? [...next, item] : next);
  };
  return (
    <fieldset className="form-field field-span">
      <legend>Who it's for *</legend>
      <div className="notice-audience">
        {AUDIENCES.map((item) => (
          <label key={item.value} className="acad-check">
            <input type="checkbox" checked={value.includes(item.value)} onChange={(event) => toggle(item.value, event.target.checked)} />
            <span>{item.label}</span>
          </label>
        ))}
      </div>
      {error ? <p className="field-error">{error}</p> : null}
    </fieldset>
  );
}

// ---------- Announcements ----------

export function AnnouncementsPage() {
  const [editing, setEditing] = useState<Announcement | "new" | null>(null);
  return (
    <ExtrasPage
      title="Announcements"
      description="News for students, parents, teachers or staff. Save a draft, schedule it, or publish now."
      icon={icon}
      tabs={NOTICE_TABS}
      note={note()}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          New announcement
        </button>
      }
    >
      <AnnouncementsBody editing={editing} setEditing={setEditing} />
    </ExtrasPage>
  );
}

function AnnouncementsBody({ editing, setEditing }: { editing: Announcement | "new" | null; setEditing: (value: Announcement | "new" | null) => void }) {
  const toast = useToast();
  const list = useOptions(useCallback(() => listAnnouncements(), []));
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<NoticeStatus | "">("");
  const [audience, setAudience] = useState<Audience | "">("");
  const [page, setPage] = useState(1);
  const [removing, setRemoving] = useState<Announcement | null>(null);
  const [pending, setPending] = useState(false);
  const needle = q.trim().toLowerCase();
  const rows = list.options.filter(
    (row) =>
      (!status || row.status === status) &&
      (!audience || row.audience.includes(audience) || row.audience.includes("all")) &&
      (!needle || `${row.title} ${row.description}`.toLowerCase().includes(needle)),
  );
  const shown = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const columns: Column<Announcement>[] = [
    { key: "title", label: "Announcement", render: (row) => <div><strong>{row.title}</strong><div className="muted notice-preview">{row.description}</div></div> },
    { key: "audience", label: "For", render: (row) => audienceLabel(row.audience) },
    { key: "date", label: "Publish date", render: (row) => displayValue(row.publish_at ?? row.created_at) },
    { key: "status", label: "Status", render: (row) => <Chip tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Chip> },
  ];
  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search announcements" placeholder="Search" value={q} onChange={(event) => { setQ(event.target.value); setPage(1); }} />
        <select aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value as NoticeStatus | ""); setPage(1); }}>
          <option value="">Any status</option>
          {(Object.keys(STATUS) as NoticeStatus[]).map((key) => <option key={key} value={key}>{STATUS[key].label}</option>)}
        </select>
        <select aria-label="Audience" value={audience} onChange={(event) => { setAudience(event.target.value as Audience | ""); setPage(1); }}>
          <option value="">Any audience</option>
          {AUDIENCES.filter((item) => item.value !== "all").map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </div>
      <div className="teach-stats">
        <Stat label="Published" value={list.options.filter((row) => row.status === "published").length} tone="green" />
        <Stat label="Scheduled" value={list.options.filter((row) => row.status === "scheduled").length} tone="blue" />
        <Stat label="Drafts" value={list.options.filter((row) => row.status === "draft").length} tone="grey" />
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={shown}
          loading={list.loading}
          emptyText={list.error ? "Announcements couldn't be loaded." : q || status || audience ? "Nothing matches these filters." : "No announcements yet."}
          actions={(row) => (
            <>
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>{row.status === "draft" ? "Edit / publish" : "Edit"}</button>
              {canChange(row).remove ? <button className="link-btn danger" type="button" onClick={() => setRemoving(row)}>Delete</button> : null}
            </>
          )}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} />
      </div>
      {editing ? (
        <AnnouncementForm
          row={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(message) => {
            setEditing(null);
            toast("success", message);
            void list.reload();
          }}
        />
      ) : null}
      {removing ? (
        <ConfirmDialog
          title="Delete this announcement?"
          body={removing.title}
          confirmLabel="Delete"
          tone="danger"
          pending={pending}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await deleteAnnouncement(removing.id);
              toast("success", "Announcement deleted.");
              void list.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete."));
            } finally {
              setPending(false);
              setRemoving(null);
            }
          }}
        />
      ) : null}
    </>
  );
}

function AnnouncementForm({ row, onClose, onSaved }: { row: Announcement | null; onClose: () => void; onSaved: (message: string) => void }) {
  const current = useCurrentSessionId();
  const sessions = useOptions(useCallback(() => refOptions("session"), []));
  const [title, setTitle] = useState(row?.title ?? "");
  const [description, setDescription] = useState(row?.description ?? "");
  const [session, setSession] = useState(row?.session_year_id ? String(row.session_year_id) : "");
  const [audience, setAudience] = useState<Audience[]>(row?.audience ?? ["all"]);
  const [publishAt, setPublishAt] = useState((row?.publish_at ?? "").slice(0, 16));
  const submit = useSubmitOnce();
  const errors = useFormErrors();
  const posted = Boolean(row && row.id > 0);
  const sessionId = session || (current ? String(current) : "");

  async function save(draft: boolean) {
    errors.clear();
    await submit.run(async () => {
      try {
        await saveAnnouncement({ title, description, session_year_id: Number(sessionId), audience, publish_at: publishAt ? `${publishAt}:00` : null, draft }, row?.id);
        onSaved(draft ? "Draft saved." : publishAt && new Date(publishAt).getTime() > Date.now() ? "Announcement scheduled." : posted ? "Announcement updated." : "Announcement published.");
      } catch (caught) {
        errors.fromError(caught, "Unable to save the announcement.");
      }
    });
  }

  return (
    <FormModal
      title={row ? (row.status === "draft" ? "Edit draft" : "Edit announcement") : "New announcement"}
      description={posted && !isOperationsLive("notices") ? "The server can't change a posted announcement's text yet; you can change who it's for and its date." : undefined}
      error={errors.formError}
      saving={submit.busy}
      submitLabel={publishAt && new Date(publishAt).getTime() > Date.now() ? "Schedule" : posted ? "Save" : "Publish"}
      wide
      onSubmit={() => void save(false)}
      onClose={onClose}
    >
      <TextField id="an-title" label="Title" required maxLength={255} value={title} onChange={setTitle} error={errors.fieldErrors.title} span />
      <TextAreaField id="an-description" label="Description" required rows={6} value={description} onChange={setDescription} error={errors.fieldErrors.description} span />
      <SelectField id="an-session" label="Academic session" required loading={sessions.loading} value={sessionId} onChange={setSession} options={sessions.options} error={errors.fieldErrors.session_year_id} />
      <TextField id="an-publish" label="Publish on (optional)" type="datetime-local" value={publishAt} onChange={setPublishAt} error={errors.fieldErrors.publish_at} hint="Leave empty to publish now." />
      <AudiencePicker value={audience} onChange={setAudience} error={errors.fieldErrors.audience} />
      {!posted ? (
        <div className="field-span">
          <button className="btn-pill btn-pill-green-soft" type="button" disabled={submit.busy} onClick={() => void save(true)}>
            Save as draft
          </button>
        </div>
      ) : null}
    </FormModal>
  );
}

// ---------- Notifications ----------

export function NotificationsPage() {
  const [composing, setComposing] = useState(false);
  return (
    <ExtrasPage
      title="Notifications"
      description="Push messages to the school's apps, and whether they were delivered."
      icon={icon}
      tabs={NOTICE_TABS}
      note={note()}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setComposing(true)}>
          Send notification
        </button>
      }
    >
      <NotificationsBody composing={composing} setComposing={setComposing} />
    </ExtrasPage>
  );
}

function NotificationsBody({ composing, setComposing }: { composing: boolean; setComposing: (value: boolean) => void }) {
  const toast = useToast();
  const list = useOptions(useCallback(() => listNotifications(), []));
  const [filter, setFilter] = useState({ q: "", from: "", to: "", delivery: "" });
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<NotificationRecord | null>(null);
  const rows = filterNotifications(list.options, filter);
  const shown = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const set = (patch: Partial<typeof filter>) => {
    setFilter((current) => ({ ...current, ...patch }));
    setPage(1);
  };
  const columns: Column<NotificationRecord>[] = [
    { key: "title", label: "Notification", render: (row) => <div><strong>{row.title}</strong><div className="muted notice-preview">{row.body}</div></div> },
    { key: "audience", label: "To", render: (row) => audienceLabel(row.audience) },
    { key: "sent", label: "Sent", render: (row) => displayValue(row.created_at) },
    { key: "delivery", label: "Delivery", render: (row) => <div><Chip tone={DELIVERY[row.delivery].tone}>{DELIVERY[row.delivery].label}</Chip>{row.recipients ? <div className="muted">{row.delivered} of {row.recipients}</div> : null}</div> },
  ];
  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search notifications" placeholder="Search" value={filter.q} onChange={(event) => set({ q: event.target.value })} />
        <label className="ops-filter-label">From <input type="date" value={filter.from} onChange={(event) => set({ from: event.target.value })} /></label>
        <label className="ops-filter-label">To <input type="date" value={filter.to} onChange={(event) => set({ to: event.target.value })} /></label>
        <select aria-label="Delivery" value={filter.delivery} onChange={(event) => set({ delivery: event.target.value })}>
          <option value="">Any delivery status</option>
          {(Object.keys(DELIVERY) as DeliveryStatus[]).map((key) => <option key={key} value={key}>{DELIVERY[key].label}</option>)}
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={shown}
          loading={list.loading}
          emptyText={list.error ? "Notifications couldn't be loaded." : "No notifications match these filters."}
          actions={(row) => <button className="link-btn" type="button" onClick={() => setOpen(row)}>Details</button>}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} />
      </div>
      {composing ? (
        <NotificationForm
          onClose={() => setComposing(false)}
          onSent={() => {
            setComposing(false);
            toast("success", "Notification sent.");
            void list.reload();
          }}
        />
      ) : null}
      {open ? (
        <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && setOpen(null)}>
          <div className="modal-card acad-modal" role="dialog" aria-modal="true" aria-labelledby="nt-title">
            <h2 id="nt-title">{open.title}</h2>
            <p style={{ whiteSpace: "pre-wrap" }}>{open.body}</p>
            <dl className="teach-facts">
              <div><dt>To</dt><dd>{audienceLabel(open.audience)}</dd></div>
              <div><dt>Sent</dt><dd>{displayValue(open.created_at)}</dd></div>
              <div><dt>Delivery</dt><dd><Chip tone={DELIVERY[open.delivery].tone}>{DELIVERY[open.delivery].label}</Chip></dd></div>
              {open.recipients ? <div><dt>Delivered</dt><dd>{open.delivered} of {open.recipients}{open.failed ? `, ${open.failed} failed` : ""}</dd></div> : null}
              {open.failure_reason ? <div><dt>Why some failed</dt><dd>{open.failure_reason}</dd></div> : null}
            </dl>
            <div className="resource-actions acad-modal-actions">
              <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => setOpen(null)}>Close</button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function NotificationForm({ onClose, onSent }: { onClose: () => void; onSent: () => void }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState<Audience[]>(["parents"]);
  const submit = useSubmitOnce();
  const errors = useFormErrors();
  return (
    <FormModal
      title="Send notification"
      description="Goes to the school's apps straight away."
      error={errors.formError}
      saving={submit.busy}
      submitLabel="Send"
      onSubmit={() =>
        void submit.run(async () => {
          errors.clear();
          try {
            await sendNotification({ title, body, audience });
            onSent();
          } catch (caught) {
            errors.fromError(caught, "Unable to send the notification.");
          }
        })
      }
      onClose={onClose}
    >
      <TextField id="nt-title-input" label="Title" required maxLength={255} value={title} onChange={setTitle} error={errors.fieldErrors.title} span />
      <TextAreaField id="nt-body" label="Message" required rows={4} value={body} onChange={setBody} error={errors.fieldErrors.body} span />
      <AudiencePicker value={audience} onChange={setAudience} error={errors.fieldErrors.audience} />
    </FormModal>
  );
}
