#!/usr/bin/env python3
"""LN-6 contract probe — standing consequence 11, at arm open and arm close.

An alias can keep its identity perfectly and change its CONTRACT: on
2026-08-05 `claude-opus-5` began rejecting the temperature parameter PREREG
§7 fixes, with the served string unchanged. Served-string assertion catches a
repointed alias; it cannot catch a moved interface. This probe records the
interface state in the arm receipt so the loud case is discovered BEFORE
samples are spent rather than when a call fails mid-cell.

MECHANISM (LN-6, verbatim intent):
  1. before an arm opens, issue a minimal request to each frontier generator
     with exactly the sampling parameters the arm will use — the adapters
     hard-code those parameters (temperature is a module constant), so the
     probe goes through the same call path as every real sample and cannot
     drift from it;
  2. record accepted / rejected / cannot-evaluate per generator;
  3. re-issue at arm close and compare. A contract that CHANGED mid-arm
     invalidates the arm on the same rule as a served-string change.

WHAT THIS DOES NOT DEFEND, declared: a parameter accepted and silently
ignored returns "accepted" at both ends and is invisible here (LN-6's third
row). That case remains open by declaration; closing it is a v1.1
distributional test, not a v1 probe.

OUTCOMES per generator (SPEC §7a.2b — three, with cause):
  accepted         the call succeeded under the arm's parameters
  rejected         the provider refused a parameter (HTTP 4xx) — the LOUD
                   contract case; the cause carries the provider's words
  cannot_evaluate  transport failed; the contract state is UNKNOWN, which is
                   neither of the above and must not be recorded as either

Comparison outcomes: unchanged / changed / cannot_evaluate. `changed`
invalidates the arm; `cannot_evaluate` blocks the arm from closing as valid
— an unverifiable contract is not a verified one — but is triaged as
instrument, not as a provider change.

Local generators are not probed: G3/G4 contracts are pinned by model digest
and ollama version on a device we control, and LN-6 scopes the probe to the
frontier generators whose interfaces move under us.
"""
import re, sys, time


PROBE_PROMPT = "Reply with the single word: ok"   # minimal; never an ECS prompt
PROBE_MAX_TOKENS = 8


def classify(record):
    """Fold an adapter record into the three-state contract outcome."""
    if record.get("status") == "ok":
        return {"outcome": "accepted",
                "model_string_served": record.get("model_string_served")}
    err = str(record.get("error", ""))
    # The loud contract case arrives as an HTTP 4xx: the provider understood
    # the request and refused a parameter. Anything else (timeout, DNS, 5xx)
    # says nothing about the contract.
    if re.search(r"\b4\d\d\b", err):
        return {"outcome": "rejected", "cause": err[:300]}
    return {"outcome": "cannot_evaluate",
            "cause": f"transport failed; contract state unknown: {err[:200]}"}


def probe(frontier_calls):
    """One probe pass. `frontier_calls` maps generator id -> zero-argument
    callable returning an adapter record (the indirection is the test seam;
    production passes lambdas over adapters.anthropic / adapters.xai)."""
    out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "generators": {}}
    for gen_id, call in sorted(frontier_calls.items()):
        try:
            rec = call()
        except Exception as e:
            rec = {"status": "infra_fault", "error": str(e)[:200]}
        out["generators"][gen_id] = {
            "model_string_requested": rec.get("model_string_requested"),
            **classify(rec)}
    return out


def compare(open_probe, close_probe):
    """Arm-close comparison. Three states, and the consumer handles all three
    (the orchestrator halts on both non-`unchanged` states, with different
    triage)."""
    diffs, unknown = [], []
    gens = set(open_probe["generators"]) | set(close_probe["generators"])
    for g in sorted(gens):
        a = open_probe["generators"].get(g, {}).get("outcome")
        b = close_probe["generators"].get(g, {}).get("outcome")
        if a is None or b is None:
            unknown.append(f"{g}: probed at only one end (open={a}, close={b})")
        elif "cannot_evaluate" in (a, b):
            unknown.append(f"{g}: contract unverifiable (open={a}, close={b})")
        elif a != b:
            diffs.append(f"{g}: {a} -> {b}")
    if diffs:
        return {"state": "changed", "diffs": diffs,
                "note": "contract changed mid-arm; the arm is invalidated on "
                        "the same rule as a served-string change (LN-6)"}
    if unknown:
        return {"state": "cannot_evaluate", "cause": "; ".join(unknown),
                "note": "an unverifiable contract is not a verified one; the "
                        "arm may not close as valid on this record"}
    return {"state": "unchanged"}


def default_frontier_calls():
    """Production probes: same adapters, same hard-coded sampling parameters
    the arm's real calls use, minimal token budget."""
    import adapters
    return {
        "G1": lambda: adapters.anthropic(PROBE_PROMPT,
                                         max_tokens=PROBE_MAX_TOKENS),
        "G2": lambda: adapters.xai(PROBE_PROMPT, max_tokens=PROBE_MAX_TOKENS),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(probe(default_frontier_calls()), indent=1))
