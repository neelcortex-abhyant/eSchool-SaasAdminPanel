"use client";

import ResourceList from "@/components/ResourceList";

type Expense = {
  id: number;
  title: string | null;
  amount: number | null;
  date: string | null;
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
      ]}
    />
  );
}
