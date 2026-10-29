"use client";

import ResourceList from "@/components/ResourceList";

type Expense = {
  id: number;
  title: string | null;
  amount: number | null;
  date: string | null;
  session_year_id: number | null;
  school_id: number | null;
};

export default function ExpensesPage() {
  return (
    <ResourceList<Expense>
      title="Expenses"
      endpoint="/expenses"
      columns={[
        { key: "id", label: "ID" },
        { key: "title", label: "Title" },
        { key: "amount", label: "Amount" },
        { key: "date", label: "Date" },
        { key: "session_year_id", label: "Session year" },
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "title", label: "Title", required: true },
        { key: "amount", label: "Amount", type: "number", required: true },
        { key: "date", label: "Date", type: "date", required: true },
        { key: "session_year_id", label: "Session year ID", type: "number", required: true },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
      ]}
    />
  );
}
