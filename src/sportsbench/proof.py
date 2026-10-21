"""Proof of pre-kickoff: hash the exact brief so a prediction can't be edited
after the result is known. The same anti-hindsight discipline modelfights.com
publishes publicly.
"""
from __future__ import annotations

import hashlib


def prompt_hash(system: str, user: str) -> str:
    """Deterministic SHA-256 over the exact prompt the model saw."""
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


def short(h: str, n: int = 12) -> str:
    return h[:n]
