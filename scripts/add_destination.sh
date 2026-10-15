#!/usr/bin/env bash
# Register an OpenTelemetry destination for the Claude API with the Admin API.
# Works with any OTLP/HTTP backend reachable over public HTTPS on port 443.
#
#   ANTHROPIC_ADMIN_KEY=sk-ant-admin... \
#   OTLP_ENDPOINT=https://ingestion.eu.bronto.io \
#   OTLP_HEADER_NAME=x-bronto-api-key OTLP_HEADER_VALUE=... \
#   CONTENT_MODE=content ./scripts/add_destination.sh
#
# OTLP_ENDPOINT is the base URL: the Claude API appends /v1/traces itself.
set -euo pipefail
: "${ANTHROPIC_ADMIN_KEY:?an Admin API key (sk-ant-admin...) is required}"
: "${OTLP_ENDPOINT:?}" "${OTLP_HEADER_NAME:?}" "${OTLP_HEADER_VALUE:?}"
CONTENT_MODE="${CONTENT_MODE:-metadata_only}"   # or: content

body=$(python3 -c 'import json,os; print(json.dumps({
  "endpoint_url": os.environ["OTLP_ENDPOINT"].rstrip("/"),
  "headers": {os.environ["OTLP_HEADER_NAME"]: os.environ["OTLP_HEADER_VALUE"]},
  "traces": {"content_mode": os.environ.get("CONTENT_MODE", "metadata_only")},
  "workspaces": {"type": "all"}}))')

curl --fail-with-body -sS "https://api.anthropic.com/v1/organizations/telemetry_destinations" \
  -H "x-api-key: $ANTHROPIC_ADMIN_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: telemetry-destinations-2026-08-11" \
  -H "content-type: application/json" \
  -d "$body"
echo
