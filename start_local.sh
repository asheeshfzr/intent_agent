#!/usr/bin/env bash
# Robust startup for the POC services
# Copies .env.example -> .env if missing, then exports env vars safely.

set -euo pipefail

# Helper: kill whatever is listening on a port (macOS/Linux)
kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti :"$port" || true)
    if [ -n "${pids}" ]; then
      echo "Freeing port $port (killing PIDs: ${pids})..."
      kill -9 ${pids} || true
    fi
  fi
}

# Prefer project virtualenv's uvicorn if present
if [ -x ".venv/bin/uvicorn" ]; then
  UVICORN=".venv/bin/uvicorn"
else
  UVICORN="uvicorn"
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Copied .env.example -> .env. Edit .env to set GGML_MODEL_PATH and flags."
fi

# Use bash "allexport" to export sourced variables (safe, ignores comments)
set -o allexport
# shellcheck disable=SC1091
source .env
set +o allexport

echo "Environment loaded."

echo "To start Qdrant with Docker run:"
echo "docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant"

# Proactively kill any lingering uvicorn processes from previous runs
echo "Killing lingering uvicorn processes (if any)..."
pkill -f "uvicorn .*app.main:app" 2>/dev/null || true
pkill -f "uvicorn .*app.tools.metrics_mock:app" 2>/dev/null || true
pkill -f "uvicorn .*app.tools.docs_mock:app" 2>/dev/null || true
sleep 1

echo "Freeing common ports (8000, ${METRICS_MOCK_PORT:-9000}, ${DOCS_MOCK_PORT:-9010})..."
kill_port "${AGENT_PORT:-8000}"
kill_port "${METRICS_MOCK_PORT:-9000}"
kill_port "${DOCS_MOCK_PORT:-9010}"
sleep 1

echo "Starting metrics mock on port ${METRICS_MOCK_PORT:-9000}..."
"${UVICORN}" app.tools.metrics_mock:app --host 0.0.0.0 --port "${METRICS_MOCK_PORT:-9000}" --reload &

echo "Starting docs mock on port ${DOCS_MOCK_PORT:-9010}..."
"${UVICORN}" app.tools.docs_mock:app --host 0.0.0.0 --port "${DOCS_MOCK_PORT:-9010}" --reload &

echo "Starting agent on port ${AGENT_PORT:-8000}..."
"${UVICORN}" app.main:app --host "${AGENT_HOST:-0.0.0.0}" --port "${AGENT_PORT:-8000}" --reload
