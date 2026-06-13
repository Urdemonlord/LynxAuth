#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/meowlabs/lynxauth"
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"

echo "[deploy] Starting LynxAuth deploy..."

# --- Backup current images for rollback ---
echo "[deploy] Tagging current images for rollback..."
for img in lynxauth-core lynxauth-worker; do
  if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${img}:latest$"; then
    docker tag "${img}:latest" "${img}:prev" 2>/dev/null || true
    echo "[deploy] Tagged ${img}:latest → ${img}:prev"
  fi
done

# --- Load new images ---
echo "[deploy] Loading new images..."
for img in /tmp/lynxauth-core.tar.gz /tmp/lynxauth-worker.tar.gz; do
  if [ -f "$img" ]; then
    gunzip -c "$img" | docker load
    rm -f "$img"
  fi
done

# --- Ensure postgres is running ---
echo "[deploy] Ensuring postgres is healthy..."
docker-compose -f "$COMPOSE_FILE" up -d --no-build postgres 2>&1

# Wait for postgres health via docker healthcheck
for i in $(seq 1 30); do
  PG_STATUS=$(docker inspect --format '{{.State.Health.Status}}' lynxauth-postgres 2>/dev/null || echo "starting")
  if [ "$PG_STATUS" = "healthy" ]; then
    echo "[deploy] Postgres healthy"
    break
  fi
  sleep 2
done

# --- Rollout inference-worker ---
echo "[deploy] Rolling out inference-worker..."
docker-compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps --no-build inference-worker 2>&1

# Wait for worker health (using Python instead of curl, since slim image lacks curl)
sleep 5
for i in $(seq 1 12); do
  if docker-compose -f "$COMPOSE_FILE" exec -T inference-worker python3 -c "
import urllib.request
try:
  r = urllib.request.urlopen('http://localhost:8000/healthz', timeout=5)
  exit(0 if r.status == 200 else 1)
except Exception:
  exit(1)
" 2>/dev/null; then
    echo "[deploy] inference-worker healthy"
    break
  fi
  sleep 5
done

# --- Rollout lynxauth-core ---
echo "[deploy] Rolling out lynxauth-core..."
docker-compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps --no-build lynxauth-core 2>&1

# --- Healthcheck (via exposed port) ---
echo "[deploy] Healthcheck..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://127.0.0.1:8082/healthz 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
  echo "[deploy] ✅ Healthcheck passed (HTTP $HTTP_CODE)"

  # --- Start demo-ui ---
  echo "[deploy] Starting demo-ui..."
  docker-compose -f "$COMPOSE_FILE" up -d --no-deps --no-build demo-ui 2>&1

  # Cleanup old tagged images (remove prev tag, keep latest)
  docker rmi lynxauth-core:prev lynxauth-worker:prev 2>/dev/null || true

  exit 0
else
  echo "[deploy] ❌ Healthcheck failed (HTTP $HTTP_CODE)"

  # --- Rollback ---
  echo "[deploy] Rolling back to previous images..."
  for img in lynxauth-core lynxauth-worker; do
    if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${img}:prev$"; then
      docker tag "${img}:prev" "${img}:latest"
      echo "[deploy] Rolled back ${img} to previous version"
    fi
  done

  docker-compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps --no-build lynxauth-core 2>&1
  sleep 5
  ROLLBACK_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://127.0.0.1:8082/healthz 2>/dev/null || echo "000")
  echo "[deploy] Rollback health: HTTP $ROLLBACK_CODE"

  exit 1
fi
