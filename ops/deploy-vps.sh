#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/meowlabs/lynxauth"
BACKUP_IMAGES="/tmp/lynxauth-image-backup.txt"
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"

echo "[deploy] Starting LynxAuth deploy..."

# --- Determine previous image IDs for rollback ---
echo "[deploy] Saving previous image IDs..."
docker images --digests --format "{{.Repository}}:{{.Tag}}@{{.Digest}}" | grep -E "lynxauth-(core|worker)" > "$BACKUP_IMAGES" 2>/dev/null || true

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
docker compose -f "$COMPOSE_FILE" up -d postgres 2>&1

# Wait for postgres health
for i in $(seq 1 30); do
  if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U lynxauth -d lynxauth 2>/dev/null; then
    echo "[deploy] Postgres healthy"
    break
  fi
  sleep 2
done

# --- Rollout inference-worker ---
echo "[deploy] Rolling out inference-worker..."
docker compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps inference-worker 2>&1

# Wait for worker health
sleep 5
for i in $(seq 1 12); do
  if docker compose -f "$COMPOSE_FILE" exec -T inference-worker curl -sf http://localhost:8000/health 2>/dev/null; then
    echo "[deploy] inference-worker healthy"
    break
  fi
  sleep 5
done

# --- Rollout lynxauth-core ---
echo "[deploy] Rolling out lynxauth-core..."
docker compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps lynxauth-core 2>&1

# --- Healthcheck ---
echo "[deploy] Healthcheck..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://127.0.0.1:8082/healthz 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
  echo "[deploy] ✅ Healthcheck passed (HTTP $HTTP_CODE)"

  # --- Start demo-ui ---
  echo "[deploy] Starting demo-ui..."
  docker compose -f "$COMPOSE_FILE" up -d --no-deps demo-ui 2>&1

  # Cleanup old images (keep last 2 tagged versions)
  docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "lynxauth-(core|worker)" | head -n -2 | xargs -r docker rmi 2>/dev/null || true

  exit 0
else
  echo "[deploy] ❌ Healthcheck failed (HTTP $HTTP_CODE)"

  # --- Rollback ---
  if [ -s "$BACKUP_IMAGES" ]; then
    echo "[deploy] Rolling back to previous images..."
    while IFS= read -r img; do
      docker pull "$img" 2>/dev/null || true
    done < "$BACKUP_IMAGES"
  fi

  docker compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps lynxauth-core 2>&1
  sleep 5
  ROLLBACK_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://127.0.0.1:8082/healthz 2>/dev/null || echo "000")
  echo "[deploy] Rollback health: HTTP $ROLLBACK_CODE"

  exit 1
fi
