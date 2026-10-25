"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { dayLabel } from "@/components/teaching/offline";
import { useCurrentSessionId } from "@/components/teaching/Pickers";
import { gradingService } from "@/lib/ops/grading";
import { IconExam } from "@/lib/icons";

export default function ReportCardPage() {
  const params = useParams<{ studentId: string }>();
  const id = Number(params.studentId);
  return (
    <TeachingPage
      module="grading"
      title="Report card"
      icon={<IconExam width={18} height={18} />}
      liveNote={OPS_LIVE_NOTE.grading}
      back={{ href: "/school/report-cards", label: "Report cards" }}
    >
      {Number.isInteger(id) && id > 0 ? (
        <Suspense fallback={<div className="skeleton" style={{ height: 300 }} />}>
          <CardBody studentId={id} />
        </Suspense>
      ) : (
        <div className="alert alert-danger">This report card link isn't valid.</div>
      )}
    </TeachingPage>
  );
}

function CardBody({ studentId }: { studentId: number }) {
  const search = useSearchParams();
  const current = useCurrentSessionId();
  const sessionId = Number(search.get("session")) || Number(current) || 0;
  const scales = useOptions(useCallback(() => gradingService().scales(), []));
  const [scaleId, setScaleId] = useState<number | "">("");
  const loader = useCallback(() => gradingService().reportCard(studentId, sessionId, scaleId || undefined).then((card) => [card]), [studentId, sessionId, scaleId]);
  const state = useOptions(sessionId ? loader : null);
  const card = state.options[0] ?? null;

  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!card) return <div className="resource-card"><div className="skeleton" style={{ height: 320 }} /></div>;

  return (
    <>
      <div className="school-filters ops-no-print">
        <select aria-label="Grading scale" value={scaleId} onChange={(event) => setScaleId(event.target.value ? Number(event.target.value) : "")}>
          <option value="">Default grading scale</option>
          {scales.options.filter((scale) => scale.status === 1).map((scale) => (
            <option key={scale.id} value={scale.id}>
              {scale.name}
            </option>
          ))}
        </select>
        <button className="btn-pill btn-pill-green" type="button" onClick={() => window.print()} disabled={!card.exams.length}>
          Print or save as PDF
        </button>
      </div>
      <article className="resource-card ops-report" aria-labelledby="rc-title">
        <header className="ops-report-head">
          <div>
            <h2 id="rc-title">{card.student_name}</h2>
            <p className="muted">
              {card.class_name} {card.section_name} · {card.session_name || "Session"}
            </p>
          </div>
          <div className="ops-report-overall">
            {card.overall.grade ? <span className="ops-report-grade">{card.overall.grade}</span> : null}
            <span>{card.exams.length ? `${card.overall.percentage}%` : "No results"}</span>
          </div>
        </header>
        <dl className="teach-facts">
          <div><dt>Admission no.</dt><dd>{card.admission_no}</dd></div>
          <div><dt>Roll number</dt><dd>{card.roll_number ?? "—"}</dd></div>
          <div><dt>Parent / guardian</dt><dd>{card.guardian_name ?? "—"}</dd></div>
          <div><dt>Result</dt><dd>{card.overall.passed === null ? "—" : card.overall.passed ? <Chip tone="green">Pass</Chip> : <Chip tone="red">Fail</Chip>}</dd></div>
          <div><dt>Promotion</dt><dd>{card.promotion ?? "Decided once every exam is processed"}</dd></div>
          <div><dt>Grading</dt><dd>{card.scale_name ?? "No grading scale"}</dd></div>
        </dl>
        {card.exams.length === 0 ? (
          <div className="empty-state">No processed exam results for this student in this session yet.</div>
        ) : (
          card.exams.map((exam) => (
            <section key={exam.exam_id} className="ops-report-exam" aria-label={exam.exam_name}>
              <h3>
                {exam.exam_name} <span className="muted">{exam.exam_date ? dayLabel(exam.exam_date) : ""}</span> {exam.published ? null : <Chip tone="amber">Not published</Chip>}
              </h3>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Subject</th>
                      <th scope="col">Marks</th>
                      <th scope="col">Grade</th>
                      <th scope="col">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exam.subjects.map((subject) => (
                      <tr key={subject.subject_name}>
                        <td>{subject.subject_name}</td>
                        <td>{subject.status === "present" ? `${subject.marks_obtained} / ${subject.max_marks}` : subject.status === "absent" ? `Absent (0 / ${subject.max_marks})` : "Withheld"}</td>
                        <td>{subject.grade ?? "—"}</td>
                        <td>{subject.passed === null ? "—" : subject.passed ? "Pass" : "Fail"}</td>
                      </tr>
                    ))}
                    <tr className="ops-report-total">
                      <th scope="row">Total</th>
                      <td>
                        {exam.total_obtained} / {exam.total_max} ({exam.percentage}%)
                      </td>
                      <td>{exam.grade ?? "—"}</td>
                      <td>{exam.passed ? "Pass" : "Fail"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          ))
        )}
        <p className="muted ops-report-foot">Generated {new Date().toLocaleDateString()} · Marks come from processed offline exam results.</p>
      </article>
    </>
  );
}
