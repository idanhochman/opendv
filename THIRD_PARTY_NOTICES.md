# Third-party software

opendv runs these tools as separate programs or installs them as Python
dependencies; it does not link them into its own code. The reference Docker
image (`docker/Dockerfile`) redistributes them, so their licenses apply to the
image's contents. Licenses below are from memory of each project and must be
checked against the exact versions before a release.

| Component | Version in image | License (verify) |
|---|---|---|
| Verilator | 5.052 | LGPL-3.0-only OR Artistic-2.0 |
| cocotb, cocotb-bus | 2.1.0, 0.3.0 | BSD-3-Clause |
| cocotb-coverage | 2.0 | BSD-2-Clause |
| cocotbext-axi | 0.1.28 | MIT |
| PyYAML | 6.0.3 | MIT |
| pytest | 9.1.1 | MIT |
| lcov | Ubuntu 24.04 package | GPL-2.0-or-later |
| Ubuntu 24.04 base packages | - | various, see `/usr/share/doc/*/copyright` in the image |

Surfer and GTKWave are not part of the image; they are used on the host.
