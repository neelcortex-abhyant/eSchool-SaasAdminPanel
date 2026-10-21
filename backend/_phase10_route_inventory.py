"""One-off OpenAPI inventory for Phase 10 (not part of the app)."""

from app.main import app
from fastapi.routing import APIRoute

PREFIXES = (
    "/api/v1/school-admin/classes",
    "/api/v1/school-admin/sections",
    "/api/v1/school-admin/subjects",
    "/api/v1/school-admin/sessions",
    "/api/v1/school-admin/teacher-assignments",
    "/api/v1/school-admin/academics",
    "/api/v1/school-admin/me",
    "/api/v1/school-admin/school",
)

rows = []
for route in app.routes:
    if not isinstance(route, APIRoute):
        continue
    path = route.path
    if not any(path == p or path.startswith(p + "/") or path.startswith(p + "{") for p in PREFIXES):
        if path not in {
            "/api/v1/school-admin/me",
            "/api/v1/school-admin/school",
            "/api/v1/school-admin/sessions",
        } and not path.startswith("/api/v1/school-admin/academics"):
            if not path.startswith("/api/v1/school-admin/classes") and not path.startswith(
                "/api/v1/school-admin/sections"
            ) and not path.startswith("/api/v1/school-admin/subjects") and not path.startswith(
                "/api/v1/school-admin/teacher-assignments"
            ):
                continue
    methods = sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"})
    rows.append((path, ",".join(methods), ",".join(route.tags or [])))

for path, methods, tags in sorted(rows):
    print(f"{methods:20} {path}  [{tags}]")
print("TOTAL", len(rows))
