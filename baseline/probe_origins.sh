#!/usr/bin/env bash
# Run on a machine with working DNS/egress before Phase 9.
set -euo pipefail
API_HOST=${API_HOST:-eschool-saas.wrteam.me}
WS_HOST=${WS_HOST:-stage-eschool-saas.wrteam.net}
WS_PORT=${WS_PORT:-9090}

echo "== DNS =="
python3 - <<PY
import socket
for host in ["$API_HOST", "$WS_HOST"]:
    print(host, socket.gethostbyname(host))
PY

echo "== HTTP =="
for url in \
  "https://$API_HOST/" \
  "https://$API_HOST/api/settings" \
  "https://$API_HOST/storage/"; do
  code=$(curl -sS -o /dev/null -w "%{http_code}" -m 20 -L "$url" || true)
  echo "$code $url"
done

echo "== WebSocket TCP =="
python3 - <<PY
import socket
s=socket.create_connection(("$WS_HOST", int("$WS_PORT")), timeout=10)
s.close()
print("OPEN $WS_HOST:$WS_PORT")
PY

echo "Probe complete. Attach output to baseline/FROZEN_ORIGINS.md before Phase 9."
