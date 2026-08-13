# CPU-Utilization Measurements

This directory contains 79,387 per-instance observations from seven
CPU-instrumented solver runs. Each row pairs one CPU-utilization measurement
with the status and runtime observed in the same run.

The collector, four-server configuration, exact sampling and aggregation
semantics, and collector checksums are available under
[`collection/`](collection/README.md).

## How to Interpret the Measurements

Each row is one matched CPU, status, and runtime observation from the same
instrumented run. `manifest.csv` defines the benchmark and configuration scope
of each file.

## Row Schema

The CSV files have no header row and use the following schema:

```text
benchmark,status,runtime_seconds,cpu_usage_percent
```

- `benchmark` is the relative SMT-LIB benchmark identifier.
- `status` is the solver outcome: `sat`, `unsat`, or `failed`.
- `runtime_seconds` is the runtime of the CPU-instrumented run.
- `cpu_usage_percent` is the run-level CPU-utilization value. It is the
  equal-server mean of per-server temporal means after host-wide samples are
  normalized to each server's 128-slot allocation; see the collection
  documentation for the exact formula.

## Inventory and Validation

`manifest.csv` records the file path, benchmark-list size, row count,
status distribution, and SHA-256 identity for every run. The public evidence
validator checks that:

- all seven inventoried files are present and no unlisted CPU CSV is present;
- every row has four fields and a supported status;
- runtimes are finite and non-negative, and CPU-utilization values are finite
  and within 0--100%;
- benchmark identifiers are unique within a file and belong to the stated
  benchmark list;
- row and status counts match the manifest; and
- every file matches the SHA-256 value in the manifest.

The validator also checks the archived collector files against
`collection/SHA256SUMS` and checks the four-server, 128-slot
configuration used by the normalization.

Run the validation from the repository root:

```bash
python3 test/validate_evidence.py
```

Recompute the seven per-run runtime-weighted means and the three pooled
profiles directly from the archived CSVs with:

```bash
python3 experiment-results/distributed/cpu-usage/summarize.py --check
```

The command prints a machine-readable CSV summary. With `--check`, it also
checks the two-decimal per-run means used in the manuscript and the pooled
observation counts used in the response letter.
