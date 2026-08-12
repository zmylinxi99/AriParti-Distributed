# CPU-Utilization Measurements

This directory contains 79,387 per-instance observations from seven
CPU-instrumented solver runs. Each row pairs one CPU-utilization measurement
with the status and runtime observed in the same run.

## How to Interpret the Measurements

Instrumentation and process scheduling can change status and runtime across
runs. Treat each row as one observation rather than combining its CPU value
with a status or runtime from another campaign. The runs used normal
experimental operation without an intentionally added external workload;
`manifest.csv` defines the benchmark and configuration scope of each file.

## Row Schema

The CSV files have no header row and use the following schema:

```text
benchmark,status,runtime_seconds,cpu_usage_percent
```

- `benchmark` is the relative SMT-LIB benchmark identifier.
- `status` is the recorded solver outcome: `sat`, `unsat`, or `failed`.
- `runtime_seconds` is the runtime recorded by the CPU-instrumented run.
- `cpu_usage_percent` is the CPU-utilization value recorded by the measurement
  campaign.

## Inventory and Validation

`manifest.csv` records the file path, benchmark-list size, row count,
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
