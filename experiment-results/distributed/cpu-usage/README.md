# CPU-Utilization Measurements

This directory contains seven valid CPU-instrumented solver runs and 79,387
per-instance observations. Every CSV row is a self-contained measurement whose
CPU value, status, and runtime are the authoritative records for this campaign.

## Measurement relationship

Collecting CPU utilization requires instrumentation and can produce normal
run-to-run variation in process scheduling, solver status, and runtime. The runs
used normal experimental operation without intentionally added external
workload. The recorded data are suitable for direct CPU-utilization analysis
and reporting within each file's documented benchmark scope.

## Row schema

The CSV files have no header row and use the following schema:

```text
benchmark,status,runtime_seconds,cpu_usage_percent
```

- `benchmark` is the relative SMT-LIB benchmark identifier.
- `status` is the recorded solver outcome: `sat`, `unsat`, or `failed`.
- `runtime_seconds` is the runtime recorded by the CPU-instrumented run.
- `cpu_usage_percent` is the CPU-utilization value recorded by the measurement
  campaign.

The runtime and status belong to the same instrumented observation as the CPU
value. `manifest.csv` defines the exact scope used when analyzing and reporting
each run.

## Inventory and validation

`manifest.csv` records the exact file path, benchmark-list size, row count,
status distribution, and SHA-256 identity for every run. The public evidence
validator checks that:

- all seven inventoried files are present and no unlisted CPU CSV is present;
- every row has four fields and a supported status;
- runtimes and CPU-utilization values are finite and non-negative;
- benchmark identifiers are unique within a file and belong to the stated
  benchmark list;
- row and status counts match the manifest; and
- every file matches its recorded SHA-256 value.

Run the validation from the repository root:

```bash
python3 test/validate_evidence.py
```
