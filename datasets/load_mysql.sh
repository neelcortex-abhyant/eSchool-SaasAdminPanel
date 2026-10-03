#!/usr/bin/env bash
# Load sanitized dumps into Phase 0 Docker MySQL (port 3307).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI not found. Install Docker Desktop, then:"
  echo "  docker compose -f ops/docker-compose.phase0.yml up -d"
  echo "  ./datasets/load_mysql.sh"
  exit 1
fi

docker compose -f ops/docker-compose.phase0.yml up -d
echo "Waiting for MySQL..."
for i in $(seq 1 40); do
  if docker exec eschool-phase0-mysql mysqladmin ping -h 127.0.0.1 -ueschool -peschool --silent; then
    break
  fi
  sleep 1
done

python3 datasets/generate_sanitized_dumps.py

for f in datasets/central.data.sanitized.sql datasets/eschool_tenant_a.data.sanitized.sql datasets/eschool_tenant_b.data.sanitized.sql; do
  echo "Loading $f"
  docker exec -i eschool-phase0-mysql mysql -ueschool -peschool < "$f"
done
echo "Done. Databases: eschool_central, eschool_tenant_a, eschool_tenant_b"
