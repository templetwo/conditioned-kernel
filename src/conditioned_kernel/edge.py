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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EdgeProfile":
        return cls(
            profile_id=str(data["profile_id"]),
            description=str(data.get("description") or ""),
            target_device=str(data.get("target_device") or "unknown"),
            arch=str(data.get("arch") or "any"),
            ram_gb=int(data.get("ram_gb") or 8),
            model=str(data.get("model") or "qwen2.5:0.5b"),
            mode=str(data.get("mode") or "chat_json"),
            num_ctx=int(data.get("num_ctx") or 2048),
            temperature=float(data.get("temperature") or 0.3),
            seed=int(data.get("seed") or 42),
            max_repair=int(data.get("max_repair") or 1),
            keep_alive=str(data.get("keep_alive") if data.get("keep_alive") is not None else "2m"),
            timeout_s=float(data.get("timeout_s") or 90),
            max_packet_bytes=int(data.get("max_packet_bytes") or 6000),
            max_facts=int(data.get("max_facts") or 8),
            max_open_threads=int(data.get("max_open_threads") or 4),
            max_answer_words=int(data.get("max_answer_words") or 120),
            max_log_file_bytes=int(data.get("max_log_file_bytes") or 5_242_880),
            one_model_only=bool(data.get("one_model_only", True)),
            stream=bool(data.get("stream", False)),
            cloud=bool(data.get("cloud", False)),
            sensors=bool(data.get("sensors", False)),
            tools=bool(data.get("tools", False)),
            estimated_model_ram_mb=int(data.get("estimated_model_ram_mb") or 500),
            estimated_substrate_ram_mb=int(data.get("estimated_substrate_ram_mb") or 200),
            notes=str(data.get("notes") or ""),
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
            "cloud": self.cloud,
            "sensors": self.sensors,
            "tools": self.tools,
            "estimated_model_ram_mb": self.estimated_model_ram_mb,
            "estimated_substrate_ram_mb": self.estimated_substrate_ram_mb,
            "notes": self.notes,
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


def packet_byte_size(packet: dict[str, Any]) -> int:
    return len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


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

    out["facts"] = [_clip(str(x), 200) for x in facts]
    out["open_threads"] = compact_threads
    # Bound user input — edge tokens and adversarial paste
    out["user_input"] = _clip(str(out.get("user_input") or ""), 800)

    # Clip long goals in digest
    digest = dict(out.get("state_digest") or {})
    if "goal" in digest:
        digest["goal"] = _clip(str(digest["goal"]), 240)
    out["state_digest"] = digest

    constraints = dict(out.get("constraints") or {})
    constraints["max_words"] = min(
        int(constraints.get("max_words") or profile.max_answer_words),
        profile.max_answer_words,
    )
    out["constraints"] = constraints

    size = packet_byte_size(out)
    if size > profile.max_packet_bytes:
        # Aggressive trim: drop repair prose first, then facts from the end
        if "repair" in out:
            repair = dict(out["repair"])
            viol = list(repair.get("violations") or [])[:5]
            repair["violations"] = [_clip(v, 80) for v in viol]
            repair["instruction"] = _clip(str(repair.get("instruction") or ""), 160)
            out["repair"] = repair
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
