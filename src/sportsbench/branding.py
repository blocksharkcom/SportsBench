"""Tasteful attribution. One dim line; never blocks anything; always suppressible."""
from __future__ import annotations

import os

SITE = "https://modelfights.com"


def banner(enabled: bool = True) -> str:
    if not enabled or os.environ.get("SPORTSBENCH_NO_BANNER"):
        return ""
    return (f"[dim]SportsBench · 45+ frontier models graded live, in public → "
            f"{SITE}[/dim]")


def show(console, enabled: bool = True) -> None:
    b = banner(enabled)
    if b:
        console.print(b)
