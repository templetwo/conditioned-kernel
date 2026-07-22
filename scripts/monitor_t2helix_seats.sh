#!/usr/bin/env bash
# T2Helix chronicle poller — Claude/Opus seat board + coordination + failures.
set -euo pipefail
DB="${T2HELIX_DATA_DIR:-$HOME/.claude/plugins/data/t2helix-templetwo-t2helix}/chronicle.db"
STATE="${CK_T2HELIX_MONITOR_STATE:-$HOME/.cache/ck_t2helix_seat_monitor.highwater}"
INTERVAL="${CK_T2HELIX_MONITOR_INTERVAL:-30}"
mkdir -p "$(dirname "$STATE")"
if [[ ! -f "$STATE" ]]; then
  sqlite3 "$DB" "SELECT COALESCE(MAX(id),0) FROM insights;" > "$STATE"
  echo "T2HELIX_MONITOR armed highwater=$(cat "$STATE") db=$DB every ${INTERVAL}s"
fi
while true; do
  HW=$(cat "$STATE")
  if [[ ! -f "$DB" ]]; then
    echo "T2HELIX_MONITOR error: missing $DB"
    sleep "$INTERVAL"; continue
  fi
  sqlite3 "$DB" "
SELECT printf('T2HELIX id=%s domain=%s | %s',
  id,
  COALESCE(domain,''),
  REPLACE(REPLACE(SUBSTR(content,1,220), CHAR(10), ' '), CHAR(13), ' ')
)
FROM insights
WHERE id > ${HW}
  AND lower(COALESCE(domain,'')) NOT LIKE '%session-action%'
  AND lower(COALESCE(domain,'')) NOT LIKE '%session-synthesis%'
  AND lower(COALESCE(domain,'')) NOT LIKE '%compass%'
  AND (
    lower(COALESCE(domain,'')) LIKE '%coordination%'
    OR lower(COALESCE(domain,'')) LIKE '%seat-board%'
    OR lower(COALESCE(domain,'')) LIKE '%conditioned-kernel%'
  )
  AND (
    lower(content) LIKE '%seat-board%'
    OR lower(content) LIKE '%opus seat%'
    OR lower(content) LIKE '%claude%'
    OR lower(content) LIKE '%freeze%'
    OR lower(content) LIKE '%thaw%'
    OR lower(content) LIKE '%for the grok seat%'
    OR lower(content) LIKE '%orchestrator%'
    OR lower(content) LIKE '%blocked%'
    OR lower(content) LIKE '%fail%'
    OR lower(content) LIKE '%m1%'
    OR lower(content) LIKE '%m2%'
    OR lower(content) LIKE '%continuity%'
  )
  AND lower(content) NOT LIKE '%seat-board reply (grok%'
ORDER BY id ASC
LIMIT 25;
" 2>/dev/null | while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    echo "$line"
    # extract id=NNNN
    id=$(echo "$line" | sed -n 's/^T2HELIX id=\([0-9]*\).*/\1/p')
    if [[ -n "$id" ]] && [[ "$id" =~ ^[0-9]+$ ]] && (( id > HW )); then
      echo "$id" > "$STATE"
      HW=$id
    fi
  done
  sleep "$INTERVAL"
done
