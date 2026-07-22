#!/usr/bin/env bash
# Poll T2Helix chronicle for Claude/Opus seat replies on the continuity board.
# Each matching NEW entry prints one line (for log tail / chat monitors).
# Surfaces blocked/fail on the coordination domain so problems are not silent.
set -euo pipefail

DB="${T2HELIX_DATA_DIR:-$HOME/.claude/plugins/data/t2helix-templetwo-t2helix}/chronicle.db"
STATE="${CK_CLAUDE_MONITOR_STATE:-$HOME/.cache/ck_claude_seat_monitor.highwater}"
INTERVAL="${CK_CLAUDE_MONITOR_INTERVAL:-30}"
LOG="${CK_CLAUDE_MONITOR_LOG:-$HOME/.cache/ck_claude_seat_monitor.log}"

mkdir -p "$(dirname "$STATE")" "$(dirname "$LOG")"
if [[ ! -f "$STATE" ]]; then
  MAX=$(sqlite3 "$DB" "SELECT COALESCE(MAX(id),0) FROM insights;" 2>/dev/null || echo 0)
  echo "$MAX" > "$STATE"
  echo "CK_CLAUDE_MONITOR armed highwater=$MAX db=$DB interval=${INTERVAL}s" | tee -a "$LOG"
fi

# Prefer coordination domain + seat-board / opus language.
# Exclude hook telemetry (session-action) and Grok's own seat-board replies.
while true; do
  HW=$(cat "$STATE" 2>/dev/null || echo 0)
  if [[ ! -f "$DB" ]]; then
    echo "CK_CLAUDE_MONITOR warn: chronicle missing at $DB" | tee -a "$LOG"
    sleep "$INTERVAL"
    continue
  fi
  SQL=$(cat <<SQL
SELECT id || ' | ' || COALESCE(domain,'') || ' | ' ||
       REPLACE(REPLACE(SUBSTR(content,1,200), CHAR(10), ' '), CHAR(13), ' ')
FROM insights
WHERE id > ${HW}
  AND lower(COALESCE(domain,'')) NOT LIKE '%session-action%'
  AND lower(COALESCE(domain,'')) NOT LIKE '%session-synthesis%'
  AND (
    (
      lower(COALESCE(domain,'')) LIKE '%coordination%'
      AND (
        lower(content) LIKE '%seat-board%'
        OR lower(content) LIKE '%seat board%'
        OR lower(content) LIKE '%opus seat%'
        OR lower(content) LIKE '%claude%'
        OR lower(content) LIKE '%opus%'
        OR lower(content) LIKE '%for the grok seat%'
        OR lower(content) LIKE '%hand%'
        OR lower(content) LIKE '%blocked%'
        OR lower(content) LIKE '%fail%'
        OR lower(content) LIKE '%g1%'
        OR lower(content) LIKE '%g2%'
        OR lower(content) LIKE '%orchestrator%'
        OR lower(content) LIKE '%continuity%'
      )
    )
    OR (
      lower(content) LIKE '%seat-board%'
      AND lower(content) LIKE '%opus%'
    )
  )
  AND lower(content) NOT LIKE '%seat-board reply (grok%'
  AND lower(content) NOT LIKE '%seat-board reply (grok / corpus%'
ORDER BY id ASC
LIMIT 20;
SQL
)
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    id="${line%% |*}"
    msg="CLAUDE_SEAT id=$line"
    echo "$msg" | tee -a "$LOG"
    if [[ "$id" =~ ^[0-9]+$ ]] && (( id > HW )); then
      echo "$id" > "$STATE"
      HW=$id
    fi
  done < <(sqlite3 "$DB" "$SQL" 2>/dev/null || true)
  sleep "$INTERVAL"
done
