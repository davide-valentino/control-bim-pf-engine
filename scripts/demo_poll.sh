#!/usr/bin/env bash
# Poll an existing runId until finished or print current status
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
RUN_ID="${1:-}"

if [ -z "$RUN_ID" ]; then
  echo "Usage: ./scripts/demo_poll.sh <runId>"
  exit 1
fi

echo "Querying status for runId: $RUN_ID from $API_URL..."
STATUS_RESP=$(curl -s "$API_URL/api/v1/status/$RUN_ID")
echo "$STATUS_RESP" | python3 -m json.tool || echo "$STATUS_RESP"
