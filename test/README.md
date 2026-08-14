# Test Assets

This directory contains runnable examples and read-only consistency checks.

## Contents

- `instances/`: small SMT-LIB v2 formulas for manual runs.
- `configs/`: parallel and distributed JSON examples.
- `output/`: generated launcher output.
- `test_partition_tree_invariants.py`: partitioner-UNSAT children, locally
  delegated regions, and Full-UNSAT promotion in parallel and distributed
  trees.
- `test_prebuilt_package.py`: redistributed binaries, checksums, licenses,
  source/prebuilt script identity, and delegated-node state.
- `validate_evidence.py`: benchmark and result inventories, CPU records and
  collector identity, and all reader-facing parallel, distributed,
  filtered no-eligible-Boolean-atom, and mechanism summaries.

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
repository root. Update `formula_file` and `output_dir`, and, for distributed
runs, update `network_subnet`, `worker_node_ips`, and `worker_node_cores` before
using them on another machine or cluster.

The launcher accepts the configured paths as provided. Relative paths are
resolved against the current working directory. Absolute paths can still be
useful for multi-node runs because every MPI rank must be able to resolve the
same input and output locations consistently.

The example configurations keep `bicp_enabled` and
`clause_reduction_enabled` set to `true`, which matches the default full
AriParti configuration. Set these fields to `false` only for controlled
ablation runs. Selecting `bicp_enabled: false` additionally requires the
explicit `"ablation": {"allow_no_bicp_ablation": true}` opt-in.

The backend names in the examples identify the solver versions used for the
reported runs. The repository's Linux x86-64 package redistributes the
corresponding license-audited upstream binaries. The prebuilt launcher resolves
them under `linux-pre_built/binaries/`; `build.py` copies them into
`bin/binaries/` for a source-built package. See `THIRD_PARTY_NOTICES.md` for
provenance, licenses, and checksums.
