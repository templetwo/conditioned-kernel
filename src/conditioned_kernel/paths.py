"""Resolve repo-relative paths."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Return repository root (parent of src/)."""
    return Path(__file__).resolve().parents[2]


def default_state_dir() -> Path:
    return repo_root() / "state"


def default_logs_dir() -> Path:
    return repo_root() / "logs"
