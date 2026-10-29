"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { Chip } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { MAX_MESSAGE, messageProblem, messagingService } from "@/lib/operations/messaging";
import { isOperationsLive, OPERATIONS_SAMPLE_NOTE } from "@/lib/operations/mode";
import type { Conversation, Message, MessagingPolicy } from "@/lib/operations/types";
import { useSubmitOnce } from "@/lib/ops/submit";
import { IconBell } from "@/lib/icons";

function when(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const today = new Date();
  return date.toDateString() === today.toDateString()
    ? date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) + ", " + date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function size(bytes: number | null): string {
  if (bytes === null) return "";
  return bytes > 1_048_576 ? `${(bytes / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function MessagesPage() {
  return (
    <ExtrasPage
      title="Teacher–parent messages"
      description="Conversations between teachers and parents that the school's policy lets admins see."
      icon={<IconBell width={18} height={18} />}
      note={isOperationsLive("messaging") ? undefined : OPERATIONS_SAMPLE_NOTE.messaging}
    >
      <MessagesBody />
    </ExtrasPage>
  );
}

function MessagesBody() {
  const policy = useOptions(useCallback(() => messagingService().policy().then((row) => [row]), []));
  const rules = policy.options[0];
  if (policy.error) return <ErrorAlert error={policy.error} onRetry={() => void policy.reload()} />;
  if (!rules) return <div className="resource-card"><div className="skeleton" style={{ height: 240 }} /></div>;
  if (!rules.can_view) {
    return (
      <div className="resource-card">
        <div className="empty-state">Your school's policy doesn't let admins read teacher–parent messages. Teachers and parents can still message each other in the apps.</div>
      </div>
    );
  }
  return <Inbox policy={rules} />;
}

function Inbox({ policy }: { policy: MessagingPolicy }) {
  const [q, setQ] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const list = useOptions(useCallback(() => messagingService().conversations({ q, unreadOnly, flaggedOnly }), [q, unreadOnly, flaggedOnly]));
  const { reload } = list;

  // No push from the server yet: check for new messages every few seconds while the tab is visible.
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void reload();
    }, policy.poll_seconds * 1000);
    return () => window.clearInterval(timer);
  }, [reload, policy.poll_seconds]);

  const open = list.options.find((row) => row.id === openId) ?? null;
  const unread = list.options.reduce((sum, row) => sum + row.unread, 0);

  return (
    <div className={`msg-layout${open ? " has-open" : ""}`}>
      <section className="resource-card msg-list" aria-label="Conversations">
        <div className="msg-list-head">
          <input type="search" aria-label="Search conversations" placeholder="Student, teacher, parent or subject" value={q} onChange={(event) => setQ(event.target.value)} />
          <div className="msg-toggles">
            <label className="acad-check"><input type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} /><span>Unread{unread ? ` (${unread})` : ""}</span></label>
            {policy.can_moderate ? <label className="acad-check"><input type="checkbox" checked={flaggedOnly} onChange={(event) => setFlaggedOnly(event.target.checked)} /><span>Flagged</span></label> : null}
          </div>
        </div>
        <ErrorAlert error={list.error} onRetry={() => void reload()} />
        {list.loading && !list.options.length ? <div className="skeleton" style={{ height: 200, margin: 12 }} /> : null}
        {!list.loading && !list.options.length ? <div className="empty-state">{q || unreadOnly || flaggedOnly ? "No conversation matches." : "No conversations yet."}</div> : null}
        <ul>
          {list.options.map((row) => (
            <li key={row.id}>
              <button type="button" className={`msg-row${row.id === openId ? " is-selected" : ""}${row.unread ? " is-unread" : ""}`} onClick={() => setOpenId(row.id)} aria-current={row.id === openId}>
                <span className="msg-row-head">
                  <strong>{row.subject}</strong>
                  <span className="muted">{when(row.last_message_at)}</span>
                </span>
                <span className="muted">{row.student_name} · {row.class_name}</span>
                <span className="msg-row-meta">
                  <span className="msg-snippet">{row.last_message}</span>
                  {row.flagged ? <Chip tone="red">Flagged</Chip> : null}
                  {row.unread ? <span className="msg-unread" aria-label={`${row.unread} unread`}>{row.unread}</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {open ? (
        <Thread key={open.id} conversation={open} policy={policy} onBack={() => setOpenId(null)} onChanged={() => void reload()} />
      ) : (
        <section className="resource-card msg-thread msg-empty" aria-label="Conversation">
          <div className="empty-state">Choose a conversation to read it.</div>
        </section>
      )}
    </div>
  );
}

function Thread({ conversation, policy, onBack, onChanged }: { conversation: Conversation; policy: MessagingPolicy; onBack: () => void; onChanged: () => void }) {
  const toast = useToast();
  const messages = useOptions(useCallback(() => messagingService().messages(conversation.id), [conversation.id]));
  const [draft, setDraft] = useState("");
  const [problem, setProblem] = useState("");
  const submit = useSubmitOnce();
  const end = useRef<HTMLDivElement>(null);
  const { reload } = messages;

  useEffect(() => {
    if (conversation.unread) void messagingService().markRead(conversation.id).then(onChanged).catch(() => undefined);
    // Mark read once when the conversation opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation.id]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void reload();
    }, policy.poll_seconds * 1000);
    return () => window.clearInterval(timer);
  }, [reload, policy.poll_seconds]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.options.length]);

  async function sendMessage() {
    const found = messageProblem(draft);
    setProblem(found);
    if (found) return;
    await submit.run(async () => {
      try {
        await messagingService().send(conversation.id, draft);
        setDraft("");
        void reload();
        onChanged();
      } catch (caught) {
        setProblem(errorMessage(caught, "Unable to send the message."));
      }
    });
  }

  async function moderate(action: () => Promise<void>, done: string) {
    try {
      await action();
      toast("success", done);
      void reload();
      onChanged();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the conversation."));
    }
  }

  return (
    <section className="resource-card msg-thread" aria-label={`Conversation: ${conversation.subject}`}>
      <header className="msg-thread-head">
        <button className="link-btn msg-back" type="button" onClick={onBack}>← All conversations</button>
        <div>
          <h2>{conversation.subject}</h2>
          <p className="muted">
            About {conversation.student_name} ({conversation.class_name}) · {conversation.teacher.name} (teacher) and {conversation.parent.name} (parent)
          </p>
        </div>
        {policy.can_moderate ? (
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => void moderate(() => messagingService().flag(conversation.id, !conversation.flagged), conversation.flagged ? "Flag removed." : "Conversation flagged for review.")}>
            {conversation.flagged ? "Remove flag" : "Flag for review"}
          </button>
        ) : null}
      </header>
      <ErrorAlert error={messages.error} onRetry={() => void reload()} />
      <ol className="ticket-thread msg-messages">
        {messages.loading && !messages.options.length ? <li className="skeleton" style={{ height: 60 }} /> : null}
        {messages.options.map((message: Message) => (
          <li key={message.id} className={`${message.sender.role === "teacher" ? "is-mine" : ""}${message.hidden ? " is-hidden" : ""}`}>
            {message.hidden ? <p className="muted"><em>Hidden by a moderator.</em>{policy.can_moderate ? ` ${message.body}` : ""}</p> : <p>{message.body}</p>}
            {!message.hidden && message.attachments.length ? (
              <p className="msg-attachments">
                {message.attachments.map((file) => (
                  <a key={file.name} href={file.url} target="_blank" rel="noopener noreferrer" className="msg-attachment">📎 {file.name}{file.size ? ` (${size(file.size)})` : ""}</a>
                ))}
              </p>
            ) : null}
            <small className="muted">
              {message.sender.name} · {message.sender.role === "school_admin" ? "School admin" : message.sender.role === "teacher" ? "Teacher" : "Parent"} · {when(message.sent_at)}
              {policy.can_moderate ? (
                <>
                  {" · "}
                  <button className="link-btn" type="button" onClick={() => void moderate(() => messagingService().hide(message.id, !message.hidden), message.hidden ? "Message shown again." : "Message hidden.")}>
                    {message.hidden ? "Unhide" : "Hide"}
                  </button>
                </>
              ) : null}
            </small>
          </li>
        ))}
        <div ref={end} />
      </ol>
      {policy.can_send ? (
        <form
          className="msg-compose"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage();
          }}
        >
          <label className="acad-sr" htmlFor="msg-draft">Message</label>
          <textarea id="msg-draft" rows={2} maxLength={MAX_MESSAGE} placeholder="Write to the teacher and parent as the school…" value={draft} onChange={(event) => setDraft(event.target.value)} aria-invalid={Boolean(problem)} />
          <button className="btn-pill btn-pill-green" type="submit" disabled={submit.busy}>{submit.busy ? "Sending…" : "Send"}</button>
          {problem ? <p className="field-error">{problem}</p> : null}
        </form>
      ) : (
        <p className="muted msg-readonly">You can read this conversation but not reply to it.</p>
      )}
    </section>
  );
}
