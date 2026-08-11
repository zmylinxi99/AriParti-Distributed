# Linux Prebuilt Package

This directory contains a prebuilt AriParti launcher package for Linux systems.

## Contents

- Python launcher and orchestration scripts are stored directly in this
  directory.
- The AriParti partitioner executable is stored under `binaries/`.
- Unmodified Linux x86-64 backend SMT solver executables are redistributed for
  the versions used in the evaluation. Their provenance, licenses, and SHA-256
  values are recorded in `../THIRD_PARTY_NOTICES.md` and
  `../third-party-licenses/`.

Current binaries:

| Binary | Path |
| --- | --- |
| Partitioner | `binaries/partitioner-bin` |
| cvc5 1.0.8 | `binaries/cvc5-1.0.8-bin` |
| OpenSMT2 2.5.2 | `binaries/opensmt-2.5.2-bin` |
| Z3 4.12.1 | `binaries/z3-4.12.1-bin` |

`build.py` copies all three backend executables into `bin/binaries/`. To use a
different solver build, place it there and change `base_solver` accordingly.
