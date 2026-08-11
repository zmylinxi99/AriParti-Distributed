# Experiment Results

This directory stores recorded results for AriParti-Distributed experiments.
Each result family documents the configuration metadata available for that
evidence.

Start with `metadata.json` for the archive-wide aggregation rule and a precise
inventory of which legacy configuration fields are known or unavailable. Run
the comprehensive current-snapshot validator from the repository root with:

```bash
python3 test/validate_evidence.py
```

The validator is read-only and does not consult Git history, start MPI, invoke a
solver, or require a local SMT-LIB benchmark checkout.

## Layout

```text
experiment-results/
├── metadata.json  # Archive-wide semantics and metadata availability
├── manifest.csv   # Result-directory and record inventory
├── sync_sumups.py # Narrow checker/regenerator for text summaries
├── distributed/
│   ├── data/       # Per-instance distributed results in CSV format
│   ├── cpu-usage/  # Validated, CPU-instrumented per-instance runs
│   └── sumup/      # Human-readable summary tables
├── ablation/
│   └── full-list-p8-1200s/         # Checksum-validated ablation evidence bundle
└── parallel/
    ├── QF_*/       # Per-instance parallel results and per-run summaries
    ├── pure-conjunction-p16-summary.csv
    ├── pure-conjunction-opensmt2-p16-summary.csv
    └── *-results-sumup.txt
```

Current file counts:

| Area | Files |
| --- | ---: |
| `distributed/data/**/*.csv` | 22 |
| `distributed/cpu-usage/QF_*/*.csv` | 7 |
| `distributed/sumup/*.txt` | 4 |
| `parallel/**/*.csv` | 59 |
| `parallel/**/*-sumup.txt` | 61 |
| `ablation/full-list-p8-1200s/*.csv` | 7 |

`manifest.csv` records the current result directories, CSV file counts, and
per-CSV record counts where the count is uniform for that directory.
`distributed/cpu-usage/manifest.csv` gives the exact per-file inventory for the
seven CPU-instrumented runs: 79,387 records in total, with status counts and
SHA-256 values for every CSV.

`metadata.json` separates recorded facts from unavailable legacy details. In
particular, the legacy parallel/distributed files identify solver versions and
slot configurations through their campaign labels, but do not retain a complete
machine inventory, evaluated Git revision, binary hashes, or random-seed
metadata. These fields are marked unavailable rather than reconstructed.

The mechanism-comparison archive is in `ablation/full-list-p8-1200s/`. It
contains eight aggregate comparisons and a complete eight-row manuscript
table, together with machine-readable result metadata, source provenance, and
checksums. It is the aggregate-level evidence bundle for the mechanism-ablation
study.

## Data Format

The per-instance CSV files under `distributed/data/` and `parallel/QF_*/` have
no header row. The observed columns are:

```text
benchmark,status,runtime_seconds
```

The CPU-usage CSV files under `distributed/cpu-usage/` are valid observations
from dedicated CPU-instrumented solver runs. They have no header row, and the
columns are:

```text
benchmark,status,runtime_seconds,cpu_usage_percent
```

CPU measurement requires instrumentation and can produce normal run-to-run
variation in solver scheduling, status, and runtime. The CPU value and its
accompanying status and runtime form one self-contained observation and are the
authoritative records for this campaign. The runs used normal experimental
operation without intentionally added external workload. The records are
suitable for direct CPU-utilization analysis and reporting within the file and
benchmark scope recorded in `distributed/cpu-usage/manifest.csv`. See
`distributed/cpu-usage/README.md` for the complete interpretation and public
validation procedure.

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

The 1,200-second value is the nominal leader-side cutoff. The leader checks the
cutoff between communication cycles, so collection and cutoff-enforcement
latency can make a recorded completion time exceed 1,200 seconds. Aggregation
uses the recorded status as authoritative: `sat` and `unsat` remain decisive
and retain their recorded runtime. The current archive contains exactly two
such decisive records above 1,200 seconds; `metadata.json` records the count and
`test/validate_evidence.py` verifies it. This rule preserves the current
per-instance baseline instead of silently relabeling records.

Check all per-run and aggregate summary files against the current per-instance
CSVs with:

```bash
python3 experiment-results/sync_sumups.py --check
```

To regenerate any stale summary files with the same documented rule, use
`--write` instead of `--check`.

`parallel/pure-conjunction-p16-summary.csv` is a derived summary. It records
per-theory QF_LRA, QF_LIA, QF_NRA, and QF_NIA rows together with retained
linear and nonlinear aggregate rows. The current outcome table independently
recovers the per-theory counts by joining each filtered list with the
corresponding p16 per-configuration CSVs. The
recorded semantics treat only `sat` and `unsat` as decisive. The
`ariparti_faster` and `cvc5_faster` fields compare runtimes only when both
configurations are decisive; `equal_runtime` records exact ties.
`neither_solved` records the remaining non-decisive pairs.

`parallel/pure-conjunction-opensmt2-p16-summary.csv` applies the same join and
outcome semantics to the two linear theories supported by the recorded
OpenSMT2 comparison. It supports the OpenSMT2 linear panel and the corresponding
aggregate counts in the manuscript.

The full-list result directory uses documented headers for each file.
`summary.csv` records twelve theory-by-configuration rows; `delta.csv` records
eight Full-versus-Disabled comparisons. `table.tex` renders all eight
theory--mechanism comparisons. See its README and `result-metadata.json` for
the scope, result meaning, and validation command.

## Evidence Scope

- The CPU-utilization campaign contains 79,387 validated observations from
  seven dedicated instrumented runs. Each file is directly usable within the
  exact scope recorded in `distributed/cpu-usage/manifest.csv`.
- The current complete-configuration performance tables use the QF_LRA,
  QF_LIA, QF_NRA, and QF_NIA parallel and distributed data, including the
  QF_NRA 32--512-slot scaling sweep.
- `sat` and `unsat` are the decisive result labels. All other recorded labels
  contribute to the unresolved count and receive the PAR-2 penalty specified
  above.
- The evaluation protocol uses a 1,200-second cutoff. The full-list mechanism
  bundle records this value in its machine-readable metadata and validates it
  against each aggregate row.
- The source campaigns for the full-list bundle cover all four artifact lists,
  p8, a 1,200-second timeout, and one recorded result per benchmark instance
  and configuration. The bundle provides validated aggregate,
  status-distribution, audit, provenance, and checksum artifacts for both
  mechanism comparisons on every theory.

## What the Validator Checks

The public checker verifies:

- all eight benchmark-list manifest entries, list sizes, and duplicate freedom;
- all thirteen result-manifest entries and their CSV inventories;
- schema, status, runtime, uniqueness, and full-list membership for 79 raw
  result CSVs (916,851 records);
- schema, status, runtime, CPU value, uniqueness, benchmark membership, status
  counts, and SHA-256 identity for seven CPU-instrumented CSVs (79,387 records);
- all 57 per-run parallel summaries and all 79 rows in the parallel/distributed
  aggregate tables using the documented PAR-2 rule;
- all nine derived pure-conjunction comparison rows; and
- all full-list ablation checksums, row invariants, deltas, benchmark counts,
  and launcher/partitioner identities.
