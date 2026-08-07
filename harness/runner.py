#!/usr/bin/env python3
"""ECS runner — the SPEC §9 state machine.

    load ECS packet -> build prompt -> generate -> LINT -> COMPILE -> SANITIZE
       -> CBMC -> VECTORS(device) -> BUDGET -> ACCEPT -> measure -> probe -> receipt
    any gate failure -> repair (<= 4 iterations) -> re-enter at LINT
    repair budget exhausted -> REJECT -> receipt (full trace kept)
    generation transport error / runner termination (OOM class)
       -> NOT a candidate failure. Re-run the eviction barrier, retry.
          Does not consume a sample, does not touch the repair budget.

THE STUB GENERATOR EXISTS FOR P2's DEFINITION OF DONE. SPEC §13 requires that
"a stub generator (returns oracle verbatim) produces a full green receipt end
to end" before P2 closes. It spends no API calls and proves the pipeline is
wired, not that any model can code.

INVARIANTS THIS FILE IS RESPONSIBLE FOR, none of which the gate chain can
enforce on its own:

  INFRA FAULTS ARE NOT CANDIDATE FAILURES. A transport error, an OOM-killed
  runner, or a barrier that failed closed consumes NO sample, touches NO
  repair budget, and never enters an acceptance-rate denominator. This is the
  error that produced two false granite negatives before the barrier existed
  (SPEC §4a.1), and the separation lives here because only the runner sees
  both the adapter's status and the sample counter.

  SERVED-STRING IDENTITY WITHIN AN ARM. Every call records requested and
  served model strings. If the served string changes mid-arm the arm is
  INVALIDATED and rerun — never averaged, never adjusted (PREREG §7). One
  requested alias was measured serving a different model, and a frozen row
  became unsatisfiable mid-build; see SUPERSESSION-001.

  PER-CELL BATCHING. A cell is one (generator × kernel × arm). All samples in
  a cell run consecutively under a single verified eviction barrier, so the
  barrier re-runs at cell boundaries only.

  VECTOR WITHHOLDING IS DERIVED, NEVER DECLARED. The weak arm's half-withheld
  vectors come from vector_policy.select() keyed on completeness, not from
  anything a packet author can set. The chain APPLIES it to gates 3 and 5;
  this file only reports it.

FIVE CORRECTIONS, 2026-08-05, on Anthony's ruling that P2 stays open
-------------------------------------------------------------------
The state machine above was described accurately and implemented partially.
Each of these was a silent divergence between the documented instrument and the
running one, and each would have been invisible in the receipts:

  1. THE PROMPT WAS BUILT AND THROWN AWAY. `prompt_mod.build()` produced text
     whose sha256 went into the receipt, and then `generate()` was called with
     the PACKET PATH — never the prompt. Every receipt would have carried a
     prompt hash the generator never saw. Adapters take prompt text; the runner
     now passes it, and the identifier stored is a hash of what was actually
     sent.

  2. REPAIR FEEDBACK WENT NOWHERE. The stopping gate's feedback was formatted
     into a local `feedback` variable that the next iteration never read. All
     five repair attempts sent the SAME prompt, so the repair loop measured
     sampling variance under a fixed prompt rather than repair. That is the
     difference between a <=4-iteration repair policy and four extra draws, and
     PREREG §7 prices them differently.

  3. THE EVICTION BARRIER WAS NEVER INVOKED. SPEC §4a.1 puts it at cell
     boundaries and the docstring above says so, but nothing called it. The two
     false granite negatives that produced §4a.1 would have recurred — as
     candidate failures, since without the barrier an OOM arrives as a model
     error rather than as a barrier refusal.

  4. SERVED IDENTITY WAS PER-CELL, NOT PER-ARM. `arm_state` was created inside
     run_cell, so a served-string change BETWEEN cells of the same arm — the
     likely shape, since cells are hours apart — passed unnoticed. PREREG §7
     scopes the assertion to the arm. It is now owned by the arm and threaded
     into each cell.

  5. INFRA ABORTS ATE SAMPLE SLOTS. `for i in range(n_samples)` spent a slot on
     an aborted candidate. Excluding it from the denominator afterwards is
     correct and insufficient: a cell that hit three transport errors returned
     seven scored samples where the design says ten, and n would have varied
     with device weather. Slots are now refilled until n scored candidates
     exist or the arm's abort cap trips.
"""
import json, os, subprocess, sys, time, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness", "gates"))
sys.path.insert(0, os.path.join(ROOT, "harness", "generators"))

import yaml
import chain
import prompt as prompt_mod
import adapters
import vector_policy
import remote as rmt

MAX_REPAIRS = 4        # PREREG §7
MAX_INFRA_RETRIES = 3  # PREREG §7, then infra abort
MAX_INFRA_ABORTS = 5   # per arm, then the arm is invalidated
MAX_SLOT_REFILLS = 20  # backstop: refilling is not an unbounded retry loop


def harness_git_sha():
    """The exact harness commit a receipt was produced by.

    Receipts previously named the kernel, arm, model and prompt but not the
    INSTRUMENT. Every fail-closed correction in this round changes what
    "accepted" means, so a receipt that does not name its harness revision
    cannot be told apart from one produced before the corrections. Recorded
    with a dirty flag, because a receipt from an uncommitted tree is not
    reproducible and should say so on its face.

    DIRTINESS IS SCOPED TO WHAT DETERMINES A RECEIPT, and that scoping is a
    correctness choice rather than a convenience. A whole-worktree check reads
    `state/current.json` — a runtime file the harness rewrites as it runs — and
    an untracked `.grok/` seat directory, and calls the instrument unreproducible
    because of them. It refused a clean instrument on the first regeneration
    attempt for exactly that reason.

    The scope below is the instrument: the harness, the ECS packets, the trusted
    tier, and the SPEC that governs them. Anything outside it cannot change what
    a gate decides. The paths are RECORDED in the receipt so the claim is
    auditable rather than trusted — a later reader can see precisely what was
    and was not covered by the word "clean".
    """
    INSTRUMENT_PATHS = ["harness", "ecs", "trusted", "SPEC.md"]

    def _git(*a):
        try:
            return subprocess.run(["git", "-C", ROOT] + list(a),
                                  capture_output=True, text=True).stdout.strip()
        except Exception:
            return ""
    sha = _git("rev-parse", "HEAD")
    changed = _git("status", "--porcelain", "--", *INSTRUMENT_PATHS)
    dirty = bool(changed)
    return {"harness_git_sha": sha or "unknown",
            "harness_tree_dirty": dirty,
            "dirty_scope": INSTRUMENT_PATHS,
            "uncommitted": [l.strip() for l in changed.splitlines()][:20],
            "note": ("receipt produced from an UNCOMMITTED instrument; not "
                     "reproducible from the sha alone") if dirty else
                    "instrument clean at this sha; scope is listed, not implied"}


def stub_generator(_prompt, kernel, seat="agentB"):
    """P2's stub: returns a sealed oracle verbatim.

    Deliberately NOT a model. Its only job is to prove the pipeline carries a
    candidate from packet to green receipt. A stub that produced anything
    cleverer would test the stub instead of the harness.
    """
    p = os.path.join(ROOT, "trusted", "oracles", f"{kernel}_{seat}.c")
    return {"generator_id": "STUB", "model_string_requested": "stub:oracle-verbatim",
            "model_string_served": "stub:oracle-verbatim", "status": "ok",
            "temperature": adapters.TEMPERATURE, "elapsed_ms": 0,
            "output": open(p).read(), "output_chars": os.path.getsize(p),
            "stub_source": os.path.relpath(p, ROOT)}


def _real_post_accept(src, packet, gates):
    """SPEC §9's measure and probe stages, resolved lazily so importing the
    runner never touches the measurement path. There is no `None means skip`:
    a caller either provides its own stage (tests mock the device boundary
    here) or gets the real one. A probe battery that cannot run raises
    chain.Infra and the slot is refilled — never a silent skip (§7a.2b)."""
    sys.path.insert(0, os.path.join(ROOT, "harness", "measure"))
    import post_accept as pa
    return pa.run(src, packet, gates)


def run_candidate(packet_path, generate, sample_index, arm_state,
                  post_accept=None):
    """One candidate through generation, gates, and up to MAX_REPAIRS repairs.

    An ACCEPTED candidate then runs the post-accept stages (measure, probe)
    before its record returns; acceptance without a probe record would leave
    the cell's D uncomputable while the receipt read green."""
    packet = yaml.safe_load(open(packet_path))
    kernel = packet["kernel"]
    rec = {"kernel": kernel, "completeness": packet["completeness"],
           "sample_index": sample_index,
           "repair_trace": [], "infra_retry_count": 0, "infra_abort": False,
           "accepted": False, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                           time.gmtime())}

    feedback = None
    for attempt in range(MAX_REPAIRS + 1):
        # The prompt is REBUILT each attempt so repair feedback reaches the
        # generator. SPEC §9 permits exactly three ingredients and prompt.build
        # is the only place they are combined; passing feedback here is the
        # third, and passing anything else is not expressible from this call.
        built = prompt_mod.build(packet_path, feedback)
        if attempt == 0:
            rec["prompt_sha256"] = built["prompt_sha256"]      # the generation prompt

        # --- generate, with infra faults kept out of the sample accounting ---
        gen = None
        for _ in range(MAX_INFRA_RETRIES):
            gen = generate(built["prompt"], kernel)
            if gen["status"] == "ok":
                break
            rec["infra_retry_count"] += 1
        if gen is None or gen["status"] != "ok":
            rec["infra_abort"] = True
            arm_state["infra_aborts"] += 1
            rec["note"] = ("INFRA ABORT: no sample consumed, no repair budget "
                           "touched, excluded from acceptance denominators")
            rec["infra_reason"] = str((gen or {}).get("error", ""))[:200]
            return rec

        # --- served-string identity within the arm ---
        served = gen["model_string_served"]
        prior = arm_state.setdefault("served", {}).setdefault(gen["generator_id"], served)
        if served != prior:
            rec["arm_invalidated"] = True
            rec["note"] = (f"served string changed mid-arm: {prior} -> {served}. "
                           f"PREREG §7 invalidates the arm; it is rerun, not averaged.")
            arm_state["invalidated"] = True
            return rec
        rec["generator"] = {k: gen[k] for k in
                            ("generator_id", "model_string_requested",
                             "model_string_served", "temperature")}

        src = adapters.strip_fences(gen["output"])
        gates = chain.run(src, packet)

        # A gate that could not RUN is an instrument fault, not a verdict on the
        # candidate. It aborts the slot exactly as a transport error does: no
        # sample, no repair budget, no denominator. Scoring it would convert a
        # dead ssh or a drifting clock into evidence about a model.
        if gates.get("infra_fault"):
            rec["infra_abort"] = True
            arm_state["infra_aborts"] += 1
            rec["infra_reason"] = f"gate chain: {gates.get('infra_reason','')}"
            rec["note"] = ("INFRA ABORT (gate chain): no sample consumed, no "
                           "repair budget touched, excluded from denominators")
            return rec

        rec["vector_policy"] = gates.get("vector_policy")
        rec["repair_trace"].append({"attempt": attempt,
                                    "prompt_sha256": built["prompt_sha256"],
                                    "is_repair": built["is_repair"],
                                    "stopped_at": gates["stopped_at"],
                                    "gates": {k: v["result"] for k, v in gates["gates"].items()}})
        if gates["accepted"]:
            # --- SPEC §9: ACCEPT -> measure -> probe, before the receipt ----
            # A stage failure here is an INSTRUMENT fault: the candidate is
            # already accepted, so nothing the measure/probe path does is a
            # verdict on it. The slot aborts and refills exactly as a
            # transport error does — an accepted-but-unprobed artifact must
            # not enter a cell, because D is computed over accepted artifacts
            # and a missing probe record would poison the whole cell's D.
            try:
                extra = (post_accept or _real_post_accept)(src, packet, gates)
            except chain.Infra as e:
                rec["infra_abort"] = True
                arm_state["infra_aborts"] += 1
                rec["infra_reason"] = f"post-accept: {str(e)[:200]}"
                rec["note"] = ("INFRA ABORT (measure/probe stage): candidate "
                               "was accepted but the instrument could not "
                               "measure or probe it; no sample consumed, slot "
                               "refilled (SPEC §7a.2b, §9)")
                return rec
            rec["accepted"] = True
            rec["gates"] = gates["gates"]
            rec["candidate_sha256"] = hashlib.sha256(src.encode()).hexdigest()
            rec["source"] = src
            rec.update(extra)
            return rec

        # --- repair feedback is the STOPPING gate's, and only that ---
        stop = gates["stopped_at"]
        fb = gates["gates"][stop]["feedback"]
        feedback = f"Gate {stop} failed:\n" + "\n".join(str(x) for x in fb[:3])
        rec["gates"] = gates["gates"]

    rec["note"] = f"repair budget of {MAX_REPAIRS} exhausted; full trace kept"
    return rec


def new_arm_state():
    """Arm-scoped state. Created ONCE PER ARM and threaded through every cell.

    Served-string identity is a PREREG §7 assertion about an arm, and cells in
    one arm are hours apart — which is when a provider re-points an alias. State
    created inside run_cell could only ever have caught a change between two
    samples of the same cell.
    """
    return {"infra_aborts": 0, "invalidated": False, "served": {}}


def barrier_for(packet, local_model=None, device="jetson"):
    """SPEC §4a.1 eviction barrier, once per cell, before any generation.

    Runs on the device because that is where MemFree lives; the local adapters
    deliberately do not manage memory themselves, so per-cell placement here is
    what makes per-cell batching safe. A barrier that fails closed is an INFRA
    fault: the cell does not run, and no candidate is scored against a device
    that could not be cleared.

    Frontier generators reach no device, so there is nothing to evict and the
    barrier is recorded as not-applicable rather than silently skipped.
    """
    if not local_model:
        return {"applicable": False, "barrier_ok": True,
                "note": "remote generator; no device memory to clear"}
    # The barrier and its threshold table are SHIPPED to the device each time
    # rather than assumed present. A stale copy on the Jetson is the exact
    # failure the barrier exists to prevent — thresholds that no longer match
    # the models (Grok reservation R2, #13712) — and "the file was already
    # there" is not a version claim.
    dev = os.path.join(ROOT, "harness", "device")
    script = ["set -e", "mkdir -p ~/ecs/barrier", "cd ~/ecs/barrier"]
    script += rmt.put("eviction_barrier.py",
                      open(os.path.join(dev, "eviction_barrier.py")).read())
    script += rmt.put("generators.json",
                      open(os.path.join(dev, "generators.json")).read())
    script.append(f"python3 eviction_barrier.py --barrier-for {local_model}")
    try:
        r = rmt.run(device, script, timeout=600)
    except Exception as e:
        return {"applicable": True, "barrier_ok": False, "error": str(e)[:300],
                "note": "barrier unreachable; treated as FAILED CLOSED"}
    if rmt.transfer_failed(r):
        return {"applicable": True, "barrier_ok": False,
                "note": "barrier payload digest mismatch; FAILED CLOSED"}
    try:
        out = json.loads([l for l in r.stdout.splitlines() if l.startswith("{")][-1]
                         if "{" in r.stdout else r.stdout)
    except Exception:
        return {"applicable": True, "barrier_ok": False,
                "error": (r.stderr or r.stdout)[:300],
                "note": "barrier did not report; treated as FAILED CLOSED"}
    out["applicable"] = True
    return out


def run_cell(packet_path, generate, n_samples=1, out_dir=None, arm_state=None,
             local_model=None, post_accept=None):
    """One cell: (generator × kernel × arm), samples consecutive under one barrier."""
    packet = yaml.safe_load(open(packet_path))
    vecs = json.load(open(os.path.join(ROOT, "trusted", "vectors",
                                       f"{packet['kernel']}.json")))["vectors"]
    arm_state = arm_state if arm_state is not None else new_arm_state()
    cell = {"cell": {"kernel": packet["kernel"], "arm": packet["completeness"]},
            "vector_policy": vector_policy.receipt_fields(vecs, packet["completeness"]),
            "harness": harness_git_sha(),
            "candidates": []}

    # --- eviction barrier, at the cell boundary, before anything generates ---
    cell["barrier"] = barrier_for(packet, local_model)
    if not cell["barrier"].get("barrier_ok"):
        cell["cell_aborted"] = True
        cell["note"] = ("BARRIER FAILED CLOSED before generation: no sample "
                        "consumed, nothing scored (SPEC §4a.1)")
        cell["summary"] = {"samples": 0, "accepted": 0, "infra_aborts": 0,
                           "acceptance_denominator": 0}
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            p = os.path.join(out_dir,
                             f"{packet['kernel']}_{packet['completeness']}.json")
            json.dump(cell, open(p, "w"), indent=1)
            cell["receipt_path"] = p
        return cell

    # --- n SCORED samples, with aborted slots refilled rather than lost -----
    scored_count, refills, idx = 0, 0, 0
    while scored_count < n_samples:
        c = run_candidate(packet_path, generate, idx, arm_state,
                          post_accept=post_accept)
        cell["candidates"].append(c)
        idx += 1
        if c.get("infra_abort"):
            refills += 1
            c["slot_refilled"] = True
            if arm_state["infra_aborts"] > MAX_INFRA_ABORTS:
                cell["arm_invalidated"] = True
                cell["note"] = (f">{MAX_INFRA_ABORTS} infra aborts; arm rerun, "
                                f"not adjusted")
                break
            if refills > MAX_SLOT_REFILLS:
                cell["arm_invalidated"] = True
                cell["note"] = (f">{MAX_SLOT_REFILLS} slot refills; the device is "
                                f"not fit to measure on, arm rerun")
                break
            continue          # the slot is refilled; it is NOT spent
        scored_count += 1
        if arm_state["invalidated"]:
            cell["arm_invalidated"] = True
            break
    cell["slot_refills"] = refills
    acc = [c for c in cell["candidates"] if c["accepted"]]
    scored = [c for c in cell["candidates"] if not c.get("infra_abort")]
    cell["summary"] = {"samples": len(cell["candidates"]), "accepted": len(acc),
                       "infra_aborts": arm_state["infra_aborts"],
                       "slot_refills": refills,
                       "scored_samples": len(scored),
                       "requested_samples": n_samples,
                       "acceptance_denominator": len(scored),
                       "note": ("infra aborts excluded from the denominator and "
                                "their slots refilled, so n is by design not by "
                                "device weather")}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, f"{packet['kernel']}_{packet['completeness']}.json")
        json.dump(cell, open(p, "w"), indent=1)
        cell["receipt_path"] = p
    return cell


if __name__ == "__main__":
    pkt = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "ecs", "crc32.ecs.yaml")
    gen = lambda prompt, k: stub_generator(prompt, k)
    c = run_cell(pkt, gen, n_samples=1,
                 out_dir=os.path.join(ROOT, "receipts", "p2_stub"))
    print(json.dumps({k: v for k, v in c.items() if k != "candidates"}, indent=1))
    print(f"  accepted={c['candidates'][0]['accepted']} "
          f"receipt={c.get('receipt_path')}")
