"""Small HTML helpers shared by the regression site and the code-coverage pages."""

import html
from importlib import resources

esc = html.escape


def read_asset(package: str, name: str) -> str:
    """A file from the `assets` folder next to a package's modules."""
    return (resources.files(package) / "assets" / name).read_text()


def pct(hit: int, size: int) -> float:
    return 100 * hit / size if size else 100.0


def bar(hit: int, size: int) -> str:
    p = pct(hit, size)
    cls = "ok" if hit == size else ("warn" if p >= 80 else "bad")
    return f'<span class="bar {cls}"><i style="width:{p:.1f}%"></i></span>'
