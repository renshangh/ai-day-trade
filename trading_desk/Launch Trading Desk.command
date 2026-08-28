#!/bin/bash
# Double-click this file in Finder to start the trading desk dashboard and
# open it in your browser. Close this window (or press Ctrl+C) to stop the
# server -- it is not left running in the background after that.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

pause_and_exit() {
  echo
  read -n 1 -s -r -p "Press any key to close this window..."
  exit "${1:-1}"
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Install Python 3, then try again."
  pause_and_exit 1
fi

is_healthy() {
  curl -fsS "http://127.0.0.1:$1/api/health" 2>/dev/null | grep -q '"ok": *true'
}

# One fixed port per branch, matching BRANCH_PORTS in server.py. Scanning a range
# for the first free port is what made the dashboard turn up somewhere different
# most times it started -- and worse, let a stale server from another branch keep
# answering on the port you expected. The branch owns its port or nothing does.
BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
case "$BRANCH" in
  main) PORT=8800 ;;
  *)    PORT=8799 ;;   # dev and every topic branch headed for it
esac
echo "Branch '$BRANCH' uses port $PORT."

# Already running and healthy on this branch's port? Just open it.
if is_healthy "$PORT"; then
  echo "Trading desk is already running on port $PORT -- opening it."
  open "http://127.0.0.1:$PORT"
  exit 0
fi

# Occupied but not answering /api/health: almost always a stale server from an
# earlier session, possibly on different code. Say so instead of sidestepping it.
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is in use by something that is not a healthy trading desk."
  echo "It is probably an older server still running. Find and stop it with:"
  echo "  lsof -nP -iTCP:$PORT -sTCP:LISTEN"
  echo "  kill <PID>"
  pause_and_exit 1
fi

echo "Starting trading desk on port $PORT..."
LOG_FILE="$(mktemp -t trading-desk-log)"
python3 "$REPO_ROOT/trading_desk/server.py" --port "$PORT" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null
  wait "$SERVER_PID" 2>/dev/null
  rm -f "$LOG_FILE"
}
trap cleanup EXIT INT TERM HUP

READY=0
for _ in $(seq 1 40); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Server exited before it became ready. Log output:"
    echo "----------------------------------------------------"
    cat "$LOG_FILE"
    pause_and_exit 1
  fi
  if is_healthy "$PORT"; then
    READY=1
    break
  fi
  sleep 0.5
done

if [ "$READY" -ne 1 ]; then
  echo "Server did not become healthy in time. Log so far:"
  echo "----------------------------------------------------"
  cat "$LOG_FILE"
  pause_and_exit 1
fi

echo "Ready. Opening http://127.0.0.1:$PORT"
open "http://127.0.0.1:$PORT"

echo
echo "Trading desk is running. Close this window or press Ctrl+C to stop it."
echo "------------------------------------------------------------------------"
tail -f "$LOG_FILE" &
TAIL_PID=$!
trap 'kill "$TAIL_PID" "$SERVER_PID" 2>/dev/null; rm -f "$LOG_FILE"' EXIT INT TERM HUP
wait "$SERVER_PID"
