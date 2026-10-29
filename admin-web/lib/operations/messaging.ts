/**
 * Teacher–parent conversations, as seen by a school admin.
 * Live (contract, see backend/docs/OPERATIONS_MODULES_API_CONTRACT.md):
 *   GET   /school-admin/messaging/policy                 what this admin may see and do
 *   GET   /school-admin/conversations?q=&unread=&flagged=
 *   GET   /school-admin/conversations/{id}/messages
 *   POST  /school-admin/conversations/{id}/messages      {body}
 *   POST  /school-admin/conversations/{id}/read
 *   PATCH /school-admin/conversations/{id}               {flagged}
 *   PATCH /school-admin/messages/{id}                    {hidden}   (moderators only)
 * The server decides which conversations an admin may open (school policy) and only returns
 * those; this client never filters private threads itself.
 * Sample: conversations between the school's real teachers and the parents of real students,
 * kept in this browser.
 */
import { staffDirectory } from "@/lib/extras/api";
import { isOperationsLive } from "@/lib/operations/mode";
import type { Attachment, Conversation, ConversationQuery, Message, MessagingPolicy, Participant } from "@/lib/operations/types";
import { peopleService } from "@/lib/people";
import { invalid, later, missing } from "@/lib/ops/store";
import { get, num, optStr, send, str, type Raw } from "@/lib/teaching/client";

export interface MessagingService {
  policy(): Promise<MessagingPolicy>;
  conversations(query?: ConversationQuery): Promise<Conversation[]>;
  messages(conversationId: number): Promise<Message[]>;
  send(conversationId: number, body: string): Promise<Message>;
  markRead(conversationId: number): Promise<void>;
  flag(conversationId: number, flagged: boolean): Promise<void>;
  hide(messageId: number, hidden: boolean): Promise<void>;
}

export const MAX_MESSAGE = 2000;

export function messageProblem(body: string): string {
  const text = body.trim();
  if (!text) return "Write a message.";
  if (text.length > MAX_MESSAGE) return `Keep messages under ${MAX_MESSAGE} characters.`;
  return "";
}

/** Conversations matching a search (student, teacher, parent or subject) and the toggles. */
export function filterConversations(rows: Conversation[], query: ConversationQuery = {}): Conversation[] {
  const needle = (query.q ?? "").trim().toLowerCase();
  return rows
    .filter((row) => !query.unreadOnly || row.unread > 0)
    .filter((row) => !query.flaggedOnly || row.flagged)
    .filter((row) => !needle || [row.subject, row.student_name, row.teacher.name, row.parent.name, row.class_name].some((value) => value.toLowerCase().includes(needle)))
    .sort((a, b) => b.last_message_at.localeCompare(a.last_message_at));
}

// ---------- live ----------

function participantOf(row: unknown): Participant {
  const value = (row && typeof row === "object" ? row : {}) as Raw;
  const role = str(value.role);
  return { user_id: num(value.user_id), name: str(value.name), role: role === "teacher" || role === "parent" ? role : "school_admin" };
}

function attachmentsOf(value: unknown): Attachment[] {
  return Array.isArray(value) ? (value as Raw[]).map((row) => ({ name: str(row.name), url: str(row.url), size: row.size === undefined || row.size === null ? null : num(row.size), content_type: optStr(row.content_type) })) : [];
}

function conversationOf(row: Raw): Conversation {
  return {
    id: num(row.id),
    subject: str(row.subject),
    student_id: num(row.student_id),
    student_name: str(row.student_name),
    class_name: str(row.class_name),
    teacher: participantOf(row.teacher),
    parent: participantOf(row.parent),
    last_message: str(row.last_message),
    last_message_at: str(row.last_message_at),
    unread: num(row.unread),
    flagged: row.flagged === true || num(row.flagged) === 1,
  };
}

function messageOf(row: Raw): Message {
  return {
    id: num(row.id),
    conversation_id: num(row.conversation_id),
    sender: participantOf(row.sender),
    body: str(row.body),
    attachments: attachmentsOf(row.attachments),
    sent_at: str(row.sent_at),
    hidden: row.hidden === true || num(row.hidden) === 1,
  };
}

const M = "/school-admin";

export const liveMessaging: MessagingService = {
  async policy() {
    const data = await get(`${M}/messaging/policy`, {}, "Unable to load messaging permissions.");
    return { can_view: data.can_view === true, can_send: data.can_send === true, can_moderate: data.can_moderate === true, poll_seconds: Math.max(5, num(data.poll_seconds ?? 15)) };
  },
  async conversations(query = {}) {
    const data = await get(`${M}/conversations`, { q: query.q?.trim(), unread: query.unreadOnly ? 1 : undefined, flagged: query.flaggedOnly ? 1 : undefined, page_size: 50 }, "Unable to load conversations.");
    return (Array.isArray(data.items) ? (data.items as Raw[]) : []).map(conversationOf);
  },
  async messages(conversationId) {
    const data = await get(`${M}/conversations/${conversationId}/messages`, { page_size: 50 }, "Unable to load messages.");
    return (Array.isArray(data.items) ? (data.items as Raw[]) : []).map(messageOf).sort((a, b) => a.sent_at.localeCompare(b.sent_at));
  },
  async send(conversationId, body) {
    const problem = messageProblem(body);
    if (problem) invalid({ body: problem });
    return messageOf(await send("POST", `${M}/conversations/${conversationId}/messages`, { body: body.trim() }, "Unable to send the message."));
  },
  async markRead(conversationId) {
    await send("POST", `${M}/conversations/${conversationId}/read`, {}, "Unable to mark as read.");
  },
  async flag(conversationId, flagged) {
    await send("PATCH", `${M}/conversations/${conversationId}`, { flagged }, "Unable to flag the conversation.");
  },
  async hide(messageId, hidden) {
    await send("PATCH", `${M}/messages/${messageId}`, { hidden }, "Unable to change the message.");
  },
};

// ---------- sample ----------

const KEY = "operations-messages-v1";

type Store = { conversations: Conversation[]; messages: Message[] };

let memory: Store | null = null;

function save() {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    // Storage blocked: changes last until reload.
  }
}

const OPENERS = [
  { subject: "Homework this week", teacher: "Please make sure the maths worksheet is finished by Friday.", parent: "Thank you, we'll check it together tonight." },
  { subject: "Absent on Monday", parent: "My child was unwell on Monday and will bring a note tomorrow.", teacher: "Thanks for letting me know. I'll share the class notes." },
  { subject: "Science project", teacher: "The science project is due next Wednesday. Groups are on the class board.", parent: "Could you tell us which group she's in?" },
  { subject: "Parent-teacher meeting", parent: "Can we meet after school on Thursday?", teacher: "Thursday at 3:30 works. See you in room 12." },
  { subject: "Reading progress", teacher: "Reading has improved a lot this term. Keep up the bedtime reading!", parent: "That's great to hear, thank you." },
];

async function build(): Promise<Store> {
  const [students, people] = await Promise.all([
    peopleService("students").listStudents({ pageSize: 8, status: "1", sort: "name" }).then((page) => page.items).catch(() => []),
    staffDirectory().catch(() => []),
  ]);
  const teachers = people.filter((row) => row.kind === "teacher");
  const conversations: Conversation[] = [];
  const messages: Message[] = [];
  const now = Date.now();
  students.slice(0, OPENERS.length).forEach((student, index) => {
    const opener = OPENERS[index];
    const teacher: Participant = { user_id: teachers[index % Math.max(teachers.length, 1)]?.user_id ?? 900 + index, name: teachers[index % Math.max(teachers.length, 1)]?.name ?? "Class teacher", role: "teacher" };
    const parent: Participant = { user_id: 800 + student.id, name: student.guardian_name || `Parent of ${student.name}`, role: "parent" };
    const id = index + 1;
    const first = new Date(now - (index * 26 + 5) * 3_600_000).toISOString();
    const second = new Date(now - (index * 26 + 2) * 3_600_000).toISOString();
    const [a, b] = opener.teacher && OPENERS[index].subject !== "Absent on Monday" && OPENERS[index].subject !== "Parent-teacher meeting" ? [teacher, parent] : [parent, teacher];
    const [textA, textB] = a.role === "teacher" ? [opener.teacher, opener.parent] : [opener.parent, opener.teacher];
    messages.push({ id: id * 100 + 1, conversation_id: id, sender: a, body: textA, attachments: index === 2 ? [{ name: "project-groups.pdf", url: "#", size: 48_200, content_type: "application/pdf" }] : [], sent_at: first, hidden: false });
    messages.push({ id: id * 100 + 2, conversation_id: id, sender: b, body: textB, attachments: [], sent_at: second, hidden: false });
    conversations.push({ id, subject: opener.subject, student_id: student.id, student_name: student.name, class_name: `${student.class_name} ${student.section_name}`.trim(), teacher, parent, last_message: textB, last_message_at: second, unread: index < 2 ? 1 : 0, flagged: false });
  });
  return { conversations, messages };
}

async function store(): Promise<Store> {
  if (memory) return memory;
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved) memory = JSON.parse(saved) as Store;
  } catch {
    memory = null;
  }
  if (!memory) {
    memory = await build();
    save();
  }
  return memory;
}

export function resetMessagingMock(): void {
  memory = null;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}

const ADMIN: Participant = { user_id: 0, name: "School admin", role: "school_admin" };

export const mockMessaging: MessagingService = {
  async policy() {
    return later({ can_view: true, can_send: true, can_moderate: true, poll_seconds: 15 });
  },
  async conversations(query = {}) {
    return later(filterConversations((await store()).conversations, query));
  },
  async messages(conversationId) {
    const db = await store();
    if (!db.conversations.some((row) => row.id === conversationId)) missing("Conversation");
    return later(db.messages.filter((row) => row.conversation_id === conversationId).sort((a, b) => a.sent_at.localeCompare(b.sent_at)));
  },
  async send(conversationId, body) {
    const problem = messageProblem(body);
    if (problem) invalid({ body: problem });
    const db = await store();
    const conversation = db.conversations.find((row) => row.id === conversationId) ?? missing("Conversation");
    const message: Message = { id: Math.max(0, ...db.messages.map((row) => row.id)) + 1, conversation_id: conversationId, sender: ADMIN, body: body.trim(), attachments: [], sent_at: new Date().toISOString(), hidden: false };
    db.messages.push(message);
    conversation.last_message = message.body;
    conversation.last_message_at = message.sent_at;
    save();
    return later(message);
  },
  async markRead(conversationId) {
    const db = await store();
    const conversation = db.conversations.find((row) => row.id === conversationId);
    if (conversation) conversation.unread = 0;
    save();
    await later(null);
  },
  async flag(conversationId, flagged) {
    const db = await store();
    const conversation = db.conversations.find((row) => row.id === conversationId) ?? missing("Conversation");
    conversation.flagged = flagged;
    save();
    await later(null);
  },
  async hide(messageId, hidden) {
    const db = await store();
    const message = db.messages.find((row) => row.id === messageId) ?? missing("Message");
    message.hidden = hidden;
    save();
    await later(null);
  },
};

export function messagingService(): MessagingService {
  return isOperationsLive("messaging") ? liveMessaging : mockMessaging;
}
