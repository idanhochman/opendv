"""Verilator code coverage as data: parse a merged coverage.dat, merge toggle directions, summarize, list the holes."""

import re
from collections import defaultdict
from pathlib import Path



LOW = 10  # hits below this are shown as "thin" (Verilator's own default threshold)


def parse_dat(path: Path) -> list[dict]:
    """One dict per coverage point: type, file, line, signal/comment, hier, count.

    Record format: C '\\x01key\\x02value\\x01key\\x02value...' count
    """
    points = []
    for raw in path.read_text().splitlines():
        if not raw.startswith("C '"):
            continue
        body, _, count = raw[3:].rpartition("' ")
        fields = {}
        for part in body.split("\x01"):
            if "\x02" in part:
                k, v = part.split("\x02", 1)
                fields[k] = v
        page = fields.get("page", "")
        points.append({
            "type": page.split("/")[0].removeprefix("v_"),
            "file": fields.get("f", ""),
            "line": int(fields.get("l", 0)),
            "what": fields.get("o", ""),
            "hier": fields.get("h", ""),
            "lines": fields.get("S", ""),
            "count": int(count),
        })
    return _merge_toggle_directions(points)


_DIR = re.compile(r"(.*):([01])->([01])")


def _merge_toggle_directions(points: list[dict]) -> list[dict]:
    """Verilator >= 5.040 emits two toggle points per bit (`sig[3]:0->1` and
    `:1->0`); 5.020 emitted one. Merge them into one point per bit whose
    count is the smaller direction, so a bit counts as toggled only once it
    has gone both ways. `rise`/`fall` keep the per-direction counts."""
    out, merged = [], {}
    for p in points:
        m = _DIR.fullmatch(p["what"]) if p["type"] == "toggle" else None
        if not m:
            out.append(p)
            continue
        key = (p["file"], p["line"], p["hier"], m.group(1))
        q = merged.get(key)
        if q is None:
            q = merged[key] = {**p, "what": m.group(1), "rise": 0, "fall": 0}
            out.append(q)
        q["rise" if m.group(2) == "0" else "fall"] += p["count"]
        q["count"] = min(q["rise"], q["fall"])
    return out


def summarize(points: list[dict]) -> dict:
    by = defaultdict(lambda: [0, 0])
    for p in points:
        by[p["type"]][1] += 1
        by[p["type"]][0] += p["count"] > 0
    return {t: {"hit": h, "size": s} for t, (h, s) in sorted(by.items())}


def holes(points: list[dict]) -> list[dict]:
    return [p for p in points if p["count"] == 0]


def bit_key(what):
    m = re.fullmatch(r"(.+?)\[(\d+)\]", what)
    return (m.group(1), int(m.group(2))) if m else (what, None)


def by_file_line(points):
    """{file: {line: [merged points covering that line]}}. Points are merged
    across instances (same type/line/what/range -> counts summed), so the
    source view shows the design as a whole, not one instance."""
    merged = {}
    for p in points:
        k = (p["file"], p["type"], p["line"], p["what"], p["lines"])
        if k in merged:
            merged[k]["count"] += p["count"]
        else:
            merged[k] = dict(p)
    files = defaultdict(lambda: defaultdict(list))
    for p in merged.values():
        covered = {p["line"]} if p["type"] == "toggle" else (ranges(p["lines"]) or {p["line"]})
        for n in covered:
            files[p["file"]][n].append(p)
    return files


def line_status(pts):
    hit = [p["count"] > 0 for p in pts]
    return "ok" if all(hit) else ("z" if not any(hit) else "part")


def ranges(spec: str) -> set[int]:
    """'52-55,57' -> {52,53,54,55,57}"""
    out = set()
    for part in filter(None, spec.split(",")):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out
