"use client";

import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { Chip, Stat, TeachingPage } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { transportService } from "@/lib/ops/transport";
import { stopProblems } from "@/lib/ops/transport-rules";
import type { Route, Stop } from "@/lib/ops/types";
import { IconPackage } from "@/lib/icons";

export default function RoutePage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  return (
    <TeachingPage module="transport" title="Route stops" icon={<IconPackage width={18} height={18} />} liveNote={OPS_LIVE_NOTE.transport} back={{ href: "/school/transport/routes", label: "Routes & stops" }}>
      {Number.isInteger(id) && id > 0 ? <RouteBody id={id} /> : <div className="alert alert-danger">This route link isn't valid.</div>}
    </TeachingPage>
  );
}

function RouteBody({ id }: { id: number }) {
  const toast = useToast();
  const state = useOptions(useCallback(() => transportService().route(id).then((row) => [row]), [id]));
  const route = state.options[0] ?? null;
  const [editing, setEditing] = useState<Stop | "new" | null>(null);
  const [removing, setRemoving] = useState<Stop | null>(null);
  const [pending, setPending] = useState(false);

  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!route) return <div className="resource-card"><div className="skeleton" style={{ height: 200 }} /></div>;

  const columns: Column<Stop>[] = [
    { key: "order", label: "#", render: (row) => <strong>{row.stop_order}</strong> },
    { key: "name", label: "Stop", render: (row) => <div><strong>{row.name}</strong>{row.landmark ? <div className="muted">{row.landmark}</div> : null}</div> },
    { key: "pickup", label: "Morning pickup", render: (row) => row.pickup_time ?? "—" },
    { key: "drop", label: "Afternoon drop", render: (row) => row.drop_time ?? "—" },
  ];

  return (
    <>
      <section className="resource-card teach-detail" aria-labelledby="route-title">
        <div className="teach-detail-head">
          <div>
            <h2 id="route-title">
              {route.name} {route.status === 1 ? <Chip tone="green">Active</Chip> : <Chip tone="grey">Inactive</Chip>}
            </h2>
            <p className="muted">{route.vehicle_label ?? "No vehicle assigned"}</p>
          </div>
          <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
            Add stop
          </button>
        </div>
        {route.description ? <p className="teach-response">{route.description}</p> : null}
      </section>
      <div className="teach-stats">
        <Stat label="Stops" value={route.stops.length} />
        <Stat label="Students" value={route.assigned_students} tone="blue" />
        <Stat label="Seats" value={route.capacity ?? "—"} tone={route.capacity !== null && route.assigned_students >= route.capacity ? "red" : "green"} />
      </div>
      <section className="resource-card" aria-label="Stops">
        <DataTable
          columns={columns}
          rows={route.stops}
          loading={state.loading}
          emptyText="No stops yet. Add them in the order the vehicle reaches them in the morning."
          actions={(row) => (
            <>
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                Edit
              </button>
              <button className="link-btn danger" type="button" onClick={() => setRemoving(row)}>
                Remove
              </button>
            </>
          )}
        />
      </section>
      {editing ? (
        <StopForm
          route={route}
          stop={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? "Stop added." : "Stop saved.");
            void state.reload();
          }}
        />
      ) : null}
      {removing ? (
        <ConfirmDialog
          title="Remove this stop?"
          body={`${removing.name} will be removed from ${route.name}. Stops where students board can't be removed.`}
          confirmLabel="Remove stop"
          tone="danger"
          pending={pending}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await transportService().removeStop(removing.id);
              toast("success", "Stop removed.");
              void state.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to remove the stop."));
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

function StopForm({ route, stop, onClose, onSaved }: { route: Route; stop: Stop | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const [name, setName] = useState(stop?.name ?? "");
  const [order, setOrder] = useState(String(stop?.stop_order ?? Math.max(0, ...route.stops.map((item) => item.stop_order)) + 1));
  const [pickup, setPickup] = useState(stop?.pickup_time ?? "");
  const [drop, setDrop] = useState(stop?.drop_time ?? "");
  const [landmark, setLandmark] = useState(stop?.landmark ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    const input = { name, stop_order: Number(order), pickup_time: pickup.trim() || null, drop_time: drop.trim() || null, landmark: landmark.trim() || null };
    const problems = stopProblems(input, route.stops, stop?.id);
    if (Object.keys(problems).length) {
      errors.setFieldErrors(problems);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await transportService().saveStop(route.id, input, stop?.id);
      onSaved(!stop);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the stop.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={stop ? "Edit stop" : "Add stop"} description={route.name} error={errors.formError} saving={saving} submitLabel="Save stop" onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="st-name" label="Stop name" required maxLength={80} value={name} onChange={setName} error={errors.fieldErrors.name} />
      <TextField id="st-order" label="Order on the route" type="number" min="1" required value={order} onChange={setOrder} error={errors.fieldErrors.stop_order} />
      <TextField id="st-pickup" label="Morning pickup" placeholder="07:15" value={pickup} onChange={setPickup} error={errors.fieldErrors.pickup_time} hint="24-hour time" />
      <TextField id="st-drop" label="Afternoon drop-off" placeholder="14:40" value={drop} onChange={setDrop} error={errors.fieldErrors.drop_time} hint="24-hour time" />
      <TextField id="st-landmark" label="Landmark" span maxLength={120} value={landmark} onChange={setLandmark} />
    </FormModal>
  );
}
