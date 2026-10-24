# opendv

A plug-and-play open-source design-verification stack: **Verilator** + **cocotb**
with multi-seed regression, merged functional and code coverage, and a static
HTML dashboard. The toolchain ships as a Docker image so versions always match.

**Status: pre-alpha.** Verilator 5.052, cocotb 2.1.0, cocotb-coverage 2.0 (pinned in `docker/`).

## Try it

```bash
export PATH="$PWD/bin:$PATH"                           # the `opendv` wrapper runs the container

cd examples/regbus
opendv targets                                         # router, regfile, fabric, top
opendv regress --all --seeds 4                         # the whole hierarchy, random seeds
opendv run fabric:test_irq_routing                     # or one test, to debug it
opendv help                                           # commands and examples; `opendv help run` for one command (works anywhere)
open regress/index.html                                # the dashboard (any browser)
```

The first run downloads the toolchain image (`ghcr.io/idanhochman/opendv`) automatically.
To use a locally built image instead, e.g. after changing `docker/`:
`docker build -t opendv:dev -f docker/Dockerfile .` then `export OPENDV_IMAGE=opendv:dev`.

## Using it

A project is a tree of targets. Each target is one toplevel with its file list and
cocotb tests, described by an `opendv.yaml` next to it; a project-level `opendv.yaml`
lists the targets. See `examples/regbus/` (router and register file blocks, a fabric
subsystem that instantiates them, and a chip top).

Two commands run things. **`opendv run`** is for debugging: one test, one seed, waves on.
**`opendv regress`** is the regression: targets, many tests, many seeds, merged coverage and the dashboard.

```bash
# debug one test
opendv run fabric:test_irq_routing            # random seed (printed); waves on
cd fabric && opendv run test_irq_routing      # a test of the target you are standing in
opendv run fabric:test_irq_routing --seed 17  # replay a seed
opendv run fabric:test_irq_routing --tag 2    # keep the previous results, build and run afresh
opendv run fabric:test_irq_routing --no-waves

# regress
opendv regress router regfile                 # some targets
opendv regress fabric:test_irq*               # tests by glob, over several seeds
opendv regress --all --code-cov               # + Verilator line/toggle/branch coverage
opendv regress --all --waves                  # + FST waveforms (off by default; `waves: true` in opendv.yaml, project defaults or a target)
opendv regress --all --master-seed 123        # replay a regression exactly
opendv regress top --seed-list 17 99          # fixed seeds
```

- **`opendv run` keeps everything for a test in one folder:**
  `<project>/sim/<target>/<test>/build_<tag>/` holds the compiled model, `sim.log`, `results.xml`,
  `dump.fst` and `coverage.yml`. The default tag is `1`, so running again overwrites it; pass
  `--tag <tag>` for a fresh build and fresh results next to it. Each test compiles its own copy of
  the design the first time. Nothing is added to the regression history or the dashboard.
- **Every regression test runs in its own simulator process**, once per seed, so each starts from
  power-on and has its own log, waveform and coverage. Seeds are random by default and drawn per
  test; the master seed and every seed are recorded, and each failure in the dashboard has a
  one-test repro command (`opendv run`).
- **Run from anywhere in the project.** The wrapper mounts the project root and keeps your
  working directory.
- **Tests write `coverage.yml`** (cocotb-coverage) into the run directory when a target sets
  `coverage.functional`, at the end of their simulation; regression results go to
  `<project>/regress/<timestamp>/<target>/<test>/seed_<n>/`.

## Layout

`opendv/` is the Python package (`config`, the two flows `run` and `regress`, the `simulator`, `results` and
`coverage` they use, the `report/` dashboard and the `codecov/` code-coverage pages), `docker/` the toolchain image,
`bin/opendv` the wrapper, `examples/` runnable projects, `tests/` unit tests (`pytest`).

## License

Apache-2.0. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
