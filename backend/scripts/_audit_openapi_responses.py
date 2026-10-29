"""Enumerate OpenAPI ops whose success JSON lacks a named $ref schema."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from app.main import app

schema = app.openapi()
paths = schema.get("paths") or {}

missing: list[tuple[str, str, str]] = []  # method, path, code
with_ref: list[tuple[str, str, str]] = []
ops = 0

for path, methods in sorted(paths.items()):
    for method, op in methods.items():
        if method.startswith("x-"):
            continue
        ops += 1
        for code in ("200", "201"):
            ok = (op.get("responses") or {}).get(code)
            if not ok:
                continue
            content = ok.get("content") or {}
            if "application/json" not in content:
                continue
            js = content["application/json"].get("schema") or {}
            ref = js.get("$ref")
            if ref:
                with_ref.append((method.upper(), path, code))
            else:
                # Untyped / empty / additionalProperties-only success body
                props = js.get("properties") or {}
                if js.get("type") == "object" and props:
                    # inline object with props — still not a named model
                    missing.append((method.upper(), path, code + ":inline"))
                else:
                    missing.append((method.upper(), path, code))

sa_writes = [m for m in missing if "/school-admin/" in m[1] and m[0] in {"POST", "PUT", "PATCH"}]
sa_all = [m for m in missing if "/school-admin/" in m[1]]
other = [m for m in missing if "/school-admin/" not in m[1]]

print(f"ops={ops} with_named_json_success={len(with_ref)} missing_named={len(missing)}")
print(f"school-admin writes missing={len(sa_writes)}")
print(f"school-admin all missing={len(sa_all)}")
print(f"other modules missing={len(other)}")

by_prefix = defaultdict(int)
for method, path, code in missing:
    parts = path.strip("/").split("/")
    key = "/".join(parts[:3]) if len(parts) >= 3 else path
    by_prefix[key] += 1

print("\n=== missing by prefix (top) ===")
for k, v in sorted(by_prefix.items(), key=lambda x: -x[1])[:25]:
    print(f"{v:4} {k}")

out = Path(__file__).resolve().parents[1] / "docs" / "_openapi_missing_responses.json"
out.write_text(
    json.dumps(
        {
            "ops": ops,
            "with_ref": len(with_ref),
            "missing": [{"method": m, "path": p, "code": c} for m, p, c in missing],
            "school_admin_writes": [{"method": m, "path": p, "code": c} for m, p, c in sa_writes],
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(f"\nWrote {out}")
print("\n=== school-admin writes sample ===")
for row in sa_writes[:40]:
    print(f"{row[0]:6} {row[1]} ({row[2]})")
