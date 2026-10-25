import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FeeTypeForm } from "@/components/ops/fees";
import { opsDb, resetOpsMock } from "@/lib/ops/store";

afterEach(cleanup);

beforeEach(() => {
  window.localStorage.clear();
  resetOpsMock();
});

describe("FeeTypeForm", () => {
  it("shows a field error and doesn't save when the name is empty", async () => {
    const onSaved = vi.fn();
    render(<FeeTypeForm type={null} onClose={() => undefined} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "Save fee type" }));
    expect(await screen.findByText("Enter a name.")).toBeTruthy();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("shows the duplicate-name error from the server under the name", async () => {
    render(<FeeTypeForm type={null} onClose={() => undefined} onSaved={() => undefined} />);
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: "Tuition fee" } });
    fireEvent.click(screen.getByRole("button", { name: "Save fee type" }));
    expect(await screen.findAllByText("A fee type with this name already exists.")).not.toHaveLength(0);
  });

  it("saves a new fee type", async () => {
    const onSaved = vi.fn();
    render(<FeeTypeForm type={null} onClose={() => undefined} onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: "Sports fee" } });
    fireEvent.change(screen.getByLabelText(/^Category/), { target: { value: "other" } });
    fireEvent.click(screen.getByRole("button", { name: "Save fee type" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(true));
    expect(opsDb().feeTypes.some((row) => row.name === "Sports fee" && row.category === "other")).toBe(true);
  });
});
