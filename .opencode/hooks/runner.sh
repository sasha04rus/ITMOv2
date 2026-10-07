#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(dirname "$(dirname "$(readlink -f "$0")")")
RESULTS_DIR="$ROOT_DIR/hooks/results"
SERVICE_DIR="$(readlink -f "$ROOT_DIR/../practices/practice_04/service/subscriptions")"
EVIDENCE_DIR="$(readlink -f "$ROOT_DIR/../practices/practice_04/evidence")"

mkdir -p "$RESULTS_DIR" "$EVIDENCE_DIR"

# Run minimal checks: python tests if exist; validate MCP tool

RESULT_JSON="$RESULTS_DIR/latest.json"

status="ok"
messages=()

# If there are tests, run them
if compgen -G "$SERVICE_DIR/tests/test_*.py" > /dev/null; then
  # Prefer unittest discovery if pytest unavailable
  if command -v pytest >/dev/null 2>&1; then
    if ! python3 -m pytest -q "$SERVICE_DIR/tests"; then
      status="fail"; messages+=("pytest failed")
    else
      messages+=("pytest passed")
    fi
  else
    if ! python3 -m unittest discover -s "$SERVICE_DIR/tests" -p 'test_*.py'; then
      status="fail"; messages+=("unittest failed")
    else
      messages+=("unittest passed")
    fi
  fi
else
  status="fail"; messages+=("no tests found")
fi

# Probe MCP tool with success and failure
SUCCESS_PAYLOAD='{"id":1,"method":"tool/execute","params":{"name":"validate_subscriber_name","args":{"name":"  Alice  "}}}'
FAIL_PAYLOAD='{"id":2,"method":"tool/execute","params":{"name":"validate_subscriber_name","args":{"name":"   "}}}'

MCP_CMD=(python3 "$ROOT_DIR/../practices/practice_04/.opencode/mcp/validate_subscriber_name/server.py")

success_out=$("${MCP_CMD[@]}" <<< "$SUCCESS_PAYLOAD" | tail -n 1)
fail_out=$("${MCP_CMD[@]}" <<< "$FAIL_PAYLOAD" | tail -n 1)

echo -e "SUCCESS: $success_out\nFAIL: $fail_out" >> "$EVIDENCE_DIR/mcp_calls.log" || true

if [[ "$fail_out" != *"isError\": true"* ]]; then
  status="fail"
  messages+=("MCP failure case not detected")
else
  messages+=("MCP failure detected")
fi

if [[ "$success_out" != *"isError\": false"* || "$success_out" != *"Alice"* ]]; then
  status="fail"
  messages+=("MCP success case failed")
else
  messages+=("MCP success detected")
fi

cat > "$RESULT_JSON" <<JSON
{
  "status": "$status",
  "messages": [$(printf '"%s",' "${messages[@]}" | sed 's/,$//')]
}
JSON

echo "Runner status: $status"

if [[ "$status" != "ok" ]]; then
  exit 1
fi
