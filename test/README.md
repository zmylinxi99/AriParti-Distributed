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

Run the state-transition checks from the repository root with:

```bash
python3 test/test_partition_tree_invariants.py
```

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
reported runs. Backend executables are not redistributed in the journal
artifact; install an official solver build in `bin/binaries/` and either use
the recorded filename or update `base_solver` before launching an example.
