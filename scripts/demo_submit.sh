#!/usr/bin/env bash
# Submit a case to the control-bim-pf-engine API and poll status to completion
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
CASE_ID="${1:-interior-demo-001}"
INPUT_TYPE="${2:-interior}"
STYLE="${3:-tropical-boutique}"
DRY_RUN="${4:-false}"

echo "========================================================"
echo "  control-bim-pf-engine API Demo Client: Submit & Poll"
echo "========================================================"
echo "Target API:   $API_URL"
echo "Case ID:      $CASE_ID"
echo "Input Type:   $INPUT_TYPE"
echo "Target Style: $STYLE"
echo "Dry Run:      $DRY_RUN"
echo ""

# 1. Submit Case
PAYLOAD=$(cat <<EOF
{
  "caseId": "$CASE_ID",
  "inputType": "$INPUT_TYPE",
  "targetStyle": "$STYLE",
  "localImagePath": "tests/fixtures/sample_${INPUT_TYPE}.png",
  "runsPerCase": 1,
  "warmup": false,
  "dryRun": $DRY_RUN
}
EOF
)

echo "Submitting case to POST $API_URL/api/v1/submit..."
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/submit" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "Response: $RESPONSE"
RUN_ID=$(echo "$RESPONSE" | grep -o '"runId":"[^"]*' | cut -d'"' -f4)

if [ -z "$RUN_ID" ]; then
  echo "Error: Failed to obtain runId from API response."
  exit 1
fi

echo ""
echo "-> Job Queued! runId: $RUN_ID"
echo "Polling status at GET $API_URL/api/v1/status/$RUN_ID..."
echo ""

# 2. Poll Status
while true; do
  STATUS_RESP=$(curl -s "$API_URL/api/v1/status/$RUN_ID")
  STATUS=$(echo "$STATUS_RESP" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
  PROGRESS=$(echo "$STATUS_RESP" | grep -o '"progress":[0-9.]*' | cut -d':' -f2 || echo "0.0")

  echo "[$(date +'%T')] Status: $STATUS (Progress: $PROGRESS)"

  if [ "$STATUS" = "done" ]; then
    echo ""
    echo "========================================================"
    echo "  Job Completed Successfully!"
    echo "========================================================"
    echo "$STATUS_RESP" | python3 -m json.tool || echo "$STATUS_RESP"
    echo ""
    echo "Download artifacts ZIP at:"
    echo "  $API_URL/api/v1/artifacts/$RUN_ID?download=zip"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo ""
    echo "========================================================"
    echo "  Job Failed!"
    echo "========================================================"
    echo "$STATUS_RESP" | python3 -m json.tool || echo "$STATUS_RESP"
    exit 1
  fi

  sleep 2
done
