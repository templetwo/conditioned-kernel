#!/usr/bin/env bash
# Jetson Orin Nano 8GB bootstrap for Conditioned Kernel.
# Run on the device (ARM64 Linux). Safe to re-run.
set -euo pipefail

echo "== Conditioned Kernel · Jetson bootstrap =="
echo "arch: $(uname -m)"
echo "host: $(hostname 2>/dev/null || true)"

if [[ "$(uname -m)" != "aarch64" && "$(uname -m)" != "arm64" ]]; then
  echo "warn: this script is intended for Jetson aarch64 (continuing anyway)"
fi

# Ollama
if ! command -v ollama >/dev/null 2>&1; then
  echo "installing Ollama (ARM64 Linux path)…"
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "ollama: $(command -v ollama)"
fi

# Primary edge model only — one at a time
MODEL="${CK_MODEL:-qwen2.5:0.5b}"
echo "pulling single model: $MODEL"
ollama pull "$MODEL"

# Python env
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

echo "edge self-check:"
ck edge --profile orin_nano_8gb
ck status --profile orin_nano_8gb
echo "smoke (live):"
ck smoke --profile orin_nano_8gb --model "$MODEL" || true

echo "done. Prefer: ck --profile orin_nano_8gb ask '…'"
echo "Do not load a second model while measuring RSS."
