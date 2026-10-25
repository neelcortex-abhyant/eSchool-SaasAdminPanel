"use client";

import { useCallback, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, StatusToggle, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useDebounced, useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { TRANSPORT_TABS, useTransportStaff } from "@/components/ops/transport";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { transportService } from "@/lib/ops/transport";
import { vehicleProblems } from "@/lib/ops/transport-rules";
import { VEHICLE_TYPES, type Vehicle, type VehicleType } from "@/lib/ops/types";
import { IconPackage } from "@/lib/icons";

export default function VehiclesPage() {
  const [editing, setEditing] = useState<Vehicle | "new" | null>(null);
  return (
    <TeachingPage
      module="transport"
      title="Vehicles"
      description="School buses and vans, their seats, and who drives and helps on each."
      icon={<IconPackage width={18} height={18} />}
      tabs={TRANSPORT_TABS}
      liveNote={OPS_LIVE_NOTE.transport}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add vehicle
        </button>
      }
    >
      <VehiclesBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function VehiclesBody({ editing, setEditing }: { editing: Vehicle | "new" | null; setEditing: (value: Vehicle | "new" | null) => void }) {
  const toast = useToast();
  const state = useOptions(useCallback(() => transportService().vehicles(), []));
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim().toLowerCase());
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const rows = state.options
    .filter((row) => !status || String(row.status) === status)
    .filter((row) => !search || [row.registration_no, row.model ?? "", row.driver_name ?? "", row.helper_name ?? ""].some((value) => value.toLowerCase().includes(search)));

  async function toggle(row: Vehicle) {
    try {
      await transportService().setVehicleStatus(row.id, row.status === 1 ? 0 : 1);
      toast("success", row.status === 1 ? `${row.registration_no} deactivated.` : `${row.registration_no} activated.`);
      void state.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the vehicle."));
    }
  }

  const columns: Column<Vehicle>[] = [
    { key: "reg", label: "Registration", render: (row) => <div><strong>{row.registration_no}</strong><div className="muted">{row.model ?? ""}</div></div> },
    { key: "type", label: "Type", render: (row) => VEHICLE_TYPES.find((item) => item.value === row.vehicle_type)?.label ?? row.vehicle_type },
    {
      key: "seats",
      label: "Seats used",
      render: (row) => <Chip tone={row.assigned_students >= row.capacity ? "red" : row.assigned_students / row.capacity > 0.85 ? "amber" : "green"}>{row.assigned_students} / {row.capacity}</Chip>,
    },
    { key: "driver", label: "Driver", render: (row) => row.driver_name ?? <span className="muted">Not assigned</span> },
    { key: "helper", label: "Helper", render: (row) => row.helper_name ?? <span className="muted">Not assigned</span> },
    { key: "status", label: "Status", render: (row) => (row.status === 1 ? <Chip tone="green">Active</Chip> : <Chip tone="grey">Inactive</Chip>) },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search vehicles" placeholder="Registration, model, driver or helper" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
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
          emptyText={state.error ? "Vehicles couldn't be loaded." : search || status ? "No vehicles match these filters." : "No vehicles yet. Add the school's buses and vans."}
          actions={(row) => (
            <>
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
        <VehicleForm
          vehicle={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? "Vehicle added." : "Vehicle saved.");
            void state.reload();
          }}
        />
      ) : null}
    </>
  );
}

function VehicleForm({ vehicle, onClose, onSaved }: { vehicle: Vehicle | null; onClose: () => void; onSaved: (created: boolean) => void }) {
  const staff = useTransportStaff();
  const [reg, setReg] = useState(vehicle?.registration_no ?? "");
  const [type, setType] = useState<VehicleType>(vehicle?.vehicle_type ?? "bus");
  const [model, setModel] = useState(vehicle?.model ?? "");
  const [capacity, setCapacity] = useState(vehicle ? String(vehicle.capacity) : "");
  const [driverId, setDriverId] = useState(vehicle?.driver_id ? String(vehicle.driver_id) : "");
  const [helperId, setHelperId] = useState(vehicle?.helper_id ? String(vehicle.helper_id) : "");
  const [active, setActive] = useState(vehicle ? vehicle.status === 1 : true);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const staffOptions = staff.options.map((row) => ({ value: String(row.id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }));

  async function submit() {
    const input = { registration_no: reg, vehicle_type: type, model: model.trim() || null, capacity: Number(capacity), driver_id: driverId ? Number(driverId) : null, helper_id: helperId ? Number(helperId) : null, status: (active ? 1 : 0) as 0 | 1 };
    const problems = vehicleProblems(input, vehicle?.assigned_students ?? 0);
    if (Object.keys(problems).length) {
      errors.setFieldErrors(problems);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await transportService().saveVehicle(input, vehicle?.id);
      onSaved(!vehicle);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the vehicle.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={vehicle ? "Edit vehicle" : "Add vehicle"} error={errors.formError} saving={saving} submitLabel="Save vehicle" wide onSubmit={() => void submit()} onClose={onClose}>
      <TextField id="vh-reg" label="Registration number" required maxLength={20} value={reg} onChange={setReg} error={errors.fieldErrors.registration_no} placeholder="KA 01 AB 1234" />
      <SelectField id="vh-type" label="Type" required value={type} onChange={(value) => setType(value as VehicleType)} options={VEHICLE_TYPES.map((item) => ({ value: item.value, label: item.label }))} />
      <TextField id="vh-model" label="Make and model" maxLength={80} value={model} onChange={setModel} />
      <TextField id="vh-capacity" label="Seats for students" type="number" min="1" max="100" required value={capacity} onChange={setCapacity} error={errors.fieldErrors.capacity} hint={vehicle?.assigned_students ? `${vehicle.assigned_students} students ride it now.` : undefined} />
      <SelectField id="vh-driver" label="Driver" placeholder="Not assigned" loading={staff.loading} value={driverId} onChange={setDriverId} options={staffOptions} error={errors.fieldErrors.driver_id} hint="From the staff list; drivers are listed first." />
      <SelectField id="vh-helper" label="Helper" placeholder="Not assigned" loading={staff.loading} value={helperId} onChange={setHelperId} options={staffOptions} error={errors.fieldErrors.helper_id} />
      <StatusToggle id="vh-active" checked={active} onChange={setActive} label="Active (can be used on routes)" />
    </FormModal>
  );
}
