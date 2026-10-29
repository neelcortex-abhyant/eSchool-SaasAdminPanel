"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, StatusToggle, TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useDebounced, useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { TRANSPORT_TABS } from "@/components/ops/transport";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { transportService } from "@/lib/ops/transport";
import type { Route } from "@/lib/ops/types";
import { IconPackage } from "@/lib/icons";

export default function RoutesPage() {
  const [editing, setEditing] = useState<Route | "new" | null>(null);
  return (
    <TeachingPage
      module="transport"
      title="Routes & stops"
      description="Each route has a vehicle and an ordered list of stops with pickup and drop-off times."
      icon={<IconPackage width={18} height={18} />}
      tabs={TRANSPORT_TABS}
      liveNote={OPS_LIVE_NOTE.transport}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add route
        </button>
      }
    >
      <RoutesBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function RoutesBody({ editing, setEditing }: { editing: Route | "new" | null; setEditing: (value: Route | "new" | null) => void }) {
  const toast = useToast();
  const state = useOptions(useCallback(() => transportService().routes(), []));
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim().toLowerCase());
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const rows = state.options
    .filter((row) => !status || String(row.status) === status)
    .filter((row) => !search || [row.name, row.description ?? "", row.vehicle_label ?? "", ...row.stops.map((stop) => stop.name)].some((value) => value.toLowerCase().includes(search)));

  async function toggle(row: Route) {
    try {
      await transportService().setRouteStatus(row.id, row.status === 1 ? 0 : 1);
      toast("success", row.status === 1 ? `${row.name} deactivated.` : `${row.name} activated.`);
      void state.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the route."));
    }
  }

  const columns: Column<Route>[] = [
    { key: "name", label: "Route", render: (row) => <div><Link className="teach-strong-link" href={`/school/transport/routes/${row.id}`}>{row.name}</Link>{row.description ? <div className="muted">{row.description}</div> : null}</div> },
    { key: "vehicle", label: "Vehicle", render: (row) => row.vehicle_label ?? <span className="muted">No vehicle</span> },
    { key: "stops", label: "Stops", render: (row) => (row.stops.length ? <span className="muted">{row.stops.map((stop) => stop.name).join(" → ")}</span> : <span className="muted">No stops yet</span>) },
    {
      key: "riders",
      label: "Students",
      render: (row) => (row.capacity === null ? row.assigned_students : <Chip tone={row.assigned_students >= row.capacity ? "red" : "green"}>{row.assigned_students} / {row.capacity}</Chip>),
    },
    { key: "status", label: "Status", render: (row) => (row.status === 1 ? <Chip tone="green">Active</Chip> : <Chip tone="grey">Inactive</Chip>) },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search routes" placeholder="Route, stop or vehicle" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
        <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value as "" | "0" | "1")}>
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={state.loading}
          emptyText={state.error ? "Routes couldn't be loaded." : search || status ? "No routes match these filters." : "No routes yet."}
          actions={(row) => (
            <>
              <Link className="link-btn" href={`/school/transport/routes/${row.id}`}>
                Stops
              </Link>
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                Edit
              </button>
              <button className={`link-btn${row.status === 1 ? " danger" : ""}`} type="button" onClick={() => void toggle(row)}>
                {row.status === 1 ? "Deactivate" : "Activate"}
              </button>
            </>
          )}
        />
      </div>
      {editing ? (
        <RouteForm
          route={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? "Route added. Open it to add stops." : "Route saved.");
            void state.reload();
          }}
        />
      ) : null}
    </>
  );
}

function RouteForm({ route, onClose, onSaved }: { route: Route | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const vehicles = useOptions(useCallback(() => transportService().vehicles(), []));
  const [name, setName] = useState(route?.name ?? "");
  const [description, setDescription] = useState(route?.description ?? "");
  const [vehicleId, setVehicleId] = useState(route?.vehicle_id ? String(route.vehicle_id) : "");
  const [active, setActive] = useState(route ? route.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    if (!name.trim()) {
      errors.setFieldErrors({ name: "Enter the route name." });
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await transportService().saveRoute({ name, description: description || null, vehicle_id: vehicleId ? Number(vehicleId) : null, status: active ? 1 : 0 }, route?.id);
      onSaved(!route);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the route.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={route ? "Edit route" : "Add route"} error={errors.formError} saving={saving} submitLabel="Save route" onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="rt-name" label="Route name" required maxLength={80} value={name} onChange={setName} error={errors.fieldErrors.name} placeholder="Route 3 – Whitefield" />
      <SelectField
        id="rt-vehicle"
        label="Vehicle"
        placeholder="No vehicle yet"
        loading={vehicles.loading}
        value={vehicleId}
        onChange={setVehicleId}
        options={vehicles.options.filter((row) => row.status === 1 || String(row.id) === vehicleId).map((row) => ({ value: String(row.id), label: `${row.registration_no} · ${row.assigned_students}/${row.capacity} seats used` }))}
        error={errors.fieldErrors.vehicle_id}
      />
      <TextAreaField id="rt-description" label="Description" span maxLength={255} value={description} onChange={setDescription} />
      <StatusToggle id="rt-active" checked={active} onChange={setActive} label="Active" />
    </FormModal>
  );
}
