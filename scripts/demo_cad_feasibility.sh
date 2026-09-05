#!/usr/bin/env bash
# Submit end-to-end DXF to BOM & ControlNet feasibility job
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
DXF_PATH="${1:-simple_room.dxf}"
PRESET="${2:-Luxury Minimal}"
STYLE="${3:-luxury-minimal}"
DRY_RUN="${4:-true}"
INPUT_TYPE="${5:-interior}"

echo "========================================================"
echo "  control-bim-pf-engine API Demo: End-to-End CAD Pre-Feasibility"
echo "========================================================"
echo "API URL:      $API_URL"
echo "DXF File:     $DXF_PATH"
echo "BOM Preset:   $PRESET"
echo "Visual Style: $STYLE"
echo "Input Type:   $INPUT_TYPE"
echo "Dry Run:      $DRY_RUN"
echo ""

PAYLOAD=$(cat <<EOF
{
  "dxfPath": "$DXF_PATH",
  "preset": "$PRESET",
  "targetStyle": "$STYLE",
  "inputType": "$INPUT_TYPE",
  "dryRun": $DRY_RUN
}
EOF
)

echo "Submitting CAD feasibility job..."
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/cad/feasibility" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "Response: $RESPONSE"
RUN_ID=$(echo "$RESPONSE" | grep -o '"runId":"[^"]*' | cut -d'"' -f4)

if [ -z "$RUN_ID" ]; then
  echo "Error: Failed to obtain runId."
  exit 1
fi

echo "Job queued with ID: $RUN_ID. Polling for completion..."
while true; do
  STATUS_RESP=$(curl -s "$API_URL/api/v1/status/$RUN_ID")
  STATUS=$(echo "$STATUS_RESP" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
  PROGRESS=$(echo "$STATUS_RESP" | grep -o '"progress":[0-9.]*' | cut -d':' -f2 || echo "0.0")

  echo "[$(date +'%T')] Status: $STATUS (Progress: $PROGRESS)"

  if [ "$STATUS" = "done" ]; then
    echo ""
    echo "Pre-feasibility job completed!"
    echo "$STATUS_RESP" | python3 -m json.tool || echo "$STATUS_RESP"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "Pre-feasibility job failed!"
    echo "$STATUS_RESP" | python3 -m json.tool || echo "$STATUS_RESP"
    exit 1
  fi
  sleep 2
done
