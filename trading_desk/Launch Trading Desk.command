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

health_json() {
  curl -fsS "http://127.0.0.1:$1/api/health" 2>/dev/null
}

# The branch of THIS checkout, read by the same code the server uses, so the
# launcher and the server can never disagree about which branch they are on.
running_branch_self() {
  python3 -c "import sys; sys.path.insert(0, '$REPO_ROOT/trading_desk'); \
import server; print(server.current_branch() or '')" 2>/dev/null
}

# The branch a running server was started from, per its own /api/health.
running_branch() {
  health_json "$1" | sed -n 's/.*"branch": *"\([^"]*\)".*/\1/p' | head -1
}

# One fixed port per branch. Scanning a range for the first free port is what made
# the dashboard turn up somewhere different most times it started -- and worse,
# let a stale server keep answering on the port you expected.
#
# The port comes from server.py rather than being restated here, so there is one
# source of truth. Asking git directly would be a second branch-detection
# mechanism that could disagree with the server's (notably when git is not on
# PATH, which is precisely why server.py reads .git/HEAD instead of shelling out).
PORT="$(python3 "$REPO_ROOT/trading_desk/server.py" --print-port 2>/dev/null)"
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
  echo "Could not determine the port for this branch. Is python3 working?"
  pause_and_exit 1
fi
BRANCH="$(running_branch_self)"
echo "Branch '${BRANCH:-unknown}' uses port $PORT."

# A server already on this port may be the one you want -- or an old one from a
# previous session still serving stale code, which answers /api/health perfectly
# well. That is the failure this whole scheme exists to prevent, so compare what
# it reports against the branch actually checked out rather than trusting "alive".
RUNNING="$(running_branch "$PORT")"
if [ -n "$RUNNING" ]; then
  if [ "$RUNNING" = "$BRANCH" ]; then
    echo "Trading desk is already running on port $PORT -- opening it."
    open "http://127.0.0.1:$PORT"
    exit 0
  fi
  echo "A trading desk is already on port $PORT, but it was started from branch"
  echo "'$RUNNING' while this checkout is on '${BRANCH:-unknown}'. It is serving"
  echo "different code than you are looking at. Stop it first:"
  echo "  lsof -nP -iTCP:$PORT -sTCP:LISTEN"
  echo "  kill <PID>"
  pause_and_exit 1
fi

# Occupied but not answering /api/health at all: something else owns the port.
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is in use by something that is not a trading desk."
  echo "Find and stop it with:"
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
