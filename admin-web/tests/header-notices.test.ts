import { describe, expect, it } from "vitest";
import { mergeNotices, noticeDate, unreadCount } from "@/lib/headerNotices";

describe("header bell", () => {
  it("puts announcements and notifications together, newest first, linked to their pages", () => {
    const merged = mergeNotices(
      [{ id: 1, title: "Sports day", description: "Friday on the main ground", created_at: "2026-10-20T09:00:00" }],
      [{ id: 4, title: "Fees due", body: "Pay by the 31st", created_at: "2026-10-27T18:00:00" }, { id: 3, title: "Old", body: null, created_at: "2026-09-01T08:00:00" }],
    );
    expect(merged.map((item) => [item.id, item.href])).toEqual([
      ["notification-4", "/school/notification"],
      ["announcement-1", "/school/announcement"],
      ["notification-3", "/school/notification"],
    ]);
    expect(merged[1]).toMatchObject({ title: "Sports day", detail: "Friday on the main ground" });
    expect(mergeNotices([], Array.from({ length: 12 }, (_, i) => ({ id: i, title: "n", created_at: `2026-10-${String(i + 10)}T00:00:00` })))).toHaveLength(8);
  });

  it("counts what hasn't been seen and formats dates", () => {
    const notices = mergeNotices([{ id: 1, title: "A" }, { id: 2, title: "B" }], []);
    expect(unreadCount(notices, ["announcement-1"])).toBe(1);
    expect(noticeDate("2026-10-27T18:00:00", new Date("2026-12-01"))).toBe("27 Oct");
    expect(noticeDate("2025-01-05T00:00:00", new Date("2026-12-01"))).toBe("5 Jan 2025");
    expect(noticeDate("")).toBe("");
  });
});
