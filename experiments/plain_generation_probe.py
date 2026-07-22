#!/usr/bin/env python3
"""Plain Ollama generation on each model. No packet, no schema, no format."""
import json, time, urllib.request

PROMPT = ("In two or three sentences, explain what makes a good note-to-self "
          "when you know you will forget everything before reading it.")
MODELS = ["qwen2.5:0.5b", "gemma3:1b", "qwen3.5:0.8b", "gemma3:4b"]
OUT = "/tmp/plaingen_results.json"

results = []
for m in MODELS:
    body = json.dumps({"model": m, "prompt": PROMPT, "stream": False}).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            d = json.loads(r.read())
        results.append({
            "model": m,
            "elapsed_s": round(time.time() - t0, 1),
            "eval_count": d.get("eval_count"),
            "thinking": d.get("thinking"),
            "response": (d.get("response") or "").strip(),
        })
        print(f"done {m} in {time.time()-t0:.0f}s", flush=True)
    except Exception as e:
        results.append({"model": m, "error": f"{type(e).__name__}: {e}",
                        "elapsed_s": round(time.time() - t0, 1)})
        print(f"FAILED {m}: {e}", flush=True)

with open(OUT, "w") as f:
    json.dump({"prompt": PROMPT, "results": results}, f, indent=2)
print("wrote " + OUT)
