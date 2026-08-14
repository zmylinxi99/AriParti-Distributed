# Experiment Results

This directory archives the per-instance records and derived summaries used by
the AriParti-Distributed evaluation. Start with:

- `manifest.csv` for the result-directory and record inventory;
- `metadata.json` for aggregation rules and evaluation settings; and
- the family-specific README beside a result set for its scope and schema.

Validate the archive from the repository root with:

```bash
python3 test/validate_evidence.py
```

The command reads the archived files and requires no benchmark checkout, MPI
job, or solver run.

## Layout

```text
experiment-results/
├── metadata.json  # Archive-wide semantics and metadata availability
├── manifest.csv   # Result-directory and record inventory
├── sync_sumups.py # Narrow checker/regenerator for text summaries
├── distributed/
│   ├── data/       # Per-instance distributed results in CSV format
│   ├── cpu-usage/  # Instrumented runs and collection tool
│   └── sumup/      # Human-readable summary tables
├── ablation/
│   └── full-list-p8-1200s/         # Checksum-validated ablation evidence bundle
└── parallel/
    ├── QF_*/       # Per-instance parallel results and per-run summaries
    ├── pure-conjunction-p16-summary.csv
    ├── pure-conjunction-opensmt2-p16-summary.csv
    └── *-results-sumup.txt
```

Archived file counts:

| Area | Files |
| --- | ---: |
| `distributed/data/**/*.csv` | 22 |
| `distributed/cpu-usage/QF_*/*.csv` | 7 |
| `distributed/sumup/*.txt` | 4 |
| `parallel/**/*.csv` | 59 |
| `parallel/**/*-sumup.txt` | 61 |
| `ablation/full-list-p8-1200s/*.csv` | 7 |

`distributed/cpu-usage/manifest.csv` inventories the seven instrumented runs:
79,387 records in total, with status counts and SHA-256 values for every CSV.
The mechanism-comparison bundle under `ablation/full-list-p8-1200s/` contains
eight aggregate comparisons, the corresponding manuscript table, metadata,
source identities, and checksums.

## Data Format

The per-instance CSV files under `distributed/data/` and `parallel/QF_*/` have
no header row. The observed columns are:

```text
benchmark,status,runtime_seconds
```

The CPU-usage CSV files under `distributed/cpu-usage/` come from dedicated
instrumented solver runs. They have no header row, and the columns are:

```text
benchmark,status,runtime_seconds,cpu_usage_percent
```

Each row is one matched CPU, status, and runtime observation from an
instrumented run. Analyze the rows within the file and benchmark scope defined
in `distributed/cpu-usage/manifest.csv`. See `distributed/cpu-usage/README.md` for
measurement details and `distributed/cpu-usage/collection/README.md` for the
collector's sampling, normalization, and aggregation rules.
`distributed/cpu-usage/summarize.py --check` recomputes the runtime-weighted
means and pooled observation counts used in the manuscript and response.

## Aggregation Rules

The summary files under `distributed/sumup/` and the top-level
`parallel/*-results-sumup.txt` files are human-readable tables with the columns:

```text
solver,sat,unsat,solved,failed,PAR-2
```

The per-run summary files under `parallel/QF_*/` are key-value text files with
the observed keys:

```text
sat,unsat,solved,failed,PAR-2
```

For the parallel and distributed aggregates used by the current manuscript,
PAR-2 is computed from the full-precision per-instance CSV runtimes.
Non-decisive runs are assigned 2,400 seconds, and the total is rounded to the
nearest whole second only after summation. The per-instance CSV files define
those PAR-2 values.

The leader checks the 1,200-second timeout between communication cycles, so a
completion can exceed the cutoff by the collection and enforcement latency.
Aggregation uses the resulting status and runtime: `sat` and `unsat` remain
decisive. The archive contains two decisive results above 1,200 seconds;
`metadata.json` states this count and `test/validate_evidence.py` checks the
count.

Check all per-run and aggregate summaries against the per-instance CSVs with:

```bash
python3 experiment-results/sync_sumups.py --check
```

To regenerate any stale summary files with the same documented rule, use
`--write` instead of `--check`.

## Derived Tables

`parallel/pure-conjunction-p16-summary.csv` is a derived summary whose
historical filename refers to the filtered lists with no eligible Boolean
partitioning atom after AriParti's preprocessing. It records per-theory QF_LRA,
QF_LIA, QF_NRA, and QF_NIA rows together with retained linear and nonlinear
aggregate rows. Per-theory counts come from joining each filtered benchmark
list with its p16 per-configuration CSVs. Only `sat` and `unsat` are decisive. The
`ariparti_faster` and `cvc5_faster` fields compare runtimes only when both
configurations are decisive; `equal_runtime` records exact ties.
`neither_solved` records the remaining non-decisive pairs.

`parallel/pure-conjunction-opensmt2-p16-summary.csv` applies the same criterion,
join, and outcome semantics to the two linear theories supported by the
OpenSMT2 comparison. It supports the OpenSMT2 linear panel and corresponding
aggregate counts in the manuscript.

The full-list result directory uses documented headers for each file.
`summary.csv` records twelve theory-by-configuration rows; `delta.csv` records
eight Full-versus-Disabled comparisons. `table.tex` renders all eight
theory--mechanism comparisons. See its README and `result-metadata.json` for
the scope, result meaning, and validation command.

## Archive Scope

- The parallel and distributed archive covers QF_LRA, QF_LIA, QF_NRA, and
  QF_NIA; distributed data include the QF_NRA 32--512-slot sweep.
- CPU-utilization results are 79,387 observations from seven instrumented runs.
  Their manifest defines each file's benchmark and configuration scope, and
  the collector defines how each run-level percentage was sampled,
  normalized, and averaged over four servers.
- The mechanism bundle covers all four artifact lists at p8 with a 1,200-second
  timeout and one run per benchmark and configuration. It contains the
  aggregate tables, deltas, provenance data, and integrity checks.
- `metadata.json` defines the benchmark, solver, slot-budget, timeout, CPU
  measurement, and aggregation semantics used by the result archive.

## What the Validator Checks

The public checker verifies:

- all eight benchmark-list manifest entries, list sizes, and duplicate freedom;
- all thirteen result-manifest entries and their CSV inventories;
- schema, status, runtime, uniqueness, and full-list membership for 79 raw
  result CSVs (916,851 records);
- schema, status, runtime, CPU value, uniqueness, benchmark membership, status
  counts, and SHA-256 identity for seven CPU-instrumented CSVs (79,387 records);
- SHA-256 identity and normalization constants for the CPU collector;
- all 57 per-run parallel summaries and all 79 rows in the parallel/distributed
  aggregate tables using the documented PAR-2 rule;
- all nine derived rows for the filtered no-eligible-Boolean-atom comparisons; and
- all full-list ablation checksums, row invariants, deltas, benchmark counts,
  and launcher/partitioner identities.
