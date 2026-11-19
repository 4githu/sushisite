#!/usr/bin/env bash
# Real Svelte/Vite → Aura FastAPI → synthetic isolated SQLite/PDF. No production app or credentials.
set -euo pipefail
app_dir="$(cd "$(dirname "$0")/.." && pwd)"
repo_dir="$(cd "$app_dir/.." && pwd)"
root="$(mktemp -d "$HOME/.hermes/profiles/personalsvelte/cache/scratch/aura-integration-XXXXXXXX")"
api_port=18762
web_port=5188
api_pid=''
web_pid=''
cleanup() {
  status=$?
  if [[ "$status" -ne 0 ]]; then
    echo 'Isolated Aura API log (failure):' >&2
    tail -n 75 "$root/api.log" 2>/dev/null >&2 || true
  fi
  [[ -z "$web_pid" ]] || kill "$web_pid" 2>/dev/null || true
  [[ -z "$api_pid" ]] || kill "$api_pid" 2>/dev/null || true
  wait "$web_pid" "$api_pid" 2>/dev/null || true
  rm -rf -- "$root"
}
trap cleanup EXIT
# Refuse to use someone else's live server. Ports are loopback-only.
for port in "$api_port" "$web_port"; do
  if curl --silent --max-time 1 "http://127.0.0.1:$port/" >/dev/null; then
    echo "Refusing occupied integration port $port" >&2
    exit 1
  fi
done
(
  cd "$repo_dir"
  exec env AURA_INTEGRATION_ROOT="$root" PERSONAL_PROJECT_DB_PATH="$root/test.sqlite" \
    sushi-fast/.venv/bin/python -m uvicorn personal_project.tests.aura_integration_server:app \
    --app-dir sushi-fast --host 127.0.0.1 --port "$api_port"
) >"$root/api.log" 2>&1 &
api_pid=$!
(
  cd "$app_dir"
  exec env PERSONAL_API_PROXY="http://127.0.0.1:$api_port" VITE_SUSHIFASTURL= \
    node_modules/.bin/vite dev --strictPort --host 127.0.0.1 --port "$web_port"
) >"$root/web.log" 2>&1 &
web_pid=$!
for attempt in {1..60}; do
  if curl --fail --silent "http://127.0.0.1:$api_port/auth/isjwt" >/dev/null && \
     curl --fail --silent "http://127.0.0.1:$web_port/personal-project/aura" >/dev/null; then
    break
  fi
  if ! kill -0 "$api_pid" 2>/dev/null || ! kill -0 "$web_pid" 2>/dev/null; then
    echo 'Isolated server exited; see logs below' >&2
    tail -n 40 "$root/api.log" "$root/web.log" >&2
    exit 1
  fi
  sleep 1
done
cd "$app_dir"
AURA_TEST_API_URL="http://127.0.0.1:$api_port" \
PLAYWRIGHT_BASE_URL="http://127.0.0.1:$web_port" \
  npx playwright test tests/aura-live-contract.e2e.ts --workers=1 --reporter=line
