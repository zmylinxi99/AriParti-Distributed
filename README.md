# AriParti-Distributed: Distributed and Parallel SMT Solving with Dynamic Variable-Level Partitioning

AriParti-Distributed is a high-performance open-source framework for distributed and parallel Satisfiability Modulo Theories (SMT) solving. It extends the dynamic variable-level partitioning strategy from our CAV 2024 Distinguished Paper into a scalable two-tier Leader–Coordinator–Worker architecture for large clusters.

The framework supports any SMT solver that accepts the SMT-LIB v2 format (e.g., Z3, CVC5, OpenSMT2), and is optimized for arithmetic theories. It incorporates advanced techniques like Boolean and Interval Constraint Propagation (BICP) for efficient formula simplification.

- Paper: *Distributed and Parallel SMT Solving Based on Dynamic Variable-Level Partitioning* (submitted to Formal Methods in System Design)
- Project: [AriParti GitHub](https://github.com/shaowei-cai-group/AriParti)
- Distributed version: [AriParti-Distributed GitHub](https://github.com/zmylinxi99/AriParti-Distributed)

The project includes code from the Z3 project (MIT License) and is itself released under the [MIT License](LICENSE.txt).

## Features

- **Dynamic Variable-Level Partitioning**
  - Fine-grained divide-and-conquer parallelism.
  - Robust even for pure-conjunction and almost-pure-conjunction formulas.

- **Boolean and Interval Constraint Propagation (BICP)**
  - Enhanced propagation by combining Boolean and arithmetic reasoning.

- **Two-Tier Distributed Architecture**
  - Leader: Global task scheduling and inter-server coordination.
  - Coordinators: Intra-server dynamic load balancing and parallel tree maintenance.
  - Workers: Solve subtasks using backend SMT solvers.

- **Flexible Solver Backend**
  - Supports any SMT solver accepting SMT-LIB v2 format.
  - Tested with CVC5, Z3, and OpenSMT2.

- **High Scalability**
  - Efficiently scales up to 512 cores with 96.99% CPU utilization.

- **Multi-Theory Support**
  - Handles QF_LRA, QF_LIA, QF_NRA, and QF_NIA benchmarks.

---

## Build Instructions

### Requirements

* Python 3.7 or later
* GCC/Clang with C++17 support
* CMake and Make
* GLIBC version >= 2.29
* MPI (e.g., OpenMPI)
* python3-mpi4py
* Installed SMT solvers (CVC5, Z3, OpenSMT2 binaries provided in `linux-pre_built/binaries`)
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
    ├── cvc5-1.0.8-bin            # (if provided)
    ├── opensmt-2.5.2-bin         # (if provided)
    ├── z3-4.12.1-bin             # (if provided)
    └── z3pp-at-smt-comp-2023-bin # (if provided)
```

The partitioner binary `partitioner-bin` is built automatically and required for AriParti's distributed solving.

---

### Base Solver Setup

AriParti requires one or more SMT solvers (CVC5, OpenSMT2, Z3) to be installed in `bin/binaries/`.

You can either:

**Use prebuilt binaries** provided in `linux-pre_built/`:

```bash
cp linux-pre_built/cvc5-1.0.8-bin bin/binaries/
cp linux-pre_built/opensmt-2.5.2-bin bin/binaries/
cp linux-pre_built/z3-4.12.1-bin bin/binaries/
cp linux-pre_built/z3pp-at-smt-comp-2023-bin bin/binaries/
```

**Or build solvers manually** (see each solver’s official instructions) and place the resulting binaries into `bin/binaries/`:


### Custom Solver Configuration

You are free to **configure and use any SMT solver and version** as long as it:

* Accepts **SMT-LIB v2 input format**
* Is placed as an executable in `bin/binaries/`
* Matches the name specified in your `config.json`:

```json
"base_solver": "your-solver-binary-name"
```

For example, if you place a custom build of Z3 4.13 as `bin/binaries/z3-4.13.0-bin`, set:

```json
"base_solver": "z3-4.13.0-bin"
```

This flexibility allows you to test AriParti with different solvers and versions seamlessly.

### Notes

* The `base_solver` field in `config.json` must match the name of the solver binary in `bin/binaries/`.
* For example:

```json
"base_solver": "cvc5-1.0.8-bin"
```

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
│   ├── partitioner.py              # Dynamic variable-level partitioner (with BICP)
│   └── utils/                      # Utility modules shared by components
│
├── linux-pre_built/                # Prebuilt SMT solver binaries (Linux)
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
│   ├── config/                     # Example JSON configurations
│   ├── instances/                  # SMT-LIB v2 test formulas
│   ├── output/                     # Auto-generated test outputs
│   └── run_tests.sh                # One-click test runner script
│
├── experiment-results/             # Collected experimental results
│   ├── distributed/                # Distributed mode results (multi-node)
│   │   ├── cpu-usage/              # CPU utilization data for analysis
│   │   ├── data/                   # Raw results without CPU usage
│   │   └── sumup/                  # Summary tables (4 theories)
│   └── parallel/                   # Parallel mode results (single-node)
│
├── build.py                        # Build script for packaging components
├── README.md                       # Main project documentation (this file)
└── LICENSE.txt                     # MIT License

```

## Distributed & Parallel Usage

AriParti supports both parallel (single-node) and distributed (multi-node) solving. The execution mode is determined by the `mode` field in the configuration JSON.

---

### Configuration JSON Overview

| Field               | Description                                                                     | Required in Mode      |
| ------------------- | ------------------------------------------------------------------------------- | --------------------- |
| `formula_file`      | Absolute path to the SMT-LIB v2 formula to solve                                | Parallel, Distributed |
| `output_dir`        | Absolute path to directory for saving logs and outputs                          | Parallel, Distributed |
| `timeout_seconds`   | Total solving timeout in seconds                                                | Parallel, Distributed |
| `base_solver`       | Name of the solver binary in `bin/binaries/` (e.g., `cvc5-1.0.8-bin`)           | Parallel, Distributed |
| `mode`              | Execution mode: `"parallel"` or `"distributed"`                                 | Parallel, Distributed |
| `parallel_core`     | Number of cores to use for single-node parallel solving                         | Parallel only         |
| `network_interface` | Network interface name for MPI communication (e.g., `eth0`, `enp1s0f1`)         | Distributed only      |
| `worker_node_ips`   | List of IP addresses of worker nodes                                            | Distributed only      |
| `worker_node_cores` | Number of available cores on each worker node (same order as `worker_node_ips`) | Distributed only      |

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
    "parallel_core": 64
}
```

**Launch Command:**

```bash
python3 solver/AriParti_launcher.py test/config/parallel-64.json
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
    "network_interface": "enp1s0f1",
    "worker_node_ips": [
        "192.168.100.13",
        "192.168.100.14",
        "192.168.100.15"
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
python3 solver/AriParti_launcher.py test/config/distributed-128.json
```

---

### Network Interface Configuration

AriParti uses MPI (`mpiexec`) for inter-node communication. The `network_interface` field in your configuration JSON specifies the name of the network interface used for cluster communication.

To find your network interface name, run:

```bash
ip addr
```

or

```bash
ifconfig
```

Common interface names include `eth0`, `ens33`, and `enp1s0f1`. Replace `enp1s0f1` in your configuration if your cluster uses a different network interface.

---

### Important Notes for Multi-Server Setup

The current distributed version requires all servers in the cluster to use the same network interface name for communication. If this condition is not met (for example, servers have different interface names or isolated networks), you must modify the launcher configuration.

In `AriParti_launcher.py`, locate the following code:

```python
'--mca', 'btl_tcp_if_include', config['network_interface'],
```

Replace it with an exclusion-based configuration:

```bash
--mca btl_tcp_if_exclude XXX
```

Here, `XXX` is a comma-separated list of all interfaces to exclude from MPI communication.

Example:

```bash
--mca btl_tcp_if_exclude lo,docker0
```

This excludes the loopback (`lo`) and Docker (`docker0`) interfaces, allowing MPI to use only physical network interfaces such as `eth0` or `enp1s0f1` for inter-node communication.

It is important to apply the same exclusion configuration on all servers to ensure consistent MPI behavior.

---

### Why This Change is Necessary

This modification allows AriParti to:

* Support heterogeneous clusters where servers may have different network interface configurations.
* Avoid errors caused by MPI attempting to use non-routable interfaces (such as Docker bridges or loopback).

---

### Checklist for Distributed Runs

* Verify that all nodes can ping each other over the selected network interface.
* Set `network_interface` correctly in `config.json` or configure `btl_tcp_if_exclude` as described.
* Ensure excluded interfaces are consistent across all servers.

### Outputs

* Logs: `<output_dir>/logs`
* Rankfile: `<output_dir>/rankfile`
* Solver results and intermediate data: `<output_dir>/`

---

### Summary Table

| Mode        | Field to Configure                                          | Example Command                                        |
| ----------- | ----------------------------------------------------------- | ------------------------------------------------------ |
| Parallel    | `parallel_core`                                             | `python3 solver/AriParti_launcher.py parallel.json`    |
| Distributed | `network_interface`, `worker_node_ips`, `worker_node_cores` | `python3 solver/AriParti_launcher.py distributed.json` |

---