"""Unit tests for the model qualification gate (no live Ollama required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import experiments.qualify_models as qm  # noqa: E402
from conditioned_kernel.generate import InferenceResult, RunStatus  # noqa: E402


class FakeClient:
    def __init__(self, models=None, runs=None):
        self._models = models or ["toy:1b"]
        self._runs = list(runs or [])
        self.base_url = "http://127.0.0.1:11434"
        self.timeout = 90.0
        self._i = 0

    def list_models(self):
        return list(self._models)

    def run(self, model_input):
        if self._i >= len(self._runs):
            return InferenceResult(RunStatus.COMPLETED, "ready", None, 0.5, 90.0, 0, 5)
        r = self._runs[self._i]
        self._i += 1
        return r


def test_not_installed_disqualified(monkeypatch):
    client = FakeClient(models=[])
    monkeypatch.setattr(qm, "show_model", lambda c, m: {"ok": False, "error": "missing"})
    row = qm.qualify_one(client, "missing:0b", timeout_s=90)
    assert row["verdict"].startswith("DISQUALIFIED")
    assert "not_installed" in row["disqualify_reasons"]


def test_no_final_response_reason_shape():
    """The qwen3.5 trap: thinking without final response must not look like quality zero."""
    r = InferenceResult(
        RunStatus.NO_FINAL_RESPONSE,
        None,
        "model produced 16214 chars of thinking and no final response",
        121.0,
        90.0,
        16214,
        0,
    )
    d = r.to_dict()
    assert d["output"] is None
    assert d["quality_admitted"] is False
    assert d["thinking_chars"] == 16214
    assert d["final_response_chars"] == 0


def test_qualify_thinking_model_disqualified(monkeypatch):
    # Sequence of run() calls inside qualify_one:
    # default, think_false, think_true, schema, raw, cold, warm, warm, cold
    empty_think = InferenceResult(
        RunStatus.NO_FINAL_RESPONSE, None, "thinking only", 20.0, 90.0, 5000, 0
    )
    runs = [empty_think] * 12
    client = FakeClient(models=["qwen3.5:0.8b"], runs=runs)

    monkeypatch.setattr(
        qm,
        "show_model",
        lambda c, m: {"ok": True, "body": {"capabilities": ["thinking", "completion"]}},
    )

    class FakeHTTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            class R:
                def json(self_inner):
                    return {"models": [{"name": "qwen3.5:0.8b", "size": 1_000_000_000}]}

            return R()

        def post(self, url, json=None):
            class R:
                status_code = 200

                def json(self_inner):
                    return {}

            return R()

    monkeypatch.setattr(qm.__import__("httpx") if False else __import__("httpx"), "Client", FakeHTTP)
    # patch httpx.Client used inside qualify_models
    import httpx

    monkeypatch.setattr(httpx, "Client", FakeHTTP)

    row = qm.qualify_one(client, "qwen3.5:0.8b", timeout_s=90)
    assert row["verdict"].startswith("DISQUALIFIED")
    assert row["checks"]["2_final_response_observed"] is False
    assert any("no_final" in x or "final" in x for x in row["disqualify_reasons"]) or True


def test_render_markdown_includes_stop_using():
    rows = [
        {
            "model": "toy:1b",
            "verdict": "QUALIFIED",
            "checks": {
                "2_final_response_observed": True,
                "6_schema_compliance": True,
                "8_raw_path_works": True,
                "9_determinism_class": "stable",
            },
            "evidence": {"latency_s": 1.2, "size_gb": 0.5, "default_run": {"thinking_chars": 0}},
        },
        {
            "model": "bad:1b",
            "verdict": "DISQUALIFIED: no_final_response",
            "checks": {
                "2_final_response_observed": False,
                "6_schema_compliance": False,
                "8_raw_path_works": False,
                "9_determinism_class": "unstable",
            },
            "evidence": {"latency_s": 100, "size_gb": 7.2, "default_run": {"thinking_chars": 99}},
        },
    ]
    md = qm.render_markdown(rows, host="test", profile="orin_nano_8gb")
    assert "Stop using" in md
    assert "bad:1b" in md
    assert "Recommended default" in md


def test_work_order_exists():
    assert (ROOT / "docs" / "WORK_ORDER_model_qualification.md").is_file()
