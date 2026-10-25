"use client";

import { useCallback, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { FEE_TABS, FeeTypeForm, categoryLabel } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { feeService } from "@/lib/ops/fees";
import type { FeeType } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";

export default function FeeTypesPage() {
  const [editing, setEditing] = useState<FeeType | "new" | null>(null);
  return (
    <TeachingPage
      module="fees"
      title="Fee types"
      description="The kinds of fees the school charges. Fee structures combine these with amounts."
      icon={<IconFees width={18} height={18} />}
      tabs={FEE_TABS}
      liveNote={OPS_LIVE_NOTE.fees}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add fee type
        </button>
      }
    >
      <TypesBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function TypesBody({ editing, setEditing }: { editing: FeeType | "new" | null; setEditing: (value: FeeType | "new" | null) => void }) {
  const toast = useToast();
  const state = useOptions(useCallback(() => feeService().types(), []));
  const [category, setCategory] = useState("");
  const rows = state.options.filter((row) => !category || row.category === category);

  async function toggle(row: FeeType) {
    try {
      await feeService().setTypeStatus(row.id, row.status === 1 ? 0 : 1);
      toast("success", row.status === 1 ? `${row.name} deactivated. Existing structures keep it.` : `${row.name} activated.`);
      void state.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the fee type."));
    }
  }

  const columns: Column<FeeType>[] = [
    { key: "name", label: "Fee type", render: (row) => <strong>{row.name}</strong> },
    { key: "category", label: "Category", render: (row) => categoryLabel(row.category) },
    { key: "description", label: "Description", render: (row) => row.description ?? "—" },
    { key: "status", label: "Status", render: (row) => (row.status === 1 ? <Chip tone="green">Active</Chip> : <Chip tone="grey">Inactive</Chip>) },
  ];

  return (
    <>
      <div className="school-filters">
        <select aria-label="Filter by category" value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">All categories</option>
          <option value="tuition">Tuition</option>
          <option value="admission">Admission</option>
          <option value="examination">Examination</option>
          <option value="transport">Transport</option>
          <option value="other">Other</option>
        </select>
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={state.loading}
          emptyText={state.error ? "Fee types couldn't be loaded." : category ? "No fee types in this category." : "No fee types yet. Add tuition, admission, exam or transport fees."}
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
        <FeeTypeForm
          type={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(created) => {
            setEditing(null);
            toast("success", created ? "Fee type added." : "Fee type saved.");
            void state.reload();
          }}
        />
      ) : null}
    </>
  );
}
