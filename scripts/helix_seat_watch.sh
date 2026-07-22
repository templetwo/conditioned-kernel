#!/usr/bin/env bash
# T2Helix chronicle poller — PRIMARY: tag SEAT-BOARD; SECONDARY: coordination domain.
# Claude/Opus taught us domain strings drift; tags do not (when used).
set -euo pipefail

DB="${T2HELIX_DATA_DIR:-$HOME/.claude/plugins/data/t2helix-templetwo-t2helix}/chronicle.db"
STATE="${CK_T2HELIX_MONITOR_STATE:-$HOME/.cache/ck_t2helix_seat_monitor.highwater}"
INTERVAL="${CK_T2HELIX_MONITOR_INTERVAL:-20}"

mkdir -p "$(dirname "$STATE")"
if [[ ! -f "$STATE" ]]; then
  sqlite3 "$DB" "SELECT COALESCE(MAX(id),0) FROM insights;" > "$STATE"
  echo "T2HELIX_WATCH armed highwater=$(cat "$STATE") interval=${INTERVAL}s (tag SEAT-BOARD first)"
fi

while true; do
  HW=$(cat "$STATE")
  if [[ ! -f "$DB" ]]; then
    echo "T2HELIX_WATCH error: missing chronicle at $DB"
    sleep "$INTERVAL"
    continue
  fi
  # Tag-first poll (json array or plain substring). Also catch HALT/grok-actionable.
  sqlite3 "$DB" "
SELECT printf('T2HELIX id=%s domain=%s tags=%s | %s',
  id,
  COALESCE(domain,''),
  COALESCE(tags,''),
  REPLACE(REPLACE(SUBSTR(content,1,240), CHAR(10), ' '), CHAR(13), ' ')
)
FROM insights
WHERE id > ${HW}
  AND lower(COALESCE(domain,'')) NOT LIKE '%session-action%'
  AND lower(COALESCE(domain,'')) NOT LIKE '%session-synthesis%'
  AND (
    lower(COALESCE(tags,'')) LIKE '%seat-board%'
    OR lower(COALESCE(domain,'')) LIKE '%seat-board%'
    OR (
      lower(COALESCE(domain,'')) LIKE '%coordination%'
      AND (
        lower(content) LIKE '%seat-board%'
        OR lower(content) LIKE '%opus%'
        OR lower(content) LIKE '%halt%'
        OR lower(content) LIKE '%freeze%'
        OR lower(content) LIKE '%thaw%'
        OR lower(content) LIKE '%for the grok%'
        OR lower(content) LIKE '%work order%'
      )
    )
    OR lower(COALESCE(tags,'')) LIKE '%grok-actionable%'
  )
  AND lower(content) NOT LIKE '%seat-board — heartbeat (grok%'
  AND lower(content) NOT LIKE '%seat board — heartbeat (grok%'
  AND lower(content) NOT LIKE '%seat-board reply (grok%'
ORDER BY id ASC
LIMIT 30;
" 2>/dev/null | while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    echo "$line"
    id=$(printf '%s' "$line" | sed -n 's/^T2HELIX id=\([0-9]*\).*/\1/p')
    if [[ -n "$id" && "$id" =~ ^[0-9]+$ ]] && (( id > HW )); then
      echo "$id" > "$STATE"
      HW=$id
    fi
  done
  sleep "$INTERVAL"
done
