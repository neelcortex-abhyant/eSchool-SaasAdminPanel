"use client";

import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { useDebounced, useOptions } from "@/components/academics/hooks";
import { SelectField } from "@/components/academics/Fields";
import { useToast } from "@/components/academics/Toasts";
import { TeachingPage } from "@/components/teaching/Frame";
import { EXAM_TABS, QuestionCard, QuestionForm } from "@/components/teaching/exams";
import { useSubjects } from "@/components/teaching/Pickers";
import { bankQuestions, removeBankQuestion, saveBankQuestion } from "@/lib/teaching/exams";
import type { BankQuestion } from "@/lib/teaching/types";
import { IconExam } from "@/lib/icons";

const BANK_NOTE = "The question bank is kept in this browser until the server has a question bank. Use “Add from question bank” on an exam to copy questions into it; copied questions are saved with the exam.";

export default function QuestionBankPage() {
  const [editing, setEditing] = useState<BankQuestion | "new" | null>(null);
  return (
    <TeachingPage
      module="exams"
      title="Question bank"
      description="Keep reusable multiple-choice questions by subject and topic, then copy them into any exam."
      icon={<IconExam width={18} height={18} />}
      tabs={EXAM_TABS}
      liveNote={BANK_NOTE}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add question
        </button>
      }
    >
      <BankBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function BankBody({ editing, setEditing }: { editing: BankQuestion | "new" | null; setEditing: (value: BankQuestion | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [subject, setSubject] = useState("");
  const [formSubject, setFormSubject] = useState("");
  const [deleting, setDeleting] = useState<BankQuestion | null>(null);
  const subjects = useSubjects("");
  const subjectNames = [...new Set(subjects.options.map((row) => row.name))].sort();
  const list = useOptions(useCallback(() => Promise.resolve(bankQuestions(search, subject)), [search, subject]));

  function openForm(value: BankQuestion | "new") {
    setFormSubject(value === "new" ? subject : value.subject_name ?? "");
    setEditing(value);
  }

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search questions" placeholder="Search question or topic" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
        <select aria-label="Filter by subject" value={subject} onChange={(event) => setSubject(event.target.value)}>
          <option value="">All subjects</option>
          {subjectNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <section className="resource-card">
        {list.options.length === 0 ? (
          <div className="empty-state">{search || subject ? "No questions match these filters." : "The question bank is empty. Use Add question to start it."}</div>
        ) : (
          <ol className="teach-questions">
            {list.options.map((question, index) => (
              <QuestionCard
                key={question.id}
                index={index}
                question={question}
                actions={
                  <>
                    {question.subject_name ? <span className="muted">{question.subject_name}</span> : null}
                    <button className="link-btn" type="button" onClick={() => openForm(question)}>
                      Edit
                    </button>
                    <button className="link-btn danger" type="button" onClick={() => setDeleting(question)}>
                      Delete
                    </button>
                  </>
                }
              />
            ))}
          </ol>
        )}
      </section>
      {editing ? (
        <QuestionForm
          title={editing === "new" ? "Add question to the bank" : "Edit bank question"}
          question={editing === "new" ? null : editing}
          nextOrder={0}
          extra={
            <SelectField
              id="bank-subject"
              label="Subject"
              placeholder="No subject"
              value={formSubject}
              onChange={setFormSubject}
              options={subjectNames.map((name) => ({ value: name, label: name }))}
            />
          }
          onClose={() => setEditing(null)}
          onSubmit={async (input) => {
            saveBankQuestion({ ...input, subject_name: formSubject || null }, editing === "new" ? undefined : editing.id);
            setEditing(null);
            toast("success", editing === "new" ? "Question added to the bank." : "Question updated.");
            void list.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          title="Delete this question from the bank?"
          body={`${deleting.question_text} — exams that already use a copy keep it.`}
          confirmLabel="Delete question"
          tone="danger"
          pending={false}
          onCancel={() => setDeleting(null)}
          onConfirm={() => {
            removeBankQuestion(deleting.id);
            setDeleting(null);
            toast("success", "Question removed from the bank.");
            void list.reload();
          }}
        />
      ) : null}
    </>
  );
}
