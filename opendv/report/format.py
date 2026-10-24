"""Formatting helpers for the dashboard pages: times, cards, test links."""

import re
from pathlib import Path

from ..htmlkit import esc


def rel(path: str | Path, base: Path) -> str:
    """Link target relative to the run dir so the run dir can be moved."""
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def fmt_t(ns: float) -> str:
    """Sim time in a readable unit: 0.001 ns -> '1 ps', 250 -> '250 ns', 100000 -> '100 us'."""
    for unit, scale in (("ps", 1e-3), ("ns", 1.0), ("us", 1e3), ("ms", 1e6)):
        v = ns / scale
        if abs(v) < 999.5 or unit == "ms":
            break
    s = f"{v:.2f}" if abs(v) < 10 else (f"{v:.1f}" if abs(v) < 100 else f"{v:.0f}")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"{s} {unit}"


def fmt_wall(sec: float) -> str:
    """Wall-clock time in a readable unit: 0.4 -> '400 ms', 1.5 -> '1.5 s', 125 -> '2m 05s', 3900 -> '1h 05m'."""
    if sec < 0.9995:
        return f"{sec * 1000:.0f} ms"
    if sec < 9.95:
        return f"{sec:.1f} s"
    total = round(sec)
    if total < 60:
        return f"{total} s"
    if total < 3600:
        return f"{total // 60}m {total % 60:02d}s"
    mins = round(sec / 60)
    return f"{mins // 60}h {mins % 60:02d}m"


def card(label: str, value: str, sub: str = "", cls: str = "") -> str:
    return (f'<div class="card {cls}"><div class="lbl">{esc(label)}</div>'
            f'<div class="val">{value}</div><div class="sub">{sub}</div></div>')


def norm_msg(m: str) -> str:
    """Group failures that differ only by data values (hex numbers, addresses)."""
    return re.sub(r"0x[0-9a-fA-F]+", "0x#", m or "(no message)")


COPY_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5">'
             '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5v-1a1 1 0 0 0-1-1h-7a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h1"/></svg>')


CHECK_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">'
              '<path d="M3 8.5l3 3 7-7"/></svg>')


def test_href(name: str) -> str:
    return f"tests/{name}.html"
