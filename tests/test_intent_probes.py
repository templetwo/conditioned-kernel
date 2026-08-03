"""Held-out / adjacent intent probes — adversarial lane for detect_intents.

Loads tests/fixtures/intent_probes.json. Each probe asserts must_include /
must_exclude membership only. This is the lane Fable asked for: intended-case
green is not enough; adjacent system reports and real session lines must hold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conditioned_kernel.context_field import detect_intents

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "intent_probes.json"


def _load_probes() -> list[dict]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert data.get("schema") == "ck.intent_probes.v1"
    probes = data.get("probes") or []
    assert probes, "intent_probes.json must list at least one probe"
    return probes


@pytest.mark.parametrize(
    "probe",
    _load_probes(),
    ids=lambda p: str(p.get("id") or p.get("line") or "probe"),
)
def test_intent_probe(probe: dict) -> None:
    line = str(probe["line"])
    intents = detect_intents(line)
    for need in probe.get("must_include") or []:
        assert need in intents, (
            f"probe {probe.get('id')}: {line!r} missing {need!r}; got {sorted(intents)}"
        )
    for ban in probe.get("must_exclude") or []:
        assert ban not in intents, (
            f"probe {probe.get('id')}: {line!r} unexpectedly has {ban!r}; got {sorted(intents)}"
        )
