#!/bin/sh
set -e

# ── 1. Start MongoDB in background ─────────────────────────────────────────
echo "[entrypoint] Starting MongoDB..."
mongod \
    --dbpath=/data/db \
    --bind_ip=0.0.0.0 \
    --port=27017 \
    --quiet \
    --nounixsocket &
MONGO_PID=$!

# ── 2. Wait until MongoDB accepts TCP connections (max 60s) ─────────────────
echo "[entrypoint] Waiting for MongoDB to be ready..."
python3 - <<'EOF'
import socket, sys, time

for attempt in range(60):
    try:
        s = socket.create_connection(("127.0.0.1", 27017), timeout=1)
        s.close()
        print("[entrypoint] MongoDB is ready.")
        sys.exit(0)
    except OSError:
        time.sleep(1)

print("[entrypoint] ERROR: MongoDB did not become available after 60s", file=sys.stderr)
sys.exit(1)
EOF

# If MongoDB exited while we were waiting, bail out
if ! kill -0 "$MONGO_PID" 2>/dev/null; then
    echo "[entrypoint] ERROR: MongoDB process exited unexpectedly"
    exit 1
fi

# ── 3. Graceful shutdown: forward SIGTERM/INT to MongoDB ─────────────────────
cleanup() {
    echo "[entrypoint] Shutting down MongoDB (pid $MONGO_PID)..."
    kill -TERM "$MONGO_PID" 2>/dev/null
    wait "$MONGO_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

# ── 4. Start the API in the foreground (becomes PID 1 via exec) ──────────────
echo "[entrypoint] Starting API on port ${PORT:-8000}..."
exec hypercorn app.main:asgi_app --bind "0.0.0.0:${PORT:-8000}"
