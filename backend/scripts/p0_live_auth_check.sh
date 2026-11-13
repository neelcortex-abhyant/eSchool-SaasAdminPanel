#!/usr/bin/env bash
# P0 live check: School Admin login, session reuse, logout, domain hostname.
#
# Usage (credentials come from the environment and are never printed):
#   export P0_API=https://eschool-backend-8322.onrender.com     # or the Netlify origin
#   export P0_EMAIL=...  P0_PASSWORD=...                         # QA School Admin
#   export P0_SLUG=qa-sunrise-1105                                # optional
#   bash backend/scripts/p0_live_auth_check.sh
#
# Calls only: /health, /health/ready, /api/v1/auth/login (invalid + valid), /auth/me,
# /school-admin/me, /school-admin/school, /schools/subdomain-availability, /auth/logout.
set -u
API="${P0_API:?set P0_API}"
SLUG="${P0_SLUG:-qa-sunrise-1105}"
pass=0; fail=0

check() { # name expected actual
  if [ "$2" = "$3" ]; then echo "PASS  $1 ($3)"; pass=$((pass+1)); else echo "FAIL  $1 expected=$2 got=$3"; fail=$((fail+1)); fi
}
timed() { # method url [curl args...] -> prints "code seconds" and writes body to /tmp-ish file
  local method=$1 url=$2; shift 2
  curl -s -o "$BODY" -w "%{http_code} %{time_total}" --max-time 120 -X "$method" "$@" "$url"
}
BODY="$(mktemp)"; trap 'rm -f "$BODY"' EXIT

read -r code t < <(timed GET "$API/health");                 echo "      /health ${t}s"; check health 200 "$code"
read -r code t < <(timed GET "$API/health/ready");           echo "      /health/ready ${t}s $(cat "$BODY")"; check health-ready 200 "$code"

read -r code t < <(timed POST "$API/api/v1/auth/login" -H 'content-type: application/json' \
  -d '{"email":"p0-nobody@example.com","password":"definitely-wrong"}')
echo "      invalid login ${t}s $(cat "$BODY")"; check invalid-login-401 401 "$code"

if [ -n "${P0_EMAIL:-}" ] && [ -n "${P0_PASSWORD:-}" ]; then
  payload=$(python -c 'import json,os;print(json.dumps({"email":os.environ["P0_EMAIL"],"password":os.environ["P0_PASSWORD"]}))')
  read -r code t < <(timed POST "$API/api/v1/auth/login" -H 'content-type: application/json' -d "$payload")
  echo "      valid login ${t}s"; check valid-login-200 200 "$code"
  TOKEN=$(python -c 'import json,sys;print(json.load(open(sys.argv[1])).get("access_token",""))' "$BODY" 2>/dev/null)
  ROLE=$(python -c 'import json,sys;print((json.load(open(sys.argv[1])).get("user") or {}).get("role",""))' "$BODY" 2>/dev/null)
  check login-role school_admin "$ROLE"
  if [ "$code" != 200 ]; then echo "      login body: $(cat "$BODY")"; fi
  if [ -n "$TOKEN" ]; then
    H="Authorization: Bearer $TOKEN"
    for round in first refresh new-tab; do
      read -r code t < <(timed GET "$API/api/v1/auth/me" -H "$H");            check "auth-me-$round" 200 "$code"
      read -r code t < <(timed GET "$API/api/v1/school-admin/me" -H "$H");    echo "      school-admin/me ${t}s"; check "school-admin-me-$round" 200 "$code"
    done
    read -r code t < <(timed GET "$API/api/v1/school-admin/school" -H "$H")
    check school-admin-school 200 "$code"
    echo "      stored domain: $(python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("domain"), d.get("domain_type"))' "$BODY" 2>/dev/null)"
    read -r code t < <(timed POST "$API/api/v1/auth/logout" -H "$H");           check logout-204 204 "$code"
    read -r code t < <(timed GET "$API/api/v1/auth/me" -H "$H");                check after-logout-401 401 "$code"
  fi
else
  echo "SKIP  valid-login checks (P0_EMAIL / P0_PASSWORD not set)"
fi

read -r code t < <(timed GET "$API/api/v1/schools/subdomain-availability?slug=$SLUG")
echo "      availability ${t}s $(cat "$BODY")"; check availability-200 200 "$code"
HOST=$(python -c 'import json,sys;print(json.load(open(sys.argv[1])).get("hostname") or "")' "$BODY" 2>/dev/null)
case "$HOST" in *.localhost|"") check hostname-is-production "$SLUG.<base>" "${HOST:-<missing>}";; *) check hostname-has-slug "$SLUG" "${HOST%%.*}";; esac

echo "== $pass passed, $fail failed"
[ "$fail" = 0 ]
