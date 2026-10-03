#!/usr/bin/env python3
"""Parse Laravel routes/api.php and public payment/webhook web routes into JSON manifests."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

API_FILE = Path(
    "/Users/apple/eSchool-Saas-V1.11.0/Admin Panel Code/PHP CODE/PHP_CODE_V1.11.0/routes/api.php"
)
WEB_FILE = Path(
    "/Users/apple/eSchool-Saas-V1.11.0/Admin Panel Code/PHP CODE/PHP_CODE_V1.11.0/routes/web.php"
)
OUT_DIR = Path("/Users/apple/eSchool-SaasAdminPanel/contract-tests/manifest")

# Confirmed in app/Providers/RouteServiceProvider.php
API_PREFIX = "/api"
API_DEFAULT_MIDDLEWARE = ["api"]
WEB_DEFAULT_MIDDLEWARE = ["web"]

METHOD_MAP = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "options": "OPTIONS",
    "any": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
}

AUTH_STACK_MW = {
    "Role",
    "checkSchoolStatus",
    "status",
    "SwitchDatabase",
    "verifiedEmail",
    "2fa",
    "wizardSettings",
    "language",
    "academySetupWizard",
}


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    out_lines: list[str] = []
    for line in src.splitlines():
        if "//" not in line:
            out_lines.append(line)
            continue
        in_str = False
        quote = None
        cut = None
        i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == "\\" and i + 1 < len(line):
                    i += 2
                    continue
                if ch == quote:
                    in_str = False
                    quote = None
            else:
                if ch in ("'", '"'):
                    in_str = True
                    quote = ch
                elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                    cut = i
                    break
            i += 1
        out_lines.append(line if cut is None else line[:cut])
    return "\n".join(out_lines)


def parse_php_array_or_string(s: str) -> list[str]:
    s = s.strip()
    if s.startswith("["):
        inner = s[1:-1].strip()
        if not inner:
            return []
        parts = re.findall(r"'([^']+)'|\"([^\"]+)\"", inner)
        return [a or b for a, b in parts]
    m = re.match(r"^['\"]([^'\"]+)['\"]$", s)
    if m:
        return [m.group(1)]
    return [s.strip("'\"")]


def join_path(*parts: str) -> str:
    segs: list[str] = []
    for p in parts:
        if not p:
            continue
        for s in p.strip("/").split("/"):
            if s:
                segs.append(s)
    return "/" + "/".join(segs) if segs else "/"


def normalize_uri(uri: str) -> str:
    uri = uri.strip().strip("'\"")
    if uri in ("", "/"):
        return ""
    return uri.strip("/")


def split_args(blob: str) -> list[str]:
    args: list[str] = []
    cur: list[str] = []
    depth = 0
    in_str = False
    quote = None
    i = 0
    while i < len(blob):
        ch = blob[i]
        if in_str:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(blob):
                cur.append(blob[i + 1])
                i += 2
                continue
            if ch == quote:
                in_str = False
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            cur.append(ch)
        elif ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        args.append("".join(cur).strip())
    return args


def extract_controller_action(action_src: str) -> str | None:
    action_src = action_src.strip()
    m = re.search(
        r"\[\s*([A-Za-z0-9_\\]+)::class\s*,\s*['\"]([^'\"]+)['\"]\s*\]",
        action_src,
    )
    if m:
        cls = m.group(1).split("\\")[-1]
        return f"{cls}@{m.group(2)}"
    m = re.search(r"['\"]([^'\"]+@[^'\"]+)['\"]", action_src)
    if m:
        return m.group(1).split("\\")[-1]
    if "function" in action_src:
        return None
    return None


def classify_auth(middleware: list[str], path: str) -> str:
    path_l = path.lower()
    if "transportation/live-tracking/session" in path_l:
        return "tracking_token"
    if "auth:sanctum" in middleware or "APISwitchDatabase" in middleware:
        return "bearer"
    if any(
        x in path_l
        for x in (
            "/login",
            "forgot-password",
            "/webhook",
            "whatsapp/webhook",
            "/payment/",
            "subscription/cron-job",
        )
    ):
        return "none"
    if path_l in {
        "/api/system-settings",
        "/api/get-languages",
        "/api/set-languages",
        "/api/settings",
        "/api/school-details",
        "/api/firebase-config",
        "/api/fees-due-notification",
        "/api/certificate/generate",
        "/api/transport/receipt",
    }:
        return "none"
    if any(m in middleware for m in AUTH_STACK_MW):
        return "session"
    return "unknown"


def classify_tenant(middleware: list[str], path: str) -> str:
    path_l = path.lower()
    if "transportation/live-tracking/session" in path_l:
        return "tracking"
    if "whatsapp/webhook/" in path_l or "{schoolcode}" in path_l:
        return "path"
    if (
        "APISwitchDatabase" in middleware
        or "checkSchoolStatus" in middleware
        or "checkChild" in middleware
    ):
        return "school-code header"
    if any(x in path_l for x in ("/login", "forgot-password")):
        return "body"
    if path_l in {"/api/school-details", "/api/certificate/generate", "/api/transport/receipt"}:
        return "body"
    if "/webhook" in path_l or "/payment/" in path_l or "subscription/cron-job" in path_l:
        return "none"
    if path_l in {
        "/api/system-settings",
        "/api/get-languages",
        "/api/set-languages",
        "/api/settings",
        "/api/firebase-config",
        "/api/fees-due-notification",
    }:
        return "none"
    return "unknown"


def build_notes(middleware: list[str], path: str, controller: str | None, removed: list[str]) -> str:
    parts: list[str] = []
    if removed:
        parts.append("withoutMiddleware: " + ", ".join(removed))
    if "transportation/live-tracking/session" in path:
        parts.append(
            "Auth via X-Tracking-Token; school DB resolved from token; outside APISwitchDatabase"
        )
    if "whatsapp/webhook/{schoolCode}" in path:
        parts.append("Meta WhatsApp Cloud API webhook; school from path param")
    if "APISwitchDatabase" in middleware:
        parts.append("Requires school-code header; validates Sanctum bearer token")
    if classify_auth(middleware, path) == "none" and any(
        x in path for x in ("/login", "forgot-password")
    ):
        parts.append("Unauthenticated; school_code expected in request body")
    if controller and "Webhook" in controller and "WhatsApp" not in controller:
        parts.append("Provider webhook; signature validation in controller")
    return "; ".join(parts)


def parse_options_array(opts: str) -> tuple[str, list[str]]:
    prefix_add = ""
    mw_add: list[str] = []
    pm = re.search(r"['\"]prefix['\"]\s*=>\s*['\"]([^'\"]*)['\"]", opts)
    if pm:
        prefix_add = pm.group(1)
    # middleware may be nested array — find value after =>
    mm = re.search(r"['\"]middleware['\"]\s*=>\s*", opts)
    if mm:
        rest = opts[mm.end() :].lstrip()
        if rest.startswith("["):
            depth = 0
            j = 0
            while j < len(rest):
                if rest[j] == "[":
                    depth += 1
                elif rest[j] == "]":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            mw_add = parse_php_array_or_string(rest[:j])
        else:
            m2 = re.match(r"['\"]([^'\"]+)['\"]", rest)
            if m2:
                mw_add = [m2.group(1)]
    return prefix_add, mw_add


def scan_balanced_array(src: str, start: int) -> tuple[str, int]:
    """src[start] == '['; return array text and index after it."""
    depth = 0
    j = start
    while j < len(src):
        ch = src[j]
        if ch in ("'", '"'):
            q = ch
            j += 1
            while j < len(src) and src[j] != q:
                if src[j] == "\\":
                    j += 2
                    continue
                j += 1
            j += 1
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return src[start : j + 1], j + 1
        j += 1
    return src[start:], len(src)


def add_route_from_call(
    call: str, method_name: str, stack: list[dict[str, Any]], routes: list[dict[str, Any]]
) -> None:
    cur = stack[-1]
    # Isolate Route::method(...) portion before chained ->helpers
    m = re.match(r"Route::[A-Za-z_]+\s*\(", call)
    if not m:
        return
    depth = 0
    i = m.end() - 1
    start_args = m.end()
    j = i
    while j < len(call):
        ch = call[j]
        if ch in ("'", '"'):
            q = ch
            j += 1
            while j < len(call) and call[j] != q:
                if call[j] == "\\":
                    j += 2
                    continue
                j += 1
            j += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                args_blob = call[start_args:j]
                j += 1
                break
        j += 1
    else:
        return

    chain = call[j:]
    args = split_args(args_blob)
    if not args:
        return

    if method_name == "match":
        methods_raw = parse_php_array_or_string(args[0])
        methods: Any = [
            METHOD_MAP.get(x.lower(), x.upper()) if isinstance(x, str) else x for x in methods_raw
        ]
        if len(methods) == 1:
            methods = methods[0]
        uri_raw = args[1]
        action_src = args[2] if len(args) > 2 else ""
    else:
        methods = METHOD_MAP[method_name]
        uri_raw = args[0]
        action_src = args[1] if len(args) > 1 else ""

    path = join_path(cur["prefix"], normalize_uri(uri_raw))
    mw = list(cur["middleware"])
    removed: list[str] = []

    for cm in re.finditer(
        r"->(name|withoutMiddleware|middleware)\s*\(",
        chain,
    ):
        kind = cm.group(1)
        arg_start = cm.end()
        # find matching close paren
        depth = 1
        k = arg_start
        while k < len(chain) and depth:
            ch = chain[k]
            if ch in ("'", '"'):
                q = ch
                k += 1
                while k < len(chain) and chain[k] != q:
                    if chain[k] == "\\":
                        k += 2
                        continue
                    k += 1
                k += 1
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            k += 1
        arg_text = chain[arg_start : k - 1]
        if kind == "withoutMiddleware":
            removed = parse_php_array_or_string(arg_text)
            mw = [x for x in mw if x not in removed]
        elif kind == "middleware":
            for x in parse_php_array_or_string(arg_text):
                if x not in mw:
                    mw.append(x)

    controller = extract_controller_action(action_src)
    auth = classify_auth(mw, path)
    tenant = classify_tenant(mw, path)
    notes = build_notes(mw, path, controller, removed)

    routes.append(
        {
            "method": methods,
            "path": path,
            "middleware": mw,
            "controller": controller,
            "auth": auth,
            "tenant_source": tenant,
            "notes": notes,
        }
    )


def parse_route_body(
    src: str, stack: list[dict[str, Any]], routes: list[dict[str, Any]]
) -> None:
    i = 0
    n = len(src)

    def current() -> dict[str, Any]:
        return stack[-1]

    while i < n:
        if src[i].isspace():
            i += 1
            continue
        if not src.startswith("Route::", i):
            i += 1
            continue

        j = i + 7
        m = re.match(r"([A-Za-z_]+)", src[j:])
        if not m:
            i += 7
            continue
        method_name = m.group(1)
        j += len(method_name)

        if method_name == "group":
            while j < n and src[j].isspace():
                j += 1
            if j < n and src[j] == "(":
                j += 1
            while j < n and src[j].isspace():
                j += 1
            if j < n and src[j] == "[":
                opts, j = scan_balanced_array(src, j)
            else:
                opts = "[]"
            prefix_add, mw_add = parse_options_array(opts)
            brace = src.find("{", j)
            if brace == -1:
                i = j
                continue
            new_prefix = (
                join_path(current()["prefix"], prefix_add)
                if prefix_add
                else current()["prefix"]
            )
            stack.append(
                {
                    "prefix": new_prefix,
                    "middleware": current()["middleware"]
                    + [x for x in mw_add if x not in current()["middleware"]],
                }
            )
            depth = 1
            k = brace + 1
            body_start = k
            while k < n and depth:
                ch = src[k]
                if ch in ("'", '"'):
                    q = ch
                    k += 1
                    while k < n and src[k] != q:
                        if src[k] == "\\":
                            k += 2
                            continue
                        k += 1
                    k += 1
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                k += 1
            parse_route_body(src[body_start : k - 1], stack, routes)
            stack.pop()
            i = k
            while i < n and src[i] in "); \t\n\r":
                if src[i] == ";":
                    i += 1
                    break
                i += 1
            continue

        if method_name == "prefix":
            pm = re.match(r"\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", src[j:])
            if not pm:
                i = j
                continue
            prefix_add = pm.group(1)
            j += pm.end()
            while True:
                nm = re.match(r"\s*->name\s*\(\s*['\"][^'\"]*['\"]\s*\)", src[j:])
                if not nm:
                    break
                j += nm.end()
            gm = re.match(
                r"\s*->group\s*\(\s*(?:static\s+)?function\s*\([^)]*\)\s*\{", src[j:]
            )
            if not gm:
                i = j
                continue
            j += gm.end()
            brace = j - 1
            stack.append(
                {
                    "prefix": join_path(current()["prefix"], prefix_add),
                    "middleware": list(current()["middleware"]),
                }
            )
            depth = 1
            k = brace + 1
            body_start = k
            while k < n and depth:
                ch = src[k]
                if ch in ("'", '"'):
                    q = ch
                    k += 1
                    while k < n and src[k] != q:
                        if src[k] == "\\":
                            k += 2
                            continue
                        k += 1
                    k += 1
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                k += 1
            parse_route_body(src[body_start : k - 1], stack, routes)
            stack.pop()
            i = k
            while i < n and src[i] in "); \t\n\r":
                if src[i] == ";":
                    i += 1
                    break
                i += 1
            continue

        if method_name in METHOD_MAP or method_name == "match":
            while j < n and src[j].isspace():
                j += 1
            if j >= n or src[j] != "(":
                i = j
                continue
            depth = 0
            start = i
            k = j
            while k < n:
                ch = src[k]
                if ch in ("'", '"'):
                    q = ch
                    k += 1
                    while k < n and src[k] != q:
                        if src[k] == "\\":
                            k += 2
                            continue
                        k += 1
                    k += 1
                    continue
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        k += 1
                        break
                k += 1
            # chained helpers
            while True:
                cm = re.match(
                    r"\s*->(name|withoutMiddleware|middleware)\s*\(",
                    src[k:],
                )
                if not cm:
                    break
                k += cm.end()
                depth = 1
                while k < n and depth:
                    ch = src[k]
                    if ch in ("'", '"'):
                        q = ch
                        k += 1
                        while k < n and src[k] != q:
                            if src[k] == "\\":
                                k += 2
                                continue
                            k += 1
                        k += 1
                        continue
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    k += 1
            while k < n and src[k].isspace():
                k += 1
            if k < n and src[k] == ";":
                k += 1
            add_route_from_call(src[start:k], method_name, stack, routes)
            i = k
            continue

        # resource / Auth::routes / etc. — skip statement
        semi = src.find(";", j)
        if semi == -1:
            break
        i = semi + 1

    return


def parse_route_file(
    src: str, *, base_prefix: str, default_middleware: list[str]
) -> list[dict[str, Any]]:
    src = strip_comments(src)
    stack: list[dict[str, Any]] = [
        {"prefix": base_prefix.rstrip("/") or "", "middleware": list(default_middleware)}
    ]
    # Normalize empty base to "" so join_path works; use "/api" as prefix string without forcing trailing
    if base_prefix and not stack[0]["prefix"].startswith("/"):
        stack[0]["prefix"] = "/" + stack[0]["prefix"]
    routes: list[dict[str, Any]] = []
    parse_route_body(src, stack, routes)
    return routes


def dedupe(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for r in routes:
        key = (json.dumps(r["method"], sort_keys=True), r["path"], r.get("controller"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def sort_key(r: dict[str, Any]) -> tuple:
    m = r["method"] if isinstance(r["method"], str) else ",".join(r["method"])
    return (r["path"], m)


def reshape(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": r["method"],
        "path": r["path"],
        "middleware": r["middleware"],
        "controller": r["controller"],
        "auth": r["auth"],
        "tenant_source": r["tenant_source"],
        "notes": r["notes"],
    }


def is_public_payment_related(r: dict[str, Any]) -> bool:
    path = r["path"].lower()
    mw = r["middleware"]
    if any(m in mw for m in AUTH_STACK_MW):
        return False
    keywords = (
        "webhook",
        "payment",
        "subscription",
        "whatsapp",
        "callback",
        "paystack",
        "flutterwave",
        "razorpay",
        "stripe",
    )
    return any(k in path for k in keywords)


KNOWN_WEB = [
    {
        "method": "POST",
        "path": "/webhook/razorpay",
        "middleware": ["web"],
        "controller": "WebhookController@razorpay",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public fee payment webhook",
    },
    {
        "method": "POST",
        "path": "/webhook/stripe",
        "middleware": ["web"],
        "controller": "WebhookController@stripe",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public fee payment webhook",
    },
    {
        "method": "POST",
        "path": "/webhook/paystack",
        "middleware": ["web"],
        "controller": "WebhookController@paystack",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public fee payment webhook",
    },
    {
        "method": "POST",
        "path": "/webhook/flutterwave",
        "middleware": ["web"],
        "controller": "WebhookController@flutterwave",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public fee payment webhook",
    },
    {
        "method": "POST",
        "path": "/subscription/webhook/stripe",
        "middleware": ["web"],
        "controller": "SubscriptionWebhookController@stripe",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public SaaS subscription webhook",
    },
    {
        "method": "POST",
        "path": "/subscription/webhook/razorpay",
        "middleware": ["web"],
        "controller": "SubscriptionWebhookController@razorpay",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public SaaS subscription webhook",
    },
    {
        "method": "POST",
        "path": "/subscription/webhook/paystack",
        "middleware": ["web"],
        "controller": "SubscriptionWebhookController@paystack",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public SaaS subscription webhook",
    },
    {
        "method": "POST",
        "path": "/subscription/webhook/flutterwave",
        "middleware": ["web"],
        "controller": "SubscriptionWebhookController@flutterwave",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public SaaS subscription webhook",
    },
    {
        "method": "GET",
        "path": "/payment/status",
        "middleware": ["web"],
        "controller": "PaymentController@status",
        "auth": "none",
        "tenant_source": "none",
        "notes": "App payment return URL; defined twice in web.php (prefix group + standalone)",
    },
    {
        "method": "GET",
        "path": "/payment/cancel",
        "middleware": ["web"],
        "controller": "PaymentController@cancel",
        "auth": "none",
        "tenant_source": "none",
        "notes": "App payment cancel URL",
    },
    {
        "method": "GET",
        "path": "/subscription/cron-job",
        "middleware": ["web", "CheckForMaintenanceMode"],
        "controller": "Controller@cron_job",
        "auth": "none",
        "tenant_source": "none",
        "notes": "Public subscription cron trigger under CheckForMaintenanceMode only",
    },
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    api_routes = dedupe(
        parse_route_file(
            API_FILE.read_text(encoding="utf-8"),
            base_prefix=API_PREFIX,
            default_middleware=API_DEFAULT_MIDDLEWARE,
        )
    )

    # Normalize known public / special routes
    for r in api_routes:
        if r["path"] == "/api/transportation/live-tracking/session":
            r["auth"] = "tracking_token"
            r["tenant_source"] = "tracking"
        elif "APISwitchDatabase" in r["middleware"]:
            r["auth"] = "bearer"
            r["tenant_source"] = "school-code header"
        elif r["auth"] == "unknown":
            r["auth"] = classify_auth(r["middleware"], r["path"])
            r["tenant_source"] = classify_tenant(r["middleware"], r["path"])

    api_out = [reshape(r) for r in api_routes]
    api_out.sort(key=sort_key)
    (OUT_DIR / "laravel_api_routes.json").write_text(
        json.dumps(api_out, indent=2) + "\n", encoding="utf-8"
    )

    web_all = dedupe(
        parse_route_file(
            WEB_FILE.read_text(encoding="utf-8"),
            base_prefix="",
            default_middleware=WEB_DEFAULT_MIDDLEWARE,
        )
    )
    web_pay = [reshape(r) for r in web_all if is_public_payment_related(r)]
    by_key: dict[tuple, dict] = {}
    for r in web_pay:
        r["auth"] = "none"
        if r["tenant_source"] == "unknown":
            r["tenant_source"] = "none"
        by_key[(json.dumps(r["method"]), r["path"])] = r
    for r in KNOWN_WEB:
        key = (json.dumps(r["method"]), r["path"])
        if key not in by_key:
            by_key[key] = dict(r)
        else:
            existing = by_key[key]
            if r["notes"] and r["notes"] not in (existing.get("notes") or ""):
                existing["notes"] = ((existing.get("notes") or "") + "; " + r["notes"]).strip("; ")
            if not existing.get("controller"):
                existing["controller"] = r["controller"]
            # ensure cron-job keeps CheckForMaintenanceMode
            if r["path"] == "/subscription/cron-job":
                existing["middleware"] = r["middleware"]

    web_out = list(by_key.values())
    web_out.sort(key=sort_key)
    (OUT_DIR / "laravel_web_payment_routes.json").write_text(
        json.dumps(web_out, indent=2) + "\n", encoding="utf-8"
    )

    method_c: Counter[str] = Counter()
    for r in api_out:
        if isinstance(r["method"], list):
            for m in r["method"]:
                method_c[m] += 1
        else:
            method_c[r["method"]] += 1
    auth_c = Counter(r["auth"] for r in api_out)
    tenant_c = Counter(r["tenant_source"] for r in api_out)

    expected = [
        "/api/student/login",
        "/api/student/class-subjects",
        "/api/parent/fees",
        "/api/teacher/online-classes",
        "/api/staff/qr-attendance/punch",
        "/api/staff/tasks",
        "/api/transportation/live-tracking/session",
        "/api/whatsapp/webhook/{schoolCode}",
        "/api/webhook/stripe",
    ]
    missing = [e for e in expected if not any(r["path"] == e for r in api_out)]

    lines = [
        "# Laravel routes manifest summary",
        "",
        "Parsed from eSchool SaaS V1.11.0 Admin Panel PHP code.",
        "",
        "## Sources",
        "",
        "| File | Role |",
        "|------|------|",
        "| `routes/api.php` | Mobile/API contracts (all routes) |",
        "| `routes/web.php` | Public payment/webhook/subscription/callback routes only |",
        "| `app/Providers/RouteServiceProvider.php` | Confirms `Route::prefix('api')->middleware('api')` for `api.php`; `web` middleware for `web.php` |",
        "",
        "## API (`laravel_api_routes.json`)",
        "",
        f"- **Total routes:** {len(api_out)}",
        f"- **HTTP methods:** {', '.join(f'{k}={v}' for k, v in sorted(method_c.items()))}",
        f"- **Auth breakdown:** {', '.join(f'{k}={v}' for k, v in sorted(auth_c.items()))}",
        f"- **Tenant source breakdown:** {', '.join(f'{k}={v}' for k, v in sorted(tenant_c.items()))}",
        "",
        "### Prefix & middleware model",
        "",
        "- Global path prefix: `/api` (RouteServiceProvider).",
        "- Default middleware group: `api`.",
        "- Tenant DB switching for authenticated mobile APIs: `APISwitchDatabase` (reads `school-code` header, validates Sanctum bearer token).",
        "- Often combined with `checkSchoolStatus` (student/teacher/staff) or `checkChild` (parent child-scoped).",
        "- Nested `auth:sanctum` appears only on a small teacher student-result subset (in addition to `APISwitchDatabase`).",
        "- WhatsApp Meta webhook uses `{schoolCode}` **path** param (no bearer).",
        "- Live-tracking WebView session uses `X-Tracking-Token` (auth=`tracking_token`, tenant=`tracking`); deliberately outside `APISwitchDatabase`.",
        "- Login / forgot-password routes are unauthenticated and expect `school_code` in the **body**.",
        "",
        "### Major path groups",
        "",
        "| Prefix | Audience |",
        "|--------|----------|",
        "| `/api/student/*` | Student app |",
        "| `/api/parent/*` | Parent/guardian app (fees under `/api/parent/fees`) |",
        "| `/api/teacher/*` | Teacher app (+ `/online-classes`) |",
        "| `/api/staff/*` | Staff app (payroll, QR attendance, tasks, leaves) |",
        "| `/api/webhook/*`, `/api/subscription/webhook/*` | Payment provider webhooks |",
        "| `/api/whatsapp/webhook/{schoolCode}` | Meta WhatsApp verify/receive |",
        "| `/api/transportation/*`, `/api/transport/*` | Transportation / live tracking |",
        "| other `/api/*` | Shared settings, chat, leaves, certificates, etc. |",
        "",
        "## Web payment/public (`laravel_web_payment_routes.json`)",
        "",
        f"- **Total routes:** {len(web_out)}",
        "- These are routes **outside** the authenticated `Role` / school-admin middleware stack.",
        "- Includes fee webhooks, subscription webhooks, app payment status/cancel return URLs, and `subscription/cron-job`.",
        "- No public WhatsApp routes exist in `web.php` (WhatsApp webhooks live under `/api/whatsapp/webhook/{schoolCode}`).",
        "- Authenticated admin subscription/addon payment success pages were excluded (session/`Role` protected).",
        "",
        "### Routes",
        "",
    ]
    for r in web_out:
        m = r["method"] if isinstance(r["method"], str) else "+".join(r["method"])
        ctrl = r.get("controller") or "closure"
        lines.append(f"- `{m} {r['path']}` → `{ctrl}`")

    lines += [
        "",
        "## Notes for contract tests",
        "",
        "- Prefer `/api/...` paths from `laravel_api_routes.json` for Flutter/student-web reconciliation.",
        "- Provider webhooks are registered on **both** `api.php` (`/api/webhook/...`) and `web.php` (`/webhook/...`); treat as parallel entry points.",
        "- `GET /payment/status` is registered twice in `web.php` (identical action); manifest de-duplicates to one record.",
        "- Regenerator: `contract-tests/scripts/parse_laravel_routes.py`.",
        "- Do not modify Laravel source; regenerate these manifests if `routes/*.php` changes.",
        "",
    ]
    (OUT_DIR / "laravel_routes_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"API routes: {len(api_out)}")
    print(f"Web payment routes: {len(web_out)}")
    print("API methods:", dict(method_c))
    print("Auth:", dict(auth_c))
    print("Tenant:", dict(tenant_c))
    if missing:
        print("MISSING expected:", missing)
        raise SystemExit(1)
    print("Expected spot-checks OK")


if __name__ == "__main__":
    main()
