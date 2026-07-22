"""The environment block must be recorded, and must never break a run."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_matrix import collect_environment  # noqa: E402

REQUIRED = {
    "host_machine",
    "host_system",
    "host_release",
    "python",
    "ollama_version",
    "model_digest",
    "model_bytes",
    "model_quantization",
}


def test_environment_block_has_required_keys():
    env = collect_environment("qwen2.5:0.5b")
    assert REQUIRED.issubset(env.keys())
    assert env["host_machine"] and env["host_system"]


def test_environment_probe_never_raises_when_ollama_is_down(monkeypatch):
    """Metadata collection is best-effort: a dead runtime must not fail the run."""
    import run_matrix

    monkeypatch.setattr(run_matrix, "DEFAULT_BASE_URL", "http://127.0.0.1:1")
    env = collect_environment("qwen2.5:0.5b")
    assert REQUIRED.issubset(env.keys())
    assert env["ollama_version"] is None
    assert "probe_error" in env
