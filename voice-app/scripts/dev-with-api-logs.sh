#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -f "$REPO_ROOT/backend/server.py" ]]; then
  printf 'Could not locate repo root from script directory: %s\n' "$SCRIPT_DIR" >&2
  exit 1
fi

LOG_DIR="$REPO_ROOT/.run-logs"
ALL_LOG="$LOG_DIR/dev-all.log"
API_LOG="$LOG_DIR/api-dev.log"
API_BUG_LOG="$LOG_DIR/api-bugs.log"
DEV_PORTS_CONFIG="${DEV_PORTS:-17493 209}"
DEV_PORTS=()

for port in $DEV_PORTS_CONFIG; do
  DEV_PORTS+=("$port")
done

KILL_PIDS=()
KILL_REASONS=()
PROTECTED_PIDS=()

mkdir -p "$LOG_DIR"

started_at="$(date '+%Y-%m-%d %H:%M:%S %z')"
printf 'Log started at %s\n' "$started_at" > "$ALL_LOG"
printf 'API log started at %s\n' "$started_at" > "$API_LOG"
printf 'API bug log started at %s\n' "$started_at" > "$API_BUG_LOG"

log_marker() {
  local message="$1"
  local bug_marker="${2:-0}"

  printf '\n%s\n' "$message"
  printf '\n%s\n' "$message" >> "$ALL_LOG"
  printf '\n%s\n' "$message" >> "$API_LOG"

  if [[ "$bug_marker" == "1" ]]; then
    printf '\n%s\n' "$message" >> "$API_BUG_LOG"
  fi
}

log_paths() {
  printf 'Logs:\n'
  printf '  all:      %s\n' "$ALL_LOG"
  printf '  api:      %s\n' "$API_LOG"
  printf '  api bugs: %s\n' "$API_BUG_LOG"
}

collect_protected_pids() {
  local pid="$$"

  PROTECTED_PIDS=()
  while [[ -n "$pid" && "$pid" =~ ^[0-9]+$ && "$pid" -gt 0 ]]; do
    PROTECTED_PIDS+=("$pid")
    pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d '[:space:]')"
  done

  if [[ -n "${BASHPID:-}" ]]; then
    PROTECTED_PIDS+=("$BASHPID")
  fi
  if [[ -n "${PPID:-}" ]]; then
    PROTECTED_PIDS+=("$PPID")
  fi
}

is_protected_pid() {
  local pid="$1"
  local protected_pid

  if [[ "${#PROTECTED_PIDS[@]}" -eq 0 ]]; then
    return 1
  fi

  for protected_pid in "${PROTECTED_PIDS[@]}"; do
    if [[ "$pid" == "$protected_pid" ]]; then
      return 0
    fi
  done

  return 1
}

queue_pid_for_kill() {
  local pid="$1"
  local reason="$2"
  local existing_pid

  if [[ ! "$pid" =~ ^[0-9]+$ ]] || [[ "$pid" -le 1 ]]; then
    return
  fi
  if is_protected_pid "$pid"; then
    return
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    return
  fi

  if [[ "${#KILL_PIDS[@]}" -gt 0 ]]; then
    for existing_pid in "${KILL_PIDS[@]}"; do
      if [[ "$existing_pid" == "$pid" ]]; then
        return
      fi
    done
  fi

  KILL_PIDS+=("$pid")
  KILL_REASONS+=("$reason")
}

queue_descendants_for_kill() {
  local parent_pid="$1"
  local child_pid

  if ! command -v pgrep >/dev/null 2>&1; then
    return
  fi

  while IFS= read -r child_pid; do
    [[ -n "$child_pid" ]] || continue
    queue_descendants_for_kill "$child_pid"
    queue_pid_for_kill "$child_pid" "child of $parent_pid"
  done < <(pgrep -P "$parent_pid" 2>/dev/null || true)
}

matches_dev_process() {
  local command="$1"

  case "$command" in
    *"scripts/dev-with-api-logs.sh"* \
      | *"dev:api-logs"* \
      | *"python3 -m backend.main"* \
      | *"server.py"* \
      | *"backend/main.py"* \
      | *"vite"* \
      | *"npm run dev"* \
      | *"yarn dev"* \
      | *"bun dev"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

queue_dev_processes_for_kill() {
  local line
  local pid
  local command

  while IFS= read -r line; do
    line="${line#"${line%%[![:space:]]*}"}"
    pid="${line%%[[:space:]]*}"
    command="${line#"$pid"}"
    command="${command#"${command%%[![:space:]]*}"}"

    if matches_dev_process "$command"; then
      queue_descendants_for_kill "$pid"
      queue_pid_for_kill "$pid" "dev process: $command"
    fi
  done < <(ps -axo pid=,command=)
}

queue_port_processes_for_kill() {
  local port
  local pid

  if ! command -v lsof >/dev/null 2>&1; then
    log_marker "lsof not found; skipping port cleanup"
    return
  fi

  if [[ "${#DEV_PORTS[@]}" -eq 0 ]]; then
    return
  fi

  for port in "${DEV_PORTS[@]}"; do
    while IFS= read -r pid; do
      [[ -n "$pid" ]] || continue
      queue_descendants_for_kill "$pid"
      queue_pid_for_kill "$pid" "listening on port $port"
    done < <(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  done
}

wait_for_pids_to_exit() {
  local timeout_seconds="$1"
  local started_at
  local pid
  local alive

  if [[ "${#KILL_PIDS[@]}" -eq 0 ]]; then
    return 0
  fi

  started_at="$(date +%s)"
  while true; do
    alive=0
    for pid in "${KILL_PIDS[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        alive=1
        break
      fi
    done

    if [[ "$alive" -eq 0 ]]; then
      return 0
    fi
    if (( $(date +%s) - started_at >= timeout_seconds )); then
      return 1
    fi

    sleep 1
  done
}

kill_queued_processes() {
  local index
  local pid
  local reason

  if [[ "${#KILL_PIDS[@]}" -eq 0 ]]; then
    log_marker "No other dev environments found"
    return
  fi

  log_marker "Killing ${#KILL_PIDS[@]} existing dev process(es)"
  for index in "${!KILL_PIDS[@]}"; do
    pid="${KILL_PIDS[$index]}"
    reason="${KILL_REASONS[$index]}"
    if kill -0 "$pid" 2>/dev/null; then
      printf '  TERM pid=%s (%s)\n' "$pid" "$reason" | tee -a "$ALL_LOG" "$API_LOG"
      kill "$pid" 2>/dev/null || true
    fi
  done

  if wait_for_pids_to_exit 5; then
    log_marker "Existing dev environments stopped"
    return
  fi

  log_marker "Force killing remaining dev process(es)"
  for pid in "${KILL_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      printf '  KILL pid=%s\n' "$pid" | tee -a "$ALL_LOG" "$API_LOG"
      kill -9 "$pid" 2>/dev/null || true
    fi
  done

  wait_for_pids_to_exit 2 || true
}

kill_other_dev_environments() {
  log_marker "==> Killing other dev environments"

  collect_protected_pids
  KILL_PIDS=()
  KILL_REASONS=()

  queue_dev_processes_for_kill
  queue_port_processes_for_kill
  kill_queued_processes
}

stream_logs() {
  local force_api="$1"

  awk \
    -v all_log="$ALL_LOG" \
    -v api_log="$API_LOG" \
    -v bug_log="$API_BUG_LOG" \
    -v force_api="$force_api" '
      function clean_ansi(value) {
        gsub(/\033\[[0-9;?]*[ -\/]*[@-~]/, "", value)
        return value
      }

      function is_api_line(value) {
        return value ~ /^.*uvicorn/ \
          || value ~ /^.*INFO.*:.*app/ \
          || value ~ /^.*ERROR/ \
          || value ~ /^.*WARNING/ \
          || value ~ /backend/ \
          || value ~ /server.py/ \
          || value ~ /main.py/ \
          || value ~ /voicebox.*starting/ \
          || value ~ /Application startup/ \
          || value ~ /Uvicorn running/
      }

      function is_bug_line(value) {
        value = clean_ansi(value)

        return value ~ /ERROR/ \
          || value ~ /Error:/ \
          || value ~ /Exception/ \
          || value ~ /ModuleNotFoundError/ \
          || value ~ /ImportError/ \
          || value ~ /Failed to start/ \
          || value ~ /Command failed/ \
          || value ~ /[0-9]+:[0-9]+.*ERROR/ \
          || value ~ /Traceback/ \
          || value ~ /No module named/
      }

      {
        print $0
        print $0 >> all_log

        api_related = force_api == "1" || is_api_line($0)
        if (api_related) {
          print $0 >> api_log
        }

        if (api_related && is_bug_line($0)) {
          print $0 >> bug_log
        }

        fflush()
      }
    '
}

check_backend_health() {
  local max_attempts=30
  local attempt=1

  log_marker "==> Checking backend health"

  while [[ $attempt -le $max_attempts ]]; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
      log_marker "✓ Backend is healthy"
      return 0
    fi

    printf "Attempt %d/%d: Backend not responding yet...\n" "$attempt" "$max_attempts"
    sleep 2
    ((attempt++))
  done

  log_marker "✗ Backend failed to respond after $max_attempts attempts" 1
  return 1
}

run_preflight() {
  local label="$1"
  shift

  log_marker "==> $label"

  set +e
  "$@" 2>&1 | stream_logs 1
  local pipe_status=("${PIPESTATUS[@]}")
  local status="${pipe_status[0]}"
  set -e

  if [[ "$status" -ne 0 ]]; then
    log_marker "Preflight failed: $label (exit $status)" 1
    exit "$status"
  fi
}

cd "$REPO_ROOT"

log_paths
kill_other_dev_environments

log_marker "==> Starting dev servers"
printf 'Backend API expected at http://localhost:17493\n'
printf 'Frontend expected at http://localhost:209\n'

# Start backend in background
log_marker "==> Starting backend server"
cd "$REPO_ROOT"

# Check if virtual environment exists and activate it
if [ -d "backend/venv" ]; then
  log_marker "Activating virtual environment"
  source backend/venv/bin/activate
fi

# Start backend with logging
set +e
PYTHONUNBUFFERED=1 python3 -m backend.main --host 127.0.0.1 --port 17493 2>&1 | stream_logs 1 &
BACKEND_PID=$!
set -e

# Give backend time to start
sleep 3

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
  log_marker "✗ Failed to start backend server" 1
  exit 1
fi

log_marker "✓ Backend server started successfully (PID: $BACKEND_PID)"

# Start frontend
log_marker "==> Starting frontend"
cd "$REPO_ROOT/web"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
  log_marker "Installing frontend dependencies..."
  if command -v npm >/dev/null 2>&1; then
    npm install 2>&1 | stream_logs 0
  else
    log_marker "No package manager found. Please install npm." 1
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
  fi
fi

# Start frontend with logging
set +e
npm run dev 2>&1 | stream_logs 0 &
FRONTEND_PID=$!
set -e

cd "$REPO_ROOT"

log_marker "✓ Frontend server started successfully (PID: $FRONTEND_PID)"

# Wait for processes
log_marker "==> All services running. Press Ctrl+C to stop."

wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true

# Cleanup function
cleanup() {
  log_marker "==> Stopping all services..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  log_marker "✓ Services stopped."
  exit 0
}

# Trap termination signals
trap cleanup SIGINT SIGTERM

# Keep script running
while true; do
  sleep 1
done
