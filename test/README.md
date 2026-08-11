# Test Assets

This directory contains small SMT-LIB instances and example configuration files.

## Contents

- `instances/` contains SMT-LIB v2 formulas for quick manual checks.
- `configs/` contains example JSON configurations.
- `output/` is reserved for generated output.
- `test_partition_tree_invariants.py` checks explicit partitioner-UNSAT
  children, proof-UNSAT versus locally delegated regions, and parallel and
  distributed Full-UNSAT promotion without starting MPI processes or solver
  runs.
- `test_prebuilt_package.py` checks the redistributed binary inventory,
  checksums, license files, source/prebuilt script identity, and a delegated-node
  state invariant.
- `validate_evidence.py` validates benchmark/result inventories, validates all
  CPU-instrumented records, and recomputes all reader-facing parallel,
  distributed, pure-conjunction, and full-list ablation summaries from the
  current repository snapshot.

Run all read-only checks from the repository root with:

```bash
python3 test/validate_evidence.py
python3 test/test_partition_tree_invariants.py
python3 test/test_prebuilt_package.py
```

These commands do not launch MPI jobs or backend solver processes. The evidence
validator may take several seconds because it scans 916,851 comparison records,
79,387 CPU-instrumented records, and verifies the ablation bundle checksums.

## Configuration Notes

The JSON files under `configs/` are examples intended to be launched from the
repository root. Update `formula_file`, `output_dir`, `network_subnet`,
`worker_node_ips`, and `worker_node_cores` before using them on another
machine or cluster.

The launcher accepts the configured paths as provided. Relative paths are
resolved against the current working directory. Absolute paths can still be
useful for multi-node runs because every MPI rank must be able to resolve the
same input and output locations consistently.

The example configurations keep `bicp_enabled` and
`clause_reduction_enabled` set to `true`, which matches the default full
AriParti configuration. Set these fields to `false` only for controlled
ablation runs.

The backend names in the examples identify the solver versions used for the
reported runs. The Linux x86-64 journal artifact redistributes the corresponding
license-audited upstream binaries; `build.py` copies them into `bin/binaries/`.
See `THIRD_PARTY_NOTICES.md` for provenance, licenses, and checksums. To use a
different build, place it in `bin/binaries/` and update `base_solver`.
