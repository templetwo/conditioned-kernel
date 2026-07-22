#!/usr/bin/env bash
# Poll T2Helix chronicle for Claude/Opus seat replies on the continuity board.
# Each matching NEW entry prints one line (monitor → chat notification).
# Also surfaces blocked/fail so problems are not silent.
set -euo pipefail

DB="${T2HELIX_DATA_DIR:-$HOME/.claude/plugins/data/t2helix-templetwo-t2helix}/chronicle.db"
STATE="${CK_CLAUDE_MONITOR_STATE:-$HOME/.cache/ck_claude_seat_monitor.highwater}"
INTERVAL="${CK_CLAUDE_MONITOR_INTERVAL:-30}"

mkdir -p "$(dirname "$STATE")"
if [[ ! -f "$STATE" ]]; then
  # Start from current max so we only report NEW entries after arming
  MAX=$(sqlite3 "$DB" "SELECT COALESCE(MAX(id),0) FROM insights;" 2>/dev/null || echo 0)
  echo "$MAX" > "$STATE"
  echo "CK_CLAUDE_MONITOR armed highwater=$MAX db=$DB interval=${INTERVAL}s"
fi

# Match Claude/Opus coordination; exclude pure Grok self-echo unless blocked/fail
# domain often: conditioned-kernel,coordination
SQL_TEMPLATE=$(cat <<'SQL'
SELECT id || ' | ' || COALESCE(domain,'') || ' | ' ||
       REPLACE(REPLACE(SUBSTR(content,1,180), CHAR(10), ' '), CHAR(13), ' ')
FROM insights
WHERE id > %s
  AND (
    lower(COALESCE(domain,'')) LIKE '%%coordination%%'
    OR lower(COALESCE(domain,'')) LIKE '%%conditioned-kernel%%'
    OR lower(content) LIKE '%%seat-board%%'
    OR lower(content) LIKE '%%seat board%%'
    OR lower(content) LIKE '%%opus seat%%'
    OR lower(content) LIKE '%%claude%%'
    OR lower(content) LIKE '%%continuity%%'
    OR lower(content) LIKE '%%blocked%%'
    OR lower(content) LIKE '%%fail%%'
  )
  AND lower(content) NOT LIKE '%%seat-board reply (grok%%'
ORDER BY id ASC
LIMIT 20;
SQL
)

while true; do
  HW=$(cat "$STATE" 2>/dev/null || echo 0)
  if [[ ! -f "$DB" ]]; then
    echo "CK_CLAUDE_MONITOR warn: chronicle missing at $DB"
    sleep "$INTERVAL"
    continue
  fi
  # shellcheck disable=SC2059
  SQL=$(printf "$SQL_TEMPLATE" "$HW")
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    id="${line%% |*}"
    echo "CLAUDE_SEAT id=$line"
    if [[ "$id" =~ ^[0-9]+$ ]] && (( id > HW )); then
      echo "$id" > "$STATE"
      HW=$id
    fi
  done < <(sqlite3 "$DB" "$SQL" 2>/dev/null || true)
  sleep "$INTERVAL"
done
