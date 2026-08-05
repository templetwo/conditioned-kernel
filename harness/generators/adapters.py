#!/usr/bin/env python3
"""Generator adapters — G1 Anthropic, G2 xAI, G3/G4 ollama on the Jetson.

Every adapter returns the SAME record shape, so the runner never branches on
provider and the receipt fields PREREG §7 requires are impossible to omit.

THREE THINGS THIS LAYER EXISTS TO GET RIGHT
-------------------------------------------
1. SERVED-STRING IDENTITY. Every call records `model_string_requested` AND
   `model_string_served`, the latter read from the provider's own response.
   Measured 2026-08-04: requesting `grok-4` returns `grok-4.3`, and `grok-4`
   is not even in the provider's model list. A harness logging its request
   string would have credited ~60 generations to a model that never ran. The
   runner asserts identity within an arm; a mid-arm change invalidates the arm
   rather than being averaged (PREREG §7).

2. INFRA FAULTS ARE NOT CANDIDATE FAILURES. Transport errors, runner
   terminations and barrier failures return status="infra_fault". They consume
   no sample, touch no repair budget, and stay out of acceptance-rate
   denominators. Getting this wrong is how a device memory fault becomes
   evidence about a model's capability — see SPEC §4a.1 and the granite false
   negatives that produced it.

3. TEMPERATURE 0.8 EVERYWHERE, no per-provider variation, frozen in PREREG §7.
   It is a module constant rather than a parameter, so no call site can drift.

Credentials are read from the operator's env files at call time. No key value
is stored in this file, logged, or placed in any returned record.

The local adapters do NOT manage memory themselves. Eviction is the runner's
job at cell boundaries via harness/device/eviction_barrier.py, because
per-call eviction would defeat per-cell batching.
"""
import json, os, subprocess, time, urllib.request

TEMPERATURE = 0.8          # PREREG §7, all four generators. Not a parameter.
NUM_CTX = 4096             # PREREG §7, local generators.
BANNED = {"grok-4"}        # floating alias, measured to serve grok-4.3


def _secret(name):
    """Read a credential by name from the operator's env files. Never logged."""
    for path in ("~/.hermes/.env", "~/.config/sovereign-bridge.env"):
        p = os.path.expanduser(path)
        if os.path.exists(p):
            for line in open(p):
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get(name)


def _record(gen_id, requested, served, text, status, t0, **extra):
    r = {"generator_id": gen_id,
         "model_string_requested": requested,
         "model_string_served": served,
         "status": status,
         "temperature": TEMPERATURE,
         "elapsed_ms": round((time.time() - t0) * 1000),
         "output": text,
         "output_chars": len(text or "")}
    r.update(extra)
    return r


def anthropic(prompt, model="claude-opus-4-5-20251101", gen_id="G1", max_tokens=1500):
    """G1. Model string is SUPERSESSION-001, not PREREG §4.

    PREREG §4 pinned `claude-opus-5`, which on 2026-08-05 began rejecting the
    temperature parameter §7 fixes at 0.8 for all four generators — the two rows
    were jointly unsatisfiable. Anthony ruled option (b): keep uniform sampling,
    move G1 to a dated model. See evidence/SUPERSESSION-001.md. `prereg-v1` and
    its DOI are unchanged; this supersedes one row beside them.

    The dated string is also VERSION-pinned rather than alias-pinned, which
    repairs §12.1's exposure for G1. G2 remains alias-pinned — xAI publishes no
    dated string for the 4.5 line.
    """
    t0 = time.time()
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "temperature": TEMPERATURE,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": _secret("ANTHROPIC_API_KEY") or "",
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except Exception as e:
        return _record(gen_id, model, None, "", "infra_fault", t0, error=str(e)[:200])
    text = "".join(b.get("text", "") for b in d.get("content", []))
    # Anthropic exposes no seed; PREREG §7 records the sample index instead.
    return _record(gen_id, model, d.get("model"), text, "ok", t0,
                   seed=None, out_tokens=(d.get("usage") or {}).get("output_tokens"))


def xai(prompt, model="grok-4.5", gen_id="G2", max_tokens=1500):
    t0 = time.time()
    if model in BANNED:
        return _record(gen_id, model, None, "", "infra_fault", t0,
                       error=f"{model} is a banned floating alias (PREREG §4)")
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "temperature": TEMPERATURE,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + (_secret("XAI_API_KEY") or ""),
                 "content-type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except Exception as e:
        return _record(gen_id, model, None, "", "infra_fault", t0, error=str(e)[:200])
    text = d["choices"][0]["message"].get("content") or ""
    return _record(gen_id, model, d.get("model"), text, "ok", t0,
                   out_tokens=(d.get("usage") or {}).get("completion_tokens"))


def ollama(prompt, model, gen_id, host="jetson", max_tokens=1500):
    """Local generator, reached over SSH because ollama binds 127.0.0.1 only."""
    t0 = time.time()
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False,
                          "keep_alive": "5m",
                          "options": {"num_ctx": NUM_CTX,
                                      "temperature": TEMPERATURE,
                                      "num_predict": max_tokens}})
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", host,
             "curl -s --max-time 300 http://127.0.0.1:11434/api/generate "
             "-H 'content-type: application/json' -d @-"],
            input=payload, capture_output=True, text=True, timeout=360)
        d = json.loads(r.stdout)
    except Exception as e:
        return _record(gen_id, model, None, "", "infra_fault", t0, error=str(e)[:200])
    if "error" in d:
        # OOM-killed runners land here. NOT a candidate failure (SPEC §4a.1).
        return _record(gen_id, model, None, "", "infra_fault", t0,
                       error=str(d["error"])[:200])
    return _record(gen_id, model, d.get("model"), d.get("response", ""), "ok", t0,
                   eval_count=d.get("eval_count"))


def strip_fences(text):
    """Remove markdown fences before the gate chain.

    Both local generators wrap output in fences despite an explicit instruction
    not to — measured at P0 for G3 and G4 alike. Gate 1 would reject every such
    candidate for a reason that has nothing to do with the ECS, manufacturing a
    failure that is an artifact of presentation rather than a property of the
    generator.
    """
    t = (text or "").strip()
    if "```" not in t:
        return t
    out = []
    for i, part in enumerate(t.split("```")):
        if i % 2 == 1:                       # inside a fence
            first, _, rest = part.partition("\n")
            out.append(rest if first.strip().isalpha() else part)
    return ("\n".join(out).strip() or t)
