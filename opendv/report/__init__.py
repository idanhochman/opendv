"""The regression dashboard: a static website over all regressions under results_dir.

    <results>/index.html                       all regressions
    <results>/assets/{site.css,site.js,runs.js}
    <results>/<regression>/index.html          one regression: a row per target
    <results>/<regression>/<target>/index.html target overview (+ tests/failures/functional/code/seeds .html)
    <results>/<regression>/<target>/tests/<test>.html   one test across seeds

Plain HTML files, no server needed. The sidebar is drawn by site.js from assets/runs.js, so a new
regression only rewrites that one file. Built by `opendv regress` after every regression;
`opendv report` rebuilds it.
"""

from .site import build_site

__all__ = ["build_site"]
