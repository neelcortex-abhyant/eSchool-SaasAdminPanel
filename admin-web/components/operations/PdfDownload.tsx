"use client";

import { useState } from "react";
import { apiBlobUrl } from "@/lib/api";

/** Downloads a PDF the server makes for signed-in users (fetched with the session token, then saved). */
export function PdfDownload({ path, fileName, label = "Download PDF", className = "btn-pill btn-pill-green-soft" }: { path: string; fileName: string; label?: string; className?: string }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <button
      className={className}
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        setFailed(false);
        try {
          const url = await apiBlobUrl(path);
          const link = document.createElement("a");
          link.href = url;
          link.download = fileName.replace(/[^A-Za-z0-9._-]+/g, "-");
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch {
          setFailed(true);
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? "Downloading…" : failed ? "Couldn't download, try again" : label}
    </button>
  );
}
