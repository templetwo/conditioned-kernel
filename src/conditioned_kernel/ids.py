"""Small id helpers."""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def short_token(n: int = 4) -> str:
    return secrets.token_hex(n)


def make_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}_{short_token(3)}"


def packet_id() -> str:
    return make_id("pkt")


def candidate_id() -> str:
    return make_id("cand")


def receipt_id() -> str:
    return make_id("rcpt")


def monotonic_ms() -> int:
    return int(time.time() * 1000)
