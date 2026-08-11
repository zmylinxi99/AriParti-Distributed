# AriParti-Distributed: Distributed and Parallel SMT Solving with Dynamic Variable-Level Partitioning

AriParti-Distributed is an open-source research framework for distributed and parallel Satisfiability Modulo Theories (SMT) solving. It extends the dynamic variable-level partitioning strategy from the CAV 2024 AriParti work into a two-tier Leader–Coordinator–Worker architecture for multi-server experiments.

The framework supports SMT solvers that accept the SMT-LIB v2 format (e.g., Z3, cvc5, OpenSMT2), and the current partitioning heuristic is designed for arithmetic theories. It incorporates Boolean and Interval Constraint Propagation (BICP) for subtask simplification.

- Associated manuscript: *Distributed and Parallel SMT Solving Based on Dynamic Variable-Level Partitioning*
- Project: [AriParti GitHub](https://github.com/shaowei-cai-group/AriParti)
- Distributed version: [AriParti-Distributed GitHub](https://github.com/zmylinxi99/AriParti-Distributed)

The project includes code from the Z3 project (MIT License) and is itself released under the [MIT License](LICENSE.txt).

## Reviewer and Reader Quick Path

The following read-only checks require Python but do not start MPI jobs or
backend solvers:

```bash
python3 test/validate_evidence.py
python3 test/test_partition_tree_invariants.py
python3 test/test_prebuilt_package.py
```

The first command validates the current benchmark/result inventory, recomputes
all 79 parallel and distributed summary rows from 916,851 per-instance records,
validates 79,387 records from seven CPU-instrumented runs, recomputes the nine
pure-conjunction rows, and checks the full-list ablation bundle. See
[`experiment-results/README.md`](experiment-results/README.md) for
the data schema and [`experiment-results/metadata.json`](experiment-results/metadata.json)
for the recorded and unavailable experimental metadata.

## Features

- **Dynamic Variable-Level Partitioning**
  - Fine-grained divide-and-conquer parallelism.
  - Designed for arithmetic formulas with limited Boolean branching, including pure-conjunction and almost-pure-conjunction instances.

- **Boolean and Interval Constraint Propagation (BICP)**
  - Combines Boolean and arithmetic propagation for subtask simplification.

- **Two-Tier Distributed Architecture**
  - Leader: Global task scheduling and inter-server coordination.
  - Coordinators: Intra-server dynamic load balancing and parallel tree maintenance.
  - Workers: Solve subtasks using backend SMT solvers.

- **Flexible Solver Backend**
  - Supports configurable SMT solver binaries that accept SMT-LIB v2 input.
  - Tested with cvc5, Z3, and OpenSMT2.

- **Parallel and Distributed Evaluation Support**
  - Includes benchmark lists, example configurations, archived results, and
    machine-readable evidence metadata.

- **Multi-Theory Support**
  - Handles QF_LRA, QF_LIA, QF_NRA, and QF_NIA benchmarks.

---

## Build Instructions

### Requirements

* Python 3.8 or later
* GCC/Clang with C++17 support
* CMake and Make
* GLIBC version >= 2.29
* MPI (e.g., OpenMPI)
* python3-mpi4py
* One of the bundled Linux x86-64 backend solvers, or another installed SMT
  solver that accepts SMT-LIB v2 input
* Unix-like OS (tested on Ubuntu 20.04 and 22.04)

Install Python MPI bindings:

```bash
sudo apt-get install python3-mpi4py
```

---

### Quick Build Command

Run the build script from the project root:

```bash
python3 build.py
```

---

### Build Outputs

After a successful build, you will have:

```
bin/
├── AriParti_launcher.py
├── control_message.py
├── coordinator.py
├── dispatcher.py
├── leader.py
├── partitioner.py
├── partition_tree.py
└── binaries/
    ├── partitioner-bin
    ├── cvc5-1.0.8-bin
    ├── opensmt-2.5.2-bin
    └── z3-4.12.1-bin
```

The partitioner binary `partitioner-bin` is built automatically and required for AriParti's distributed solving.

---

### Base Solver Setup

AriParti requires one or more SMT solvers in `bin/binaries/`. For Linux x86-64,
the journal artifact redistributes unmodified upstream binaries for cvc5 1.0.8,
OpenSMT2 2.5.2, and Z3 4.12.1. `build.py` copies these binaries from
`linux-pre_built/binaries/` into `bin/binaries/`.

The backend binaries are third-party software and are not covered by the
AriParti-Distributed MIT license. Their upstream sources, exact release assets,
copyright notices, license texts, and SHA-256 values are recorded in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Review those terms before
using or redistributing the artifact. On another platform, or to use a different
solver build, replace the bundled executable and update `base_solver`.


### Custom Solver Configuration

You can configure a custom SMT solver binary if it:

* Accepts an SMT-LIB v2 file as its only positional argument
* Exits successfully and prints exactly `sat` or `unsat` for ordinary inputs;
  for an input containing `(get-model)`, the first output line must be the
  status and subsequent lines may contain the model
* Is placed as an executable in `bin/binaries/`
* Matches the name specified in your `config.json`:

```json
"base_solver": "your-solver-binary-name"
```

For example, if you place a custom build of Z3 4.13.0 as `bin/binaries/z3-4.13.0-bin`, set:

```json
"base_solver": "z3-4.13.0-bin"
```

No solver-specific command-line flags are added by the worker. A custom solver
therefore needs to support this invocation contract directly, or be wrapped by
a small adapter executable. A backend `unknown` response is not a decisive
result and the current worker treats it as a subprocess error.

---

## Directory Structure

```
AriParti-Distributed/
├── src/                            # Core distributed SMT solving framework
│   ├── AriParti_launcher.py        # Entry point for multi-node distributed runs
│   ├── leader.py                   # Leader process: global task scheduling & coordination
│   ├── coordinator.py              # Coordinator process: intra-server scheduling
│   ├── dispatcher.py               # Orchestrates leader, coordinators, and workers
│   ├── partition_tree.py           # Partition tree maintenance & UNSAT propagation
│   ├── control_message.py          # MPI message definitions for control flow
│   ├── partitioner.py              # Python wrapper for the partitioner process
│   └── partitioner/                # C++ partitioner source tree
│
├── linux-pre_built/                # Prebuilt launcher and AriParti partitioner
│
├── benchmark-lists/                # Benchmark set listings for batch experiments
│   ├── all/                        # Full benchmark lists (LRA, LIA, NRA, NIA)
│   │   ├── QF_LRA-all_list-1753.txt
│   │   ├── QF_LIA-all_list-13226.txt
│   │   ├── QF_NRA-all_list-12134.txt
│   │   └── QF_NIA-all_list-25358.txt
│   └── pure-conjunction/           # Filtered lists for pure conjunction instances
│       ├── QF_LRA-pure_conjunction_list-337.txt
│       ├── QF_LIA-pure_conjunction_list-4066.txt
│       ├── QF_NRA-pure_conjunction_list-6034.txt
│       └── QF_NIA-pure_conjunction_list-1520.txt
│
├── test/                           # Test suite & benchmark instances
│   ├── configs/                     # Example JSON configurations
│   ├── instances/                  # SMT-LIB v2 test formulas
│   ├── validate_evidence.py        # Read-only current-snapshot evidence checker
│   └── output/                     # Auto-generated test outputs
│
├── experiment-results/             # Collected experimental results
│   ├── metadata.json               # Known and unavailable campaign metadata
│   ├── distributed/                # Distributed mode results (multi-node)
│   │   ├── cpu-usage/              # Validated CPU-instrumented per-instance runs
│   │   ├── data/                   # Raw results without CPU usage
│   │   └── sumup/                  # Summary tables (4 theories)
│   ├── parallel/                   # Parallel mode results (single-node)
│   └── ablation/                   # Full-list p8/1200s mechanism evidence
│
├── build.py                        # Build script for packaging components
├── README.md                       # Main project documentation (this file)
└── LICENSE.txt                     # MIT License

```

## Evaluation Results

The experiment archive is stored under `experiment-results/`. It contains
per-instance records for the archived parallel and distributed comparisons and
a validated CPU-utilization campaign and aggregate bundle for the full-list
mechanism ablations. Companion README files document the schemas, aggregation
rules, measurement scope, and validation commands.

## Evaluation Result Map

Paths are relative to this repository.

| Evidence | Repository path and role |
| --- | --- |
| Benchmark universe | `benchmark-lists/manifest.csv` and `benchmark-lists/all/` define the four arithmetic lists used for scope accounting and the mechanism-comparison archive. [`benchmark-lists/QF_NIA-provenance.md`](benchmark-lists/QF_NIA-provenance.md) documents why the evaluated 25,358-instance QF_NIA list differs from the later 25,443-instance frozen SMT-LIB 2023 list and records the complete 85-instance difference. |
| Pure-conjunction subset | The current outcome table uses the QF_LRA, QF_LIA, QF_NRA, and QF_NIA lists under `benchmark-lists/pure-conjunction/`; their p16 cvc5 outcomes are recoverable from the corresponding per-configuration CSVs. The two linear OpenSMT2 joins used with the CAV-style scatter panel are summarized in `experiment-results/parallel/pure-conjunction-opensmt2-p16-summary.csv`. |
| Parallel comparisons by theory and backend | The complete-configuration tables use the QF_LRA, QF_LIA, QF_NRA, and QF_NIA CSVs and summaries under `experiment-results/parallel/`. |
| Distributed comparison and resource levels | The manuscript reports selected p512 measurements on all four theories and the QF_NRA 32--512-slot sweep under `experiment-results/distributed/`. |
| CPU utilization | `experiment-results/distributed/cpu-usage/` contains seven independent CPU-instrumented runs with 79,387 valid per-instance observations. Its README and manifest define the measurement relationship, exact coverage, status counts, and file hashes. |
| BICP and clause-reduction configuration comparisons | `experiment-results/ablation/full-list-p8-1200s/` preserves the aggregate and audit artifacts for all eight full-list comparisons used by the current manuscript. |
| Result inventory | `experiment-results/manifest.csv` inventories the archived result directories and their record counts. |
| Experimental metadata | `experiment-results/metadata.json` records aggregation semantics, known configuration facts, explicit legacy metadata gaps, and the metadata captured by new runs. |
| Runnable implementation and examples | `src/`, `linux-pre_built/`, and `test/configs/` provide the implementation, a prebuilt Linux launcher/partitioner runtime, three license-audited backend solver binaries, and example launcher configurations. |

The older CAV 2024 artifact evaluation package is archived separately on
[Zenodo](https://doi.org/10.5281/zenodo.10947054). The evidence described above
belongs to the distributed implementation in this repository.

## Full-List Mechanism-Ablation Evidence

The full-list BICP and clause-reduction evidence is located at:

```text
experiment-results/ablation/full-list-p8-1200s/
```

The archive covers the four artifact benchmark lists with eight cores per
benchmark instance and a 1,200-second timeout. `delta.csv` and `table.tex`
report all eight Full-versus-Disabled aggregate comparisons. Verify the
bundle's file integrity with:

```bash
(cd experiment-results/ablation/full-list-p8-1200s && sha256sum --check SHA256SUMS)
```

### Result Interpretation

The solved-count delta is `full - ablated`, while the PAR-2 delta is
`ablated - full`; positive values therefore favor the full configuration. The
eight rendered rows are aggregate results for the stated theory, benchmark
list, core count, and timeout. See the bundle README and `result-metadata.json`
for the complete result scope.

## Reproducibility Levels

- **Verify the published evidence:** run `python3 test/validate_evidence.py`.
  This is local and does not require the benchmark corpus, MPI, or solver runs.
- **Check implementation invariants and packaging:** run the other two commands
  in the reviewer quick path above.
- **Run AriParti on a supplied formula:** build or use the Linux prebuilt
  package, update an example configuration, and follow the parallel or
  distributed launch instructions below.
- **Repeat the full evaluation:** obtain the SMT-LIB benchmark corpus identified
  by `benchmark-lists/manifest.csv`, provide equivalent compute resources, and
  use the recorded configuration scope. The repository does not claim that the
  complete legacy machine inventory or executable hashes are recoverable; the
  exact gaps are marked as unavailable in `experiment-results/metadata.json`.

## Distributed & Parallel Usage

AriParti supports both parallel (single-node) and distributed (multi-node) solving. The execution mode is determined by the `mode` field in the configuration JSON.

---

### Configuration JSON Overview

| Field               | Description                                                                                                                    | Required in Mode      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------------------- |
| `formula_file`      | Absolute path to the SMT-LIB v2 formula to solve                                                                               | Parallel, Distributed |
| `output_dir`        | Absolute path to the directory for saving logs and outputs                                                                     | Parallel, Distributed |
| `timeout_seconds`   | Total solving timeout in seconds                                                                                               | Parallel, Distributed |
| `base_solver`       | Name of the solver binary in `bin/binaries/` (e.g., `cvc5-1.0.8-bin`)                                                          | Parallel, Distributed |
| `mode`              | Execution mode: `"parallel"` or `"distributed"`                                                                                | Parallel, Distributed |
| `parallel_core`     | Number of cores to use for single-node parallel solving (**recommended ≥ 8 cores**)                                            | Parallel only         |
| `bicp_enabled`      | Enable Boolean and Interval Constraint Propagation in the partitioner; defaults to `true`                                      | Optional             |
| `clause_reduction_enabled` | Enable theory-level clause reduction in generated subtasks; defaults to `true`                                         | Optional             |
| `network_subnet`  | IPv4 subnet (CIDR) used for MPI TCP communication (e.g., `192.0.2.0/24`)                                    | Distributed only      |
| `worker_node_ips`   | List of IP addresses of worker nodes                                                                                           | Distributed only      |
| `worker_node_cores` | Number of available cores on each worker node (same order as `worker_node_ips`, **recommended ≥ 8 cores on the first server**) | Distributed only      |

---

### Parallel Mode Example

This mode runs AriParti on a single machine using multiple cores.

**Configuration:**

```json
{
    "formula_file": "/path/to/lia-unsat-17.8.smt2",
    "output_dir": "/path/to/output/lia-parallel-64",
    "timeout_seconds": 1200,
    "base_solver": "opensmt-2.5.2-bin",
    "mode": "parallel",
    "parallel_core": 64,
    "bicp_enabled": true,
    "clause_reduction_enabled": true
}
```

**Launch Command:**

```bash
python3 linux-pre_built/AriParti_launcher.py test/configs/parallel-64.json
```

---

### Distributed Mode Example

This mode runs AriParti across multiple nodes in a cluster.

**Configuration:**

```json
{
    "formula_file": "/path/to/nia-sat-6.2.smt2",
    "output_dir": "/path/to/output/nia-distributed-128",
    "timeout_seconds": 1200,
    "base_solver": "z3-4.12.1-bin",
    "mode": "distributed",
    "bicp_enabled": true,
    "clause_reduction_enabled": true,
    "network_subnet": "192.0.2.0/24",
    "worker_node_ips": [
        "192.0.2.11",
        "192.0.2.12",
        "192.0.2.13"
    ],
    "worker_node_cores": [
        32,
        32,
        64
    ]
}
```

**Launch Command:**

```bash
python3 linux-pre_built/AriParti_launcher.py test/configs/distributed-128.json
```

---

### Ablation Switches

The full AriParti configuration uses:

```json
"bicp_enabled": true,
"clause_reduction_enabled": true
```

For mechanism-ablation runs, the launcher also accepts:

- `bicp_enabled: false` selects the pure-ICP baseline: it disables
  Boolean-driven propagation and BICP-derived Boolean facts/simplifications
  while keeping arithmetic interval propagation, the original formula
  constraints, and partition-path bounds.
- `clause_reduction_enabled: false` to keep value-based subtask extraction but
  skip theory-level clause simplification and dominated-clause removal.

At the current repository state, `bicp_enabled: false` is a non-default
ablation configuration and requires an explicit ablation opt-in. The result
directory contains the completed full-list p8/1200-second `no_bicp` rows in
`experiment-results/ablation/full-list-p8-1200s/`, whose README documents the
configuration and validation scope.

Each launch writes `<output_dir>/run-metadata.json` with the effective
configuration, command line, git commit when available, platform information,
best-effort `--version` output, and SHA-256 hashes for the configured solver
and partitioner binaries.

---

### Network Subnet Configuration

AriParti uses MPI (`mpiexec`) for inter-node communication. The `network_subnet` field in your configuration JSON specifies the IPv4 subnet (CIDR notation) that Open MPI should use for both its OOB and BTL TCP channels.

To discover the correct subnet, run:

```bash
ip -4 addr show
```

and identify the address and prefix of the NIC you want to use (for example,
`192.0.2.11/24` in a documentation-only configuration). Use the subnet portion
(for example, `192.0.2.0/24`) for `network_subnet`. Replace all documentation
addresses with the actual private addresses of your cluster. You can confirm
the prefix with:

```bash
ip route
```

The launcher forwards this value via `--mca oob_tcp_if_include` and `--mca btl_tcp_if_include`, and forces `--mca btl self,tcp` so all MPI traffic stays on the TCP fabric you specify.

---

### Important Notes for Multi-Server Setup

* Every node must have an address inside `network_subnet` and be able to reach the others over that network.
* Open MPI accepts comma-separated subnets when you need to enable multiple networks (e.g., `"10.1.0.0/16,172.16.0.0/16"`).
* If you require additional MCA tuning (such as exclusions), supply extra flags via `OMPI_MCA` environment variables or adjust the launcher accordingly.

---

### Why This Change is Necessary

This configuration ensures that:

* Both control (OOB) and data (BTL) traffic stay on the same routed subnet.
* MPI uses the TCP transport explicitly, avoiding surprises from other fabrics.

---

### Checklist for Distributed Runs

* Verify that all nodes can ping each other over the subnet specified in `network_subnet`.
* Set `network_subnet` correctly in `config.json`, updating it whenever the cluster topology changes.
* Keep any additional MCA overrides consistent across all servers.

### Outputs

* Logs: `<output_dir>/logs`
* Rankfile: `<output_dir>/rankfile`
* Solver results and intermediate data: `<output_dir>/`

---

### Summary Table

| Mode        | Field to Configure                                          | Example Command                                        |
| ----------- | ----------------------------------------------------------- | ------------------------------------------------------ |
| Parallel    | `parallel_core`                                             | `python3 linux-pre_built/AriParti_launcher.py parallel.json`    |
| Distributed | `network_subnet`, `worker_node_ips`, `worker_node_cores` | `python3 linux-pre_built/AriParti_launcher.py distributed.json` |

---
