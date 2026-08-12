# Linux Prebuilt Package

This directory packages the AriParti launcher, partitioner, and backend solvers
for Linux x86-64. It requires Python 3.8 or later, Open MPI, `python3-mpi4py`,
and GLIBC 2.30 or later. The launcher uses Linux-specific CPU affinity and Open
MPI options.

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

From the repository root, run the parallel example with:

```bash
python3 linux-pre_built/AriParti_launcher.py test/configs/parallel-64.json
```

The launcher resolves `base_solver` in this directory's `binaries/` folder. To
use another solver build, place its executable there and update `base_solver`.

Running `python3 build.py` from the repository root instead compiles the
partitioner and creates a separate `bin/` package. The build copies the three
bundled backend executables into `bin/binaries/`.
