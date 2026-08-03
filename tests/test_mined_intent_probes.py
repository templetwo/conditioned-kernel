"""Mined intent probes — regression lane built from real typed turns.

Loads tests/fixtures/mined_intent_probes.json. Unlike the hand-authored lane in
test_intent_probes.py, every line here is verbatim from a real session, so the
set covers phrasings nobody thought to invent at the desk.

Two assertions:
  * 'locked' probes are currently correct and must not regress.
  * the 'known_gap' count is ratcheted — probes the classifier still gets wrong
    are recorded rather than hidden, and the count may only shrink.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conditioned_kernel.context_field import detect_intents

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mined_intent_probes.json"


def _load() -> dict:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert data.get("schema") == "mined_intent_probes.v1"
    assert data.get("probes"), "mined_intent_probes.json must list at least one probe"
    return data


_DATA = _load()
_LOCKED = [p for p in _DATA["probes"] if p.get("status") == "locked"]


@pytest.mark.parametrize(
    "probe",
    _LOCKED,
    ids=lambda p: str(p.get("id") or p.get("line") or "probe"),
)
def test_mined_probe_locked(probe: dict) -> None:
    line = str(probe["line"])
    intents = detect_intents(line)
    for need in probe.get("expected_include") or []:
        assert need in intents, (
            f"{probe.get('id')} ({probe.get('bucket')}): {line!r} "
            f"lost {need!r}; got {sorted(intents)}"
        )
    for ban in probe.get("expected_exclude") or []:
        assert ban not in intents, (
            f"{probe.get('id')} ({probe.get('bucket')}): {line!r} "
            f"regained {ban!r}; got {sorted(intents)}"
        )


def test_known_gap_count_only_shrinks() -> None:
    """The recorded residual is a ceiling, not a target. Fixing gaps lowers it."""
    ceiling = int(_DATA["known_gap_ceiling"])
    actual = 0
    for probe in _DATA["probes"]:
        intents = detect_intents(str(probe["line"]))
        ok = all(n in intents for n in probe.get("expected_include") or []) and all(
            b not in intents for b in probe.get("expected_exclude") or []
        )
        if not ok:
            actual += 1
    assert actual <= ceiling, (
        f"mined probe failures grew from {ceiling} to {actual}; "
        "a change made real-turn routing worse"
    )
