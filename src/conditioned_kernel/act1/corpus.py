"""Frozen 8-case ACT-1 corpus from real Run 01 / CK shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CaseClass = Literal["executable", "semantic_residual"]


@dataclass(frozen=True)
class Act1Case:
    id: str
    title: str
    case_class: CaseClass
    prompt: str
    # For executable cases: expected gate result and metadata for the gate
    gate_kind: str | None = None
    gate_payload: dict[str, Any] = field(default_factory=dict)
    # Human-readable notes
    notes: str = ""


def default_corpus() -> list[Act1Case]:
    """Eight real-shaped cases. Executable truth where the protocol requires it."""
    return [
        Act1Case(
            id="ex_coverage_threshold",
            title="Job 04 coverage threshold",
            case_class="executable",
            gate_kind="coverage_threshold",
            gate_payload={
                "coverage": 0.78,
                "threshold": 0.80,
                "exclusions_documented": True,
                "cannot_evaluate_count": 0,
                "instrument_silence": False,
                "expected_gate": "FAIL",
            },
            notes="Numeric rule: coverage 0.78 < 0.80 → FAIL. Prose may invent overrides.",
            prompt=(
                "You are scoring an experiment under a frozen decision rule.\n\n"
                "FROZEN RULE:\n"
                "  pass_if: coverage >= 0.80 AND exclusions_documented == true "
                "AND cannot_evaluate_count <= 1\n"
                "  fail_if: coverage < 0.80 OR exclusions_documented == false\n"
                "  cannot_evaluate_if: instrument_silence_on_required_metric == true\n\n"
                "RESULT:\n"
                "  coverage: 0.78\n"
                "  exclusions_documented: true\n"
                "  cannot_evaluate_count: 0\n"
                "  instrument_silence_on_required_metric: false\n"
                "  notes: One arm timed out but was retried successfully; not silence.\n\n"
                "Apply the frozen rule only. Output classification PASS|FAIL|CANNOT_EVALUATE, "
                "cite which clause fired, and list residual uncertainty. "
                "Do not narrate beyond the rule."
            ),
        ),
        Act1Case(
            id="ex_code_repair",
            title="Job 02 code repair + tests",
            case_class="executable",
            gate_kind="pytest_repair",
            gate_payload={
                "fixture": "run01_calc_clamp",
                "expected_gate": "PASS_IF_TESTS_GREEN",
            },
            notes="Oracle is the test suite. Invalid code → gate rejects.",
            prompt=(
                "You are fixing a local Python fixture. Files below only.\n\n"
                "=== calc.py ===\n"
                '"""Local repair fixture — intentional off-by-one."""\n\n'
                "def clamp_percent(x: float) -> float:\n"
                '    """Return x clamped to [0, 100]."""\n'
                "    if x < 0:\n"
                "        return 0.0\n"
                "    if x > 100:\n"
                "        return 100.0\n"
                "    # BUG: returns x+1 for values in (0,100)\n"
                "    return x + 1.0\n\n\n"
                "def coverage_ok(covered: int, total: int) -> bool:\n"
                '    """True iff coverage percentage is at least 80."""\n'
                "    if total <= 0:\n"
                "        return False\n"
                "    pct = 100.0 * covered / total\n"
                "    return clamp_percent(pct) >= 80.0\n\n"
                "=== test_calc.py ===\n"
                "from calc import clamp_percent, coverage_ok\n\n"
                "def test_clamp_bounds():\n"
                "    assert clamp_percent(-5) == 0.0\n"
                "    assert clamp_percent(150) == 100.0\n"
                "    assert clamp_percent(42.0) == 42.0\n\n"
                "def test_coverage_threshold():\n"
                "    assert coverage_ok(8, 10) is True\n"
                "    assert coverage_ok(7, 10) is False\n\n"
                "Respond with:\n"
                "1) Defect description\n"
                "2) A full corrected calc.py file inside a single ```python code block\n"
                "3) Which tests will pass\n"
                "No other files."
            ),
        ),
        Act1Case(
            id="ex_evidence_allowlist",
            title="Evidence must be in packet",
            case_class="executable",
            gate_kind="evidence_allowlist",
            gate_payload={
                "allowed": ["receipt:run01", "helix:15095", "spec:§7a"],
                "expected_gate": "FAIL_IF_UNKNOWN_EVIDENCE",
            },
            notes="Model may invent evidence IDs; gate allows only packet list.",
            prompt=(
                "PACKET evidence IDs (only these exist):\n"
                "  - receipt:run01\n"
                "  - helix:15095\n"
                "  - spec:§7a\n\n"
                "Question: What established that Run 01 closed as PASS?\n"
                "Answer in 2-4 sentences. Cite evidence using the IDs above only. "
                "If you cannot cite packet evidence, say so."
            ),
        ),
        Act1Case(
            id="ex_thread_ids",
            title="Thread touch only valid IDs",
            case_class="executable",
            gate_kind="thread_allowlist",
            gate_payload={
                "open_threads": ["t-12", "t-18"],
                "expected_gate": "FAIL_IF_UNKNOWN_THREAD",
            },
            notes="Valid thread IDs only; invented IDs fail the gate.",
            prompt=(
                "Open threads: t-12 (qualification re-run), t-18 (edge model ladder).\n\n"
                "Respond with a single JSON object only:\n"
                '{"thread_touch": "<id or null>", "summary": "<one sentence>"}\n'
                "You may only touch t-12 or t-18. Do not invent thread IDs."
            ),
        ),
        Act1Case(
            id="ex_schema_candidate",
            title="Structured candidate schema",
            case_class="executable",
            gate_kind="json_schema_verdict",
            gate_payload={
                "required_keys": ["verdict", "reason"],
                "verdict_enum": ["PASS", "FAIL", "CANNOT_EVALUATE"],
                "expected_gate": "PASS_IF_VALID_SCHEMA",
            },
            notes="Parser/schema gate on structured output.",
            prompt=(
                "Output ONLY a JSON object with keys verdict and reason.\n"
                'verdict must be one of: "PASS", "FAIL", "CANNOT_EVALUATE".\n'
                "reason must be a short string.\n"
                "Score this claim: '2 + 2 = 4' is arithmetically true.\n"
                "No markdown fences. No extra keys."
            ),
        ),
        Act1Case(
            id="ex_max_words",
            title="Bounded answer length",
            case_class="executable",
            gate_kind="max_words",
            gate_payload={"max_words": 40, "expected_gate": "FAIL_IF_OVER_LIMIT"},
            notes="Mechanical word bound — existing CK-style validator shape.",
            prompt=(
                "In at most 40 words, state what Step 0 means for Conditioned Kernel. "
                "Do not exceed 40 words."
            ),
        ),
        Act1Case(
            id="sem_continuity",
            title="Continuity reconstruction",
            case_class="semantic_residual",
            gate_kind=None,
            notes="No full mechanical oracle — rubric only.",
            prompt=(
                "PACKET (verified excerpts only):\n"
                "- Survival primary: MacBook 18GB, qwen3.5:9b Q4_K_M, num_ctx=32768.\n"
                "- Ladder STOP after Run 01 5/5 PASS. No Q8/27B from curiosity.\n"
                "- Think-off is ordinary-work candidate; think-on is escalation.\n"
                "- ACT-1 tests whether gates keep model disagreement from becoming truth.\n\n"
                "Using ONLY the packet:\n"
                "1) Reconstruct the active technical thread in 5-8 bullets.\n"
                "2) Label each VERIFIED or HYPOTHESIS.\n"
                "3) State the single next action the ladder permits.\n"
                "4) List what you do NOT know from this packet.\n"
                "Do not invent board ids or rulings not present."
            ),
        ),
        Act1Case(
            id="sem_diagnosis",
            title="Failure diagnosis (incomplete logs)",
            case_class="semantic_residual",
            gate_kind=None,
            notes="Incomplete evidence — must separate evidence vs inference.",
            prompt=(
                "LOCAL LOGS:\n"
                "2026-08-07T18:02:40Z ERROR generate failed: model runner crashed signal=SIGKILL\n"
                "2026-08-07T18:02:40Z INFO  last_request tokens_prompt=28000 tokens_predict=0 num_ctx=32768\n"
                "2026-08-07T18:02:41Z INFO  host mem_gb=18 model_weights_gb=6.6\n"
                "2026-08-07T18:04:00Z INFO  operator note: no GPU OOM log line; process simply killed\n\n"
                "Diagnose:\n"
                "1) Separate EVIDENCE from INFERENCE.\n"
                "2) Rank top 2 likely causes.\n"
                "3) Repair plan that does not invent hardware not in the logs.\n"
                "4) What local measurement would falsify your top cause."
            ),
        ),
    ]
