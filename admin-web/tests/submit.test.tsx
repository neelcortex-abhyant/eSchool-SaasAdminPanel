import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { newIdempotencyKey, useSubmitOnce } from "@/lib/ops/submit";

describe("useSubmitOnce", () => {
  it("ignores a second submit while the first is still running", async () => {
    const { result } = renderHook(() => useSubmitOnce());
    let resolve: (value: string) => void = () => undefined;
    let calls = 0;
    const action = () => {
      calls += 1;
      return new Promise<string>((done) => (resolve = done));
    };
    let first: Promise<string | undefined> = Promise.resolve(undefined);
    let second: Promise<string | undefined> = Promise.resolve(undefined);
    act(() => {
      first = result.current.run(action);
      second = result.current.run(action);
    });
    expect(calls).toBe(1);
    expect(result.current.busy).toBe(true);
    await act(async () => {
      resolve("saved");
      await first;
    });
    expect(await first).toBe("saved");
    expect(await second).toBeUndefined();
    expect(result.current.busy).toBe(false);
  });

  it("makes a different idempotency key each time", () => {
    expect(newIdempotencyKey()).not.toBe(newIdempotencyKey());
  });
});
