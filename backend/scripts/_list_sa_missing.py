"""Print remaining school-admin missing named JSON responses."""
from __future__ import annotations

import json
from pathlib import Path

d = json.loads(Path("docs/_openapi_missing_responses.json").read_text(encoding="utf-8"))
sa = [m for m in d["missing"] if "school-admin" in m["path"]]
for m in sa:
    print(f"{m['method']:6} {m['path']}")
print(f"TOTAL {len(sa)}")
