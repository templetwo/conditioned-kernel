"""Edge compute profiles and budget enforcement.

Product default is Jetson Orin Nano 8GB-class, not desktop luxury.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from conditioned_kernel.paths import repo_root

DEFAULT_PROFILE_ID = "orin_nano_8gb"


@dataclass(frozen=True)
class EdgeProfile:
    profile_id: str
    description: str
    target_device: str
    arch: str
    ram_gb: int
    model: str
    mode: str
    num_ctx: int
    temperature: float
    seed: int
    max_repair: int
    keep_alive: str
    timeout_s: float
    max_packet_bytes: int
    max_facts: int
    max_open_threads: int
    max_answer_words: int
    max_log_file_bytes: int
    one_model_only: bool
    stream: bool
    cloud: bool
    sensors: bool
    tools: bool
    estimated_model_ram_mb: int
    estimated_substrate_ram_mb: int
    notes: str = ""
    # Ollama chat/generate "think" flag. False disables reasoning channel for
    # thinking-capable kernels (e.g. qwen3.5). Never treated as the final answer.
    think: bool = False
    # Step 0 runtime tuple (optional; survival profiles fill these)
    base_model: str = ""
    quant: str = ""
    digest_prefix: str = ""
    backend: str = "ollama"
    tool_surface: str = "local_only"
    compile_policy: str = "static-v0"
    gate_version: str = "step0-gate-v1"
    think_profile: str = "ordinary"  # ordinary | deliberate (default name for this file)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EdgeProfile":
        return cls(
            profile_id=str(data["profile_id"]),
            description=str(data.get("description") or ""),
            target_device=str(data.get("target_device") or "unknown"),
            arch=str(data.get("arch") or "any"),
            ram_gb=int(data.get("ram_gb") or 8),
            model=str(data.get("model") or "qwen3.5:0.8b"),
            mode=str(data.get("mode") or "chat_json"),
            num_ctx=int(data["num_ctx"] if data.get("num_ctx") is not None else 2048),
            # Preserve valid falsy zeros (RUN 00.8A): temperature=0.0 and seed=0
            # must not fall through value-or-default logic.
            temperature=float(
                data["temperature"] if data.get("temperature") is not None else 0.3
            ),
            seed=int(data["seed"] if data.get("seed") is not None else 42),
            max_repair=int(data["max_repair"] if data.get("max_repair") is not None else 1),
            keep_alive=str(data.get("keep_alive") if data.get("keep_alive") is not None else "2m"),
            timeout_s=float(data["timeout_s"] if data.get("timeout_s") is not None else 90),
            max_packet_bytes=int(
                data["max_packet_bytes"] if data.get("max_packet_bytes") is not None else 6000
            ),
            max_facts=int(data["max_facts"] if data.get("max_facts") is not None else 8),
            max_open_threads=int(
                data["max_open_threads"] if data.get("max_open_threads") is not None else 4
            ),
            max_answer_words=int(
                data["max_answer_words"] if data.get("max_answer_words") is not None else 120
            ),
            max_log_file_bytes=int(
                data["max_log_file_bytes"]
                if data.get("max_log_file_bytes") is not None
                else 5_242_880
            ),
            one_model_only=bool(data.get("one_model_only", True)),
            stream=bool(data.get("stream", False)),
            cloud=bool(data.get("cloud", False)),
            sensors=bool(data.get("sensors", False)),
            tools=bool(data.get("tools", False)),
            estimated_model_ram_mb=int(data.get("estimated_model_ram_mb") or 500),
            estimated_substrate_ram_mb=int(data.get("estimated_substrate_ram_mb") or 200),
            notes=str(data.get("notes") or ""),
            # Default False: Studio path disables thinking for thinking-capable models.
            think=bool(data["think"]) if data.get("think") is not None else False,
            base_model=str(data.get("base_model") or ""),
            quant=str(data.get("quant") or ""),
            digest_prefix=str(data.get("digest_prefix") or ""),
            backend=str(data.get("backend") or "ollama"),
            tool_surface=str(data.get("tool_surface") or "local_only"),
            compile_policy=str(data.get("compile_policy") or "static-v0"),
            gate_version=str(data.get("gate_version") or "step0-gate-v1"),
            think_profile=str(data.get("think_profile") or "ordinary"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "description": self.description,
            "target_device": self.target_device,
            "arch": self.arch,
            "ram_gb": self.ram_gb,
            "model": self.model,
            "mode": self.mode,
            "num_ctx": self.num_ctx,
            "temperature": self.temperature,
            "seed": self.seed,
            "max_repair": self.max_repair,
            "keep_alive": self.keep_alive,
            "timeout_s": self.timeout_s,
            "max_packet_bytes": self.max_packet_bytes,
            "max_facts": self.max_facts,
            "max_open_threads": self.max_open_threads,
            "max_answer_words": self.max_answer_words,
            "max_log_file_bytes": self.max_log_file_bytes,
            "one_model_only": self.one_model_only,
            "stream": self.stream,
            "think": self.think,
            "cloud": self.cloud,
            "sensors": self.sensors,
            "tools": self.tools,
            "estimated_model_ram_mb": self.estimated_model_ram_mb,
            "estimated_substrate_ram_mb": self.estimated_substrate_ram_mb,
            "notes": self.notes,
            "base_model": self.base_model,
            "quant": self.quant,
            "digest_prefix": self.digest_prefix,
            "backend": self.backend,
            "tool_surface": self.tool_surface,
            "compile_policy": self.compile_policy,
            "gate_version": self.gate_version,
            "think_profile": self.think_profile,
        }

    def with_think_profile(self, think_profile: str) -> "EdgeProfile":
        """Same model identity; only ordinary vs deliberate thinking changes."""
        tp = (think_profile or "ordinary").strip().lower()
        if tp not in ("ordinary", "deliberate", "off", "on"):
            raise ValueError(
                f"think_profile must be ordinary|deliberate (got {think_profile!r})"
            )
        think = tp in ("deliberate", "on")
        name = "deliberate" if think else "ordinary"
        d = self.to_dict()
        d["think"] = think
        d["think_profile"] = name
        return EdgeProfile.from_dict(d)

    def runtime_tuple(self) -> dict[str, Any]:
        """Qualified operating-point fields (Step 0 DoD A/D)."""
        return {
            "profile_id": self.profile_id,
            "model": self.model,
            "base_model": self.base_model,
            "quant": self.quant,
            "digest_prefix": self.digest_prefix,
            "backend": self.backend,
            "num_ctx": self.num_ctx,
            "think": self.think,
            "think_profile": self.think_profile,
            "tool_surface": self.tool_surface,
            "compile_policy": self.compile_policy,
            "gate_version": self.gate_version,
            "target_device": self.target_device,
            "arch": self.arch,
            "ram_gb": self.ram_gb,
        }

    @property
    def estimated_working_set_mb(self) -> int:
        return self.estimated_model_ram_mb + self.estimated_substrate_ram_mb

    def headroom_mb(self) -> int:
        # Leave ~2.5GB for OS + Ollama runtime + fragmentation on 8GB class
        reserve = 2500 if self.ram_gb <= 8 else 1500
        return max(0, self.ram_gb * 1024 - reserve - self.estimated_working_set_mb)


def configs_dir() -> Path:
    return repo_root() / "configs" / "edge"


def list_profiles() -> list[str]:
    d = configs_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def load_profile(profile_id: str | None = None) -> EdgeProfile:
    pid = profile_id or DEFAULT_PROFILE_ID
    path = configs_dir() / f"{pid}.json"
    if not path.exists():
        known = ", ".join(list_profiles()) or "(none)"
        raise FileNotFoundError(f"edge profile not found: {pid} (known: {known})")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return EdgeProfile.from_dict(data)


# Dashboard/selection maps are not inference tokens — excluded from edge budget.
_OBSERVABILITY_PACKET_KEYS = frozenset(
    {
        "context_field",
        "evidence_pool_selected",
        "intents",
        "prior_accepted_answer_control",
        # Step 0 provenance: attached after compile, never rendered into the
        # prompt (build_model_input reads an explicit key allowlist), so these
        # are not inference tokens and must not move the edge byte count.
        "compile_policy",
        "gate_version",
        "executable_authority",
    }
)


def packet_byte_size(packet: dict[str, Any]) -> int:
    body = {
        k: v
        for k, v in packet.items()
        if k != "_edge" and k not in _OBSERVABILITY_PACKET_KEYS
    }
    return len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def enforce_packet_budget(
    packet: dict[str, Any],
    profile: EdgeProfile,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Bound packet fields to edge limits. Returns (possibly trimmed) packet.

    If strict and still over max_packet_bytes after trim, raises BudgetError.
    """
    out = dict(packet)
    facts = list(out.get("facts") or [])
    threads = list(out.get("open_threads") or [])
    recent = list(out.get("recent_turns") or [])

    if len(facts) > profile.max_facts:
        facts = facts[: profile.max_facts]
    if len(threads) > profile.max_open_threads:
        threads = threads[: profile.max_open_threads]

    # Prefer compact thread records
    compact_threads = []
    for t in threads:
        if isinstance(t, dict):
            compact_threads.append({"id": t.get("id"), "title": _clip(str(t.get("title") or ""), 120)})
        else:
            compact_threads.append(_clip(str(t), 120))

    # Compact recent dialogue (byte-aware ring is applied in state; re-clip here)
    compact_recent: list[dict[str, Any]] = []
    for t in recent:
        if not isinstance(t, dict):
            continue
        compact_recent.append(
            {
                "user": _clip(str(t.get("user") or ""), 200),
                "answer": _clip(str(t.get("answer") or ""), 280),
                **(
                    {"ts": str(t["ts"])}
                    if t.get("ts")
                    else {}
                ),
            }
        )

    out["facts"] = [_clip(str(x), 200) for x in facts]
    out["open_threads"] = compact_threads
    out["recent_turns"] = compact_recent
    # Bound user input — edge tokens and adversarial paste
    out["user_input"] = _clip(str(out.get("user_input") or ""), 800)

    # Clip long goals in digest
    digest = dict(out.get("state_digest") or {})
    if "goal" in digest:
        digest["goal"] = _clip(str(digest["goal"]), 240)
    if "design_intent" in digest:
        digest["design_intent"] = _clip(str(digest["design_intent"]), 420)
    if "operator_name" in digest:
        digest["operator_name"] = _clip(str(digest["operator_name"]), 40)
    out["state_digest"] = digest

    constraints = dict(out.get("constraints") or {})
    constraints["max_words"] = min(
        int(constraints.get("max_words") or profile.max_answer_words),
        profile.max_answer_words,
    )
    out["constraints"] = constraints

    size = packet_byte_size(out)
    if size > profile.max_packet_bytes:
        # Aggressive trim: drop repair prose first, then oldest recent turns,
        # then facts from the end (fail-closed BudgetError only as last resort)
        if "repair" in out:
            repair = dict(out["repair"])
            viol = list(repair.get("violations") or [])[:5]
            repair["violations"] = [_clip(v, 80) for v in viol]
            repair["instruction"] = _clip(str(repair.get("instruction") or ""), 160)
            out["repair"] = repair
            size = packet_byte_size(out)

        while size > profile.max_packet_bytes and len(out.get("recent_turns") or []) > 0:
            out["recent_turns"] = list(out["recent_turns"])[1:]  # drop oldest
            size = packet_byte_size(out)

        while size > profile.max_packet_bytes and len(out.get("facts") or []) > 2:
            out["facts"] = list(out["facts"])[:-1]
            size = packet_byte_size(out)

        while size > profile.max_packet_bytes and len(out.get("open_threads") or []) > 1:
            out["open_threads"] = list(out["open_threads"])[:-1]
            size = packet_byte_size(out)

        if size > profile.max_packet_bytes and strict:
            raise BudgetError(
                f"arrival packet {size}B exceeds profile {profile.profile_id} "
                f"max_packet_bytes={profile.max_packet_bytes}"
            )

    out["_edge"] = {
        "profile_id": profile.profile_id,
        "packet_bytes": packet_byte_size(out),
        "max_packet_bytes": profile.max_packet_bytes,
        "num_ctx": profile.num_ctx,
        "one_model_only": profile.one_model_only,
    }
    return out


class BudgetError(RuntimeError):
    """Raised when an edge budget would be violated."""


def host_arch() -> str:
    return getattr(sys, "platform", "unknown") + "/" + (
        # platform.machine without importing if possible
        __import__("platform").machine()
    )


def edge_status_report(profile: EdgeProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "target_device": profile.target_device,
        "host_arch": host_arch(),
        "profile_arch": profile.arch,
        "ram_gb_budget": profile.ram_gb,
        "num_ctx": profile.num_ctx,
        "model_default": profile.model,
        "max_packet_bytes": profile.max_packet_bytes,
        "keep_alive": profile.keep_alive,
        "one_model_only": profile.one_model_only,
        "estimated_working_set_mb": profile.estimated_working_set_mb,
        "estimated_headroom_mb": profile.headroom_mb(),
        "stream": profile.stream,
        "cloud": profile.cloud,
        "notes": profile.notes,
    }


def _clip(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)] + "…"
