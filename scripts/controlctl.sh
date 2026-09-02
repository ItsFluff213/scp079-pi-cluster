#!/usr/bin/env bash
set -euo pipefail

URL="${CONTROL_URL:-http://127.0.0.1:8090}"
TOKEN="${CONTROL_TOKEN:-}"

if [[ $# -ne 2 ]]; then
  echo "Usage: CONTROL_TOKEN=... $0 <dashboard|scp079|so100|coding|swarm> <start|stop|restart|status>" >&2
  exit 2
fi

SERVICE="$1"
ACTION="$2"
if [[ -n "$TOKEN" ]]; then
  curl --fail-with-body -sS -X POST -H "Authorization: Bearer ${TOKEN}" \
    "${URL}/api/services/${SERVICE}/${ACTION}"
else
  curl --fail-with-body -sS -X POST "${URL}/api/services/${SERVICE}/${ACTION}"
fi
echo
