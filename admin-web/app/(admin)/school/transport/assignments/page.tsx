"use client";

import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, StatusToggle, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useDebounced, useFormErrors, useOptions, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { StudentPicker } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { isOpsLive } from "@/lib/ops/mode";
import { TRANSPORT_TABS } from "@/components/ops/transport";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import type { StudentRow } from "@/lib/people";
import { today } from "@/lib/ops/store";
import { transportService } from "@/lib/ops/transport";
import { capacityProblem, seatsLeft } from "@/lib/ops/transport-rules";
import type { Route, TransportAssignment, TransportDirection } from "@/lib/ops/types";
import { IconPackage } from "@/lib/icons";

const PAGE_SIZE = 20;
const DIRECTION_LABEL: Record<TransportDirection, string> = { both: "Pickup and drop", pickup: "Morning pickup only", drop: "Afternoon drop only" };

export default function TransportAssignmentsPage() {
  const [editing, setEditing] = useState<TransportAssignment | "new" | null>(null);
  return (
    <TeachingPage
      module="transport"
      title="Student transport"
      description="Which students ride which route, and where they board."
      icon={<IconPackage width={18} height={18} />}
      tabs={TRANSPORT_TABS}
      liveNote={OPS_LIVE_NOTE.transport}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Assign transport
        </button>
      }
    >
      <AssignmentsBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function AssignmentsBody({ editing, setEditing }: { editing: TransportAssignment | "new" | null; setEditing: (value: TransportAssignment | "new" | null) => void }) {
  const toast = useToast();
  const routes = useOptions(useCallback(() => transportService().routes(), []));
  const [routeId, setRouteId] = useState<number | "">("");
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [page, setPage] = useState(1);
  const [removing, setRemoving] = useState<TransportAssignment | null>(null);
  const [pending, setPending] = useState(false);
  const loader = useCallback(() => transportService().assignments({ page, pageSize: PAGE_SIZE, q: search, routeId }), [page, search, routeId]);
  const list = usePagedList(loader);

  const columns: Column<TransportAssignment>[] = [
    { key: "student", label: "Student", render: (row) => <div><strong>{row.student_name}</strong><div className="muted">{row.admission_no} · {row.class_name} {row.section_name}</div></div> },
    { key: "route", label: "Route", render: (row) => row.route_name },
    { key: "stop", label: "Stop", render: (row) => row.stop_name },
    ...(isOpsLive("transport")
      ? [{ key: "from", label: "Added", render: (row: TransportAssignment) => row.start_date }]
      : [
          { key: "direction", label: "Uses", render: (row: TransportAssignment) => DIRECTION_LABEL[row.direction] },
          { key: "from", label: "From", render: (row: TransportAssignment) => row.start_date },
        ]),
    { key: "status", label: "Status", render: (row) => (row.status === 1 ? <Chip tone="green">Active</Chip> : <Chip tone="grey">Paused</Chip>) },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search students" placeholder="Student name or admission no." value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <select aria-label="Filter by route" value={routeId} onChange={(event) => { setRouteId(event.target.value ? Number(event.target.value) : ""); setPage(1); }}>
          <option value="">All routes</option>
          {routes.options.map((route) => (
            <option key={route.id} value={route.id}>
              {route.name}
            </option>
          ))}
        </select>
      </div>
      {routes.options.length ? (
        <div className="teach-summary">
          {routes.options.filter((route) => route.status === 1).map((route) => {
            const left = seatsLeft(route.capacity, route.assigned_students);
            return (
              <Chip key={route.id} tone={left === null ? "grey" : left <= 0 ? "red" : left <= 3 ? "amber" : "green"}>
                {route.name}: {left === null ? `${route.assigned_students} students, no vehicle` : `${left} seats left`}
              </Chip>
            );
          })}
        </div>
      ) : null}
      <ErrorAlert error={list.error ?? routes.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.data?.items ?? []}
          loading={list.loading}
          emptyText={list.error ? "Transport assignments couldn't be loaded." : search || routeId ? "No students match these filters." : "No students use school transport yet."}
          actions={(row) => (
            <>
              {isOpsLive("transport") ? null : (
                <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                  Change
                </button>
              )}
              <button className="link-btn danger" type="button" onClick={() => setRemoving(row)}>
                Remove
              </button>
            </>
          )}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {editing ? (
        <AssignmentForm
          routes={routes.options}
          assignment={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? "Transport assigned." : "Transport updated.");
            void list.reload();
            void routes.reload();
          }}
        />
      ) : null}
      {removing ? (
        <ConfirmDialog
          title="Remove this student's transport?"
          body={`${removing.student_name} will no longer ride ${removing.route_name}.`}
          confirmLabel="Remove"
          tone="danger"
          pending={pending}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await transportService().removeAssignment(removing.id);
              toast("success", "Transport removed.");
              void list.reload();
              void routes.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to remove the transport."));
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

function AssignmentForm({ routes, assignment, onClose, onSaved }: { routes: Route[]; assignment: TransportAssignment | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const [student, setStudent] = useState<StudentRow | null>(assignment ? ({ id: assignment.student_id, name: assignment.student_name, admission_no: assignment.admission_no, class_name: assignment.class_name, section_name: assignment.section_name } as StudentRow) : null);
  const [routeId, setRouteId] = useState(assignment ? String(assignment.route_id) : "");
  const [stopId, setStopId] = useState(assignment ? String(assignment.stop_id) : "");
  const [direction, setDirection] = useState<TransportDirection>(assignment?.direction ?? "both");
  const [startDate, setStartDate] = useState(assignment?.start_date ?? today());
  const [active, setActive] = useState(assignment ? assignment.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const route = routes.find((row) => String(row.id) === routeId);
  // Moving within the same route doesn't take another seat.
  const sameRoute = assignment && route && assignment.route_id === route.id && assignment.status === 1;
  const warning = route && active && !sameRoute ? capacityProblem(route.capacity, route.assigned_students) : "";
  const activeRoutes = useMemo(() => routes.filter((row) => row.status === 1 || String(row.id) === routeId), [routes, routeId]);

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!student) invalid.student_id = "Choose a student.";
    if (!routeId) invalid.route_id = "Choose a route.";
    if (!stopId) invalid.stop_id = "Choose a stop.";
    if (warning) invalid.route_id = warning;
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await transportService().saveAssignment({ student_id: (student as StudentRow).id, route_id: Number(routeId), stop_id: Number(stopId), direction, start_date: startDate, status: active ? 1 : 0 }, assignment?.id);
      onSaved(!assignment);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the transport assignment.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={assignment ? "Change transport" : "Assign transport"} error={errors.formError} saving={saving} submitLabel="Save" wide onSubmit={() => void submit()} onClose={onClose}>
      {assignment ? (
        <div className="form-field">
          <span className="field-label">Student</span>
          <strong>{assignment.student_name}</strong>
        </div>
      ) : (
        <StudentPicker id="ta-student" value={student} onPick={setStudent} error={errors.fieldErrors.student_id} />
      )}
      <SelectField
        id="ta-route"
        label="Route"
        required
        placeholder="Choose a route"
        value={routeId}
        onChange={(value) => {
          setRouteId(value);
          setStopId("");
        }}
        options={activeRoutes.map((row) => {
          const left = seatsLeft(row.capacity, row.assigned_students);
          return { value: String(row.id), label: `${row.name}${left === null ? "" : ` · ${left} seats left`}` };
        })}
        error={errors.fieldErrors.route_id}
        hint={route && !route.vehicle_id ? "This route has no vehicle yet." : undefined}
      />
      <SelectField
        id="ta-stop"
        label="Stop"
        required
        placeholder={route ? (route.stops.length ? "Choose a stop" : "This route has no stops yet") : "Choose a route first"}
        disabled={!route || route.stops.length === 0}
        value={stopId}
        onChange={setStopId}
        options={(route?.stops ?? []).map((stop) => ({ value: String(stop.id), label: `${stop.stop_order}. ${stop.name}${stop.pickup_time ? ` · pickup ${stop.pickup_time}` : ""}${stop.drop_time ? ` · drop ${stop.drop_time}` : ""}` }))}
        error={errors.fieldErrors.stop_id}
      />
      {isOpsLive("transport") ? null : (
        <>
          <SelectField id="ta-direction" label="Uses" required value={direction} onChange={(value) => setDirection(value as TransportDirection)} options={(Object.keys(DIRECTION_LABEL) as TransportDirection[]).map((value) => ({ value, label: DIRECTION_LABEL[value] }))} />
          <TextField id="ta-start" label="From" type="date" required value={startDate} onChange={setStartDate} error={errors.fieldErrors.start_date} />
        </>
      )}
      {isOpsLive("transport") ? null : <StatusToggle id="ta-active" checked={active} onChange={setActive} label="Active (takes a seat)" />}
    </FormModal>
  );
}
