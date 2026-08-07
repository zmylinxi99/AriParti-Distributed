# Linux Prebuilt Package

This directory contains a prebuilt AriParti launcher package for Linux systems.

## Contents

- Python launcher and orchestration scripts are stored directly in this
  directory.
- The AriParti partitioner executable is stored under `binaries/`.
- Backend SMT solver executables are not redistributed in the FMSD journal
  artifact. Obtain a compatible solver from its official distribution, review
  its license, and copy it to `bin/binaries/` after running `build.py`.

Current binaries:

| Binary | Path |
| --- | --- |
| Partitioner | `binaries/partitioner-bin` |

The example configurations retain the backend executable names used for the
reported experiments (`opensmt-2.5.2-bin` and `z3-4.12.1-bin`). To run an
example, install the corresponding official solver build under that name or
change `base_solver` to the executable you supplied.
