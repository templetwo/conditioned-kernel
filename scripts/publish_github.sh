#!/usr/bin/env bash
# Publish Conditioned Kernel to github.com/templetwo/conditioned-kernel
# Uses the GLOBAL git credential helper (osxkeychain) — not the stale gh token store.
set -euo pipefail

OWNER="${CK_GITHUB_OWNER:-templetwo}"
REPO="${CK_GITHUB_REPO:-conditioned-kernel}"
DESC="${CK_GITHUB_DESC:-Edge-first substrate-conditioned generation: model as replaceable kernel (Jetson Orin Nano class)}"
VISIBILITY="${CK_GITHUB_VISIBILITY:-public}"  # public|private

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Conditioned Kernel publish =="
echo "repo: ${OWNER}/${REPO} (${VISIBILITY})"
echo "path: $ROOT"

# 1) Pull PAT/password from global git credential helper
CREDS="$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null || true)"
USER="$(printf '%s\n' "$CREDS" | awk -F= '/^username=/{print $2; exit}')"
TOKEN="$(printf '%s\n' "$CREDS" | awk -F= '/^password=/{print $2; exit}')"

if [[ -z "${TOKEN}" ]]; then
  echo "error: no github.com credentials from git credential helper (osxkeychain)." >&2
  echo "fix: gh auth login   OR   store a PAT via: git credential approve" >&2
  exit 1
fi

echo "credential helper: username=${USER:-'(none)'} token=present (len=${#TOKEN})"

# 2) Sync gh CLI to the same global token (fixes stale ~/.config/gh token)
printf '%s\n' "$TOKEN" | gh auth login --hostname github.com --with-token
gh auth status
LOGIN="$(gh api user -q .login)"
echo "authenticated as: $LOGIN"

# Prefer owner matching login if OWNER was default and differs
if [[ "$OWNER" == "templetwo" && -n "$LOGIN" && "$LOGIN" != "templetwo" ]]; then
  echo "note: gh login is '$LOGIN' (not templetwo). Creating under $LOGIN unless CK_GITHUB_OWNER is set."
  # Keep templetwo if it's an org the user can admin — try as requested first
fi

# 3) Create repo if missing, then push
if gh repo view "${OWNER}/${REPO}" >/dev/null 2>&1; then
  echo "remote repo exists: ${OWNER}/${REPO}"
else
  echo "creating ${OWNER}/${REPO}…"
  gh repo create "${OWNER}/${REPO}" \
    --"${VISIBILITY}" \
    --description "$DESC" \
    --disable-wiki \
    --source . \
    --remote origin \
    --push
  echo "created + pushed."
  gh repo view "${OWNER}/${REPO}" --web 2>/dev/null || true
  echo "URL: https://github.com/${OWNER}/${REPO}"
  exit 0
fi

# Exists: ensure origin and push
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/${OWNER}/${REPO}.git"
else
  git remote add origin "https://github.com/${OWNER}/${REPO}.git"
fi

git push -u origin main
echo "pushed main → https://github.com/${OWNER}/${REPO}"
gh repo view "${OWNER}/${REPO}" --json url -q .url
