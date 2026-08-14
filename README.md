# AriParti-Distributed: Distributed and Parallel SMT Solving Based on Dynamic Variable-Level Partitioning

AriParti-Distributed extends the dynamic variable-level partitioning strategy
of AriParti into a Leader–Coordinator–Worker architecture for parallel and
multi-server SMT solving. It targets arithmetic theories, simplifies generated
subtasks with Boolean and Interval Constraint Propagation (BICP), and delegates
them to an SMT-LIB v2 backend such as cvc5, Z3, or OpenSMT2.

This repository contains the implementation and the supporting material for
the associated manuscript: source code, a ready-to-run Linux x86-64 package,
example configurations, benchmark manifests, experimental records, summaries,
and consistency checks.

- Associated manuscript: *Distributed and Parallel SMT Solving Based on Dynamic Variable-Level Partitioning*
- Original CAV 2024 project: [AriParti](https://github.com/shaowei-cai-group/AriParti)
- This implementation and evidence repository: [AriParti-Distributed](https://github.com/zmylinxi99/AriParti-Distributed)

The AriParti-Distributed source is released under the [MIT License](LICENSE.txt)
and includes Z3-derived code under the MIT License. The redistributed backend
solver binaries remain under their respective upstream licenses; see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Start Here

Choose the path that matches what you want to do:

| Goal | Starting point |
| --- | --- |
| Run the parallel example | `python3 linux-pre_built/AriParti_launcher.py test/configs/parallel-64.json` |
| Build from source | `python3 build.py` |
| Inspect the archived experiments | [`experiment-results/README.md`](experiment-results/README.md) |
| Check benchmark provenance | [`benchmark-lists/README.md`](benchmark-lists/README.md) |
| Configure a cluster run | [Distributed mode example](#distributed-mode-example) |

The following read-only commands validate the archived evidence and
implementation invariants without starting MPI jobs or backend solvers:

```bash
python3 test/validate_evidence.py
python3 test/test_partition_tree_invariants.py
python3 test/test_prebuilt_package.py
```

The first command validates the benchmark/result inventory, recomputes
all 79 parallel and distributed summary rows from 916,851 per-instance records,
validates 79,387 records from seven CPU-instrumented runs and the
collector checksums, recomputes the nine rows for the filtered
no-eligible-Boolean-atom comparisons, and checks the full-list ablation bundle. See
[`experiment-results/README.md`](experiment-results/README.md) for
the data schema and [`experiment-results/metadata.json`](experiment-results/metadata.json)
for the evaluation configuration and aggregation rules.

## Features

| Capability | What it provides |
| --- | --- |
| Dynamic variable-level partitioning | Fine-grained divide-and-conquer parallelism for arithmetic formulas with limited Boolean branching, including instances with no eligible Boolean partitioning atom after AriParti's preprocessing. |
| BICP simplification | Combined Boolean and interval propagation on generated subtasks. |
| Contextual clause reduction | Literal and clause simplification justified by the BICP-derived context. |
| Two-tier scheduling | A leader balances work across servers; coordinators maintain local partition trees and schedule solver workers. |
| Configurable backends | Any executable that follows the documented SMT-LIB v2 invocation contract; the repository includes cvc5, OpenSMT2, and Z3 binaries. |
| Parallel and distributed modes | Single-node multicore solving and multi-node solving through Open MPI. |
| Arithmetic theories | QF_LRA, QF_LIA, QF_NRA, and QF_NIA benchmark workflows. |

## Build Instructions

### Runtime Requirements

* Python 3.8 or later
* Open MPI
* python3-mpi4py
* Linux x86-64 for the bundled executables (tested on Ubuntu 20.04 and 22.04)
* GLIBC 2.30 or later for the bundled partitioner
* A bundled backend solver or another executable that follows the
  [custom solver contract](#custom-solver-configuration)

Install Python MPI bindings:

```bash
sudo apt-get install python3-mpi4py
```

Building the partitioner from source also requires GCC or Clang with C++17
support and Make.

### Build from Source

Run the build script from the project root:

```bash
python3 build.py
```

### Build Output

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

The partitioner binary `partitioner-bin` is built automatically and is required
for both parallel and distributed AriParti runs.

### Base Solver Setup

AriParti resolves `base_solver` relative to the `binaries/` directory beside
the launcher being used. The source build produced by `build.py` therefore uses
`bin/binaries/`, while the ready-to-run package uses
`linux-pre_built/binaries/`. For Linux x86-64, the repository redistributes
unmodified upstream binaries for cvc5 1.0.8, OpenSMT2 2.5.2, and Z3 4.12.1;
`build.py` copies them into `bin/binaries/`.

The backend binaries are third-party software and are not covered by the
AriParti-Distributed MIT license. Their upstream sources, exact release assets,
copyright notices, license texts, and SHA-256 values are listed in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Review those terms before
using or redistributing the artifact. On another platform, or to use a different
solver build, replace the bundled executable and update `base_solver`.

### Custom Solver Configuration

You can configure a custom SMT solver binary if it:

* Accepts an SMT-LIB v2 file as its only positional argument
* Exits successfully and prints exactly `sat` or `unsat` for ordinary inputs;
  for an input containing `(get-model)`, the first output line must be the
  status and subsequent lines may contain the model
* Is placed in the `binaries/` directory beside the launcher being used
  (`bin/binaries/` after a source build or `linux-pre_built/binaries/` for the
  prebuilt package)
* Matches the basename specified in your `config.json`:

```json
"base_solver": "your-solver-binary-name"
```

For example, if you place a custom build of Z3 4.13.0 beside the selected
launcher as `binaries/z3-4.13.0-bin`, set:

```json
"base_solver": "z3-4.13.0-bin"
```

No solver-specific command-line flags are added by the worker. A custom solver
therefore needs to support this invocation contract directly, or be wrapped by
a small adapter executable. A backend `unknown` response is not a decisive
result and the current worker treats it as a subprocess error.

## Directory Structure

```text
AriParti-Distributed/
├── src/                 # Python runtime and C++ partitioner source
├── linux-pre_built/     # Linux launcher, partitioner, and backend binaries
├── benchmark-lists/     # Full and filtered benchmark manifests
├── experiment-results/  # Parallel, distributed, CPU, and ablation records
├── test/                # Example formulas, configurations, and validators
├── third-party-licenses/
├── build.py
└── README.md
```

The README in each data or package directory describes its internal layout.

## Experimental Evidence

`experiment-results/` contains the records behind the manuscript's parallel
and distributed comparisons, CPU-utilization measurements, and mechanism
ablations. The evaluation uses four SMT-LIB 2023 arithmetic lists containing
52,471 instances in total. Use the map below to go directly to the relevant
material. Paths are relative to this repository.

| Question | Repository path and contents |
| --- | --- |
| Which benchmarks were evaluated? | `benchmark-lists/manifest.csv` and `benchmark-lists/all/` define the four arithmetic lists. [`benchmark-lists/QF_NIA-provenance.md`](benchmark-lists/QF_NIA-provenance.md) explains the 85-instance difference between the evaluated QF_NIA list and the later frozen SMT-LIB 2023 list. |
| Where are the parallel results? | `experiment-results/parallel/` contains per-instance CSVs and summaries by theory, backend, and CPU-slot budget. Its two top-level `pure-conjunction` summary CSVs retain their historical filenames but contain the derived p16 comparisons on instances with no eligible Boolean partitioning atom after AriParti's preprocessing. |
| Where are the distributed results? | `experiment-results/distributed/` contains the p512 measurements for all four theories and the QF_NRA 32--512-slot sweep. |
| Where are the CPU measurements? | `experiment-results/distributed/cpu-usage/` contains 79,387 observations from seven instrumented runs, plus the collector and its sampling, normalization, and aggregation rules. |
| Where are the BICP and contextual clause-reduction comparisons? | `experiment-results/ablation/full-list-p8-1200s/` contains all eight full-versus-disabled aggregate comparisons, the manuscript table, metadata, and checksums. The BICP comparison isolates its BCP--ICP coupling by retaining interval contraction in the disabled variant. Positive solved-count and PAR-2 deltas favor the full configuration. |
| What metadata are available? | `experiment-results/metadata.json` defines aggregation rules and evaluation settings. `experiment-results/manifest.csv` inventories result directories and row counts. |

### Manuscript Scope and Conventions

The manuscript reports three distinct experimental campaigns. The earlier
parallel campaign used one Ubuntu 20.04.4 LTS server with 1 TB RAM and two AMD
EPYC 7763 processors, each with 64 physical cores. The distributed-hardware
campaign used Ubuntu 20.04.4 LTS servers with 1 TB RAM and two AMD EPYC 9754
processors per server, each processor providing 128 physical cores; the p512
runs used four of these servers. The full-list p8 ablation campaign ran on one
server in the latter environment.

The manuscript uses `pN` for the complete configured budget of `N` CPU slots
for one configuration–instance run. In the evaluated AriParti(p512)
configuration, four servers provide 128 slots each. The distributed tier uses
504 slots, and the remaining eight-slot isolated allocation contains both the
local partition-and-solve branch and the direct complete-instance solver. The
leader and partitioners share these allocations; they do not add slots beyond
p512. The maximum simultaneous process count is 519 because some processes
share configured slots, and the launcher enforces reservations and worker
ceilings without fixed one-to-one CPU binding.

The main parallel, ablation, and distributed-hardware results were collected in
separate campaigns. Each reported configuration–instance pair has one recorded
run. The earlier parallel p8 and p32 rows are therefore not scaling baselines
for the distributed p512 rows. The resource-level sequence reported in the
manuscript is the same-campaign full-list QF_NRA sweep from p32 to p512.

At p512, the cross-system comparisons cover SMTS on QF_LRA and QF_LIA and
cvc5-cloud on QF_NRA. The AriParti QF_NIA p512 record is included as a
descriptive result; no distributed QF_NIA reference was evaluated. All
cross-system claims concern complete configurations, including task generation,
scheduling, communication, and backend solving.

The manuscript's correctness result is protocol-level SAT/UNSAT status
soundness for the implemented failure-free MPI orchestration. Its semantic
trusted base comprises equisatisfiable preprocessing, the expression and task
translations, BICP enclosure operations satisfying the stated contractor
contract, and sound backend results. The proof separately establishes
soundness of the implemented contextual-reduction rules. Its
ownership-preservation argument derives initial-frontier coverage from the
implemented binary-split cover, and a refinement proposition connects the
leader and coordinator event loops to the ownership protocol.
The communication model assumes reliable nonduplicating MPI communication and
no process or network failure. Timeouts, `unknown`, abnormal exits, resource
failures, and executions outside that model are unresolved and provide no SAT
or UNSAT evidence. The result does not claim failure recovery or reconstruction
of a model in the original input vocabulary.

The earlier CAV 2024 artifact evaluation package is archived separately on
[Zenodo](https://doi.org/10.5281/zenodo.10947054).

## Reproducibility Levels

- **Verify the published evidence:** run `python3 test/validate_evidence.py`.
  This is local and does not require the benchmark corpus, MPI, or solver runs.
- **Check implementation invariants and packaging:** run the other two commands
  under [Start Here](#start-here).
- **Run AriParti on a supplied formula:** build or use the Linux prebuilt
  package, update an example configuration, and follow the parallel or
  distributed launch instructions below.
- **Run the full benchmark lists:** obtain the SMT-LIB corpus identified by
  `benchmark-lists/manifest.csv`, configure the documented solver versions and
  slot budgets, and aggregate the results with the rules in
  `experiment-results/metadata.json`.

## Distributed & Parallel Usage

AriParti supports parallel solving on one machine and distributed solving
across several machines. Set the execution mode in the configuration JSON.

### Configuration JSON Overview

Common fields:

| Field | Meaning | Requirement or default |
| --- | --- | --- |
| `formula_file` | Absolute or working-directory-relative path to the SMT-LIB v2 input | Required |
| `timeout_seconds` | Configured wall-clock cutoff; the evaluated 1,200-second distributed cutoff includes initialization, partitioning, backend startup, and solving, and the leader checks it between communication cycles | Required |
| `base_solver` | Basename of the executable in the launcher's adjacent `binaries/` directory | Required |
| `mode` | `"parallel"` or `"distributed"` | Required |
| `output_dir` | Absolute or working-directory-relative output directory | `./output` |
| `bicp_enabled` | Enable BICP in the partitioner | `true` |
| `clause_reduction_enabled` | Enable theory-level clause reduction | `true` |
| `output_total_time` | Print total launcher elapsed time | `false` |
| `ablation` | Advanced mechanism switches | Disabled |

Mode-specific fields:

| Field | Meaning | Mode |
| --- | --- | --- |
| `parallel_core` | Number of cores used on one machine; at least 8 is recommended | Parallel |
| `network_subnet` | IPv4 subnet for MPI TCP traffic, such as `192.0.2.0/24` | Distributed |
| `worker_node_ips` | Worker-node addresses | Distributed |
| `worker_node_cores` | Available cores on each listed node, in the same order as `worker_node_ips` | Distributed |
| `isolated_coordinator_cores` | First-node cores reserved for the isolated coordinator when that node has at least 16 cores | Distributed; defaults to 8 |

Relative paths are resolved from the directory in which the launcher is
started. In distributed mode, all MPI ranks must resolve the formula and output
paths consistently. The launcher places the leader and an isolated coordinator
on the first listed node and reserves 2, 4, or 8 cores there according to the
available-core count; an explicit `isolated_coordinator_cores` value is honored
when the first node has at least 16 cores.

### Parallel Mode Example

This mode runs AriParti on a single machine using multiple cores.

Example configuration:

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

Launch it from the repository root:

```bash
python3 linux-pre_built/AriParti_launcher.py test/configs/parallel-64.json
```

### Distributed Mode Example

This mode runs AriParti across multiple nodes in a cluster.

Example configuration:

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

After replacing the documentation addresses, launch it from the repository
root:

```bash
python3 linux-pre_built/AriParti_launcher.py test/configs/distributed-128.json
```

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
- `clause_reduction_enabled: false` retains BICP and contextual truth
  evaluation, including deletion of false literals and clauses already
  satisfied by the context, but disables within-clause arithmetic comparisons
  and dominated-clause removal.

`bicp_enabled: false` requires
`"ablation": {"allow_no_bicp_ablation": true}` as an explicit opt-in. The
result directory contains the full-list p8/1200-second `no_bicp` rows in
`experiment-results/ablation/full-list-p8-1200s/`, whose README documents the
configuration and validation scope.

Each launch writes `<output_dir>/run-metadata.json` with the effective
configuration, command line, git commit when available, platform information,
best-effort `--version` output, and SHA-256 hashes for the configured solver
and partitioner binaries.

### Evaluated Heuristic Defaults

The manuscript evaluates the following scheduling and simplification defaults.
The source locations in the final column are the implementation reference.

| Mechanism | Evaluated behavior | Source |
| --- | --- | --- |
| Terminate on demand | Child progress values are 0 (unscheduled), 1 (running), and 2 (decisive). Thresholds for the reachable progress sums 0--3 are 1200, 400, 300, and 200 seconds. The root is exempt, and a parent is retained when its elapsed time exceeds the remaining run budget. | `src/coordinator.py`: `terminate_threshold`, `check_terminate_node` |
| Partitioner seeds | New runs from this source snapshot use seed 0 for interactive coordinators and seed 1 for the isolated coordinator. | `src/coordinator.py`: `parti_seed` |
| Split boundary | Prefer a seeded-random candidate non-equality literal; otherwise try zero, a finite midpoint, a one-sided offset of 128, or zero for a fully unbounded interval, in that order. Finite widths above 10 round the midpoint upward; a non-interior boundary is rejected. The default partition seed is 0. | `src/partitioner/src/math/subpaving/subpaving_t_def.h`: `init_partition` and boundary selection |
| BICP | Root and non-root propagation budgets are 10 and 5 seconds. | `src/partitioner/src/math/subpaving/subpaving_t_def.h`: `m_root_max_prop_time`, `m_max_prop_time` |
| Clause domination | Skip the quadratic pass above 10,000 input clauses. | `src/partitioner/src/math/subpaving/subpaving_t_def.h`: `remove_dominated_clauses` |
| Initial frontier | Attempt to expose one open task per interactive coordinator for at most 20 seconds. | `src/coordinator.py`: `pre_partition` |
| Migration tabu | Query donors in round-robin order and exclude a coordinator for 3 seconds after its latest assignment or successful split. | `src/leader.py`: `split_tabu` and donor selection |
| Transfer eligibility | Follow a unique open child. If both children are open, transfer the right child only when both have run for at least 5 seconds and each exceeds either 25 seconds or the mean runtime of backend-UNSAT leaves. | `src/partition_tree.py`: `satisfy_split_requirement`, `select_split_node` |

### Network Subnet Configuration

AriParti uses Open MPI (`mpiexec`) for inter-node communication.
`network_subnet` selects the IPv4 network used by both the OOB control channel
and BTL data channel. Every worker address must be reachable through this
network.

Find the address and prefix of the intended network interface with:

```bash
ip -4 addr show
ip route
```

For an interface address such as `192.0.2.11/24`, configure the subnet as
`192.0.2.0/24`. Replace the documentation addresses in the example with your
cluster's addresses and verify that the nodes can reach one another. Open MPI
also accepts a comma-separated list when several networks are required, for
example `"198.51.100.0/24,203.0.113.0/24"`.

The launcher passes the selected network to `oob_tcp_if_include` and
`btl_tcp_if_include` and selects the `self,tcp` BTL transports. Apply any
additional `OMPI_MCA` overrides consistently on every node.

### Outputs

* Logs: `<output_dir>/logs`
* Rankfile: `<output_dir>/rankfile`
* Solver results and intermediate data: `<output_dir>/`
