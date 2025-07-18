# AriParti: Distributed and Parallel SMT Solving Based on Dynamic Variable-level Partitioning

AriParti is an open-source distributed and parallel SMT solving framework based on dynamic variable-level partitioning, as described in our paper *Distributed and Parallel SMT Solving Based on Dynamic Variable-level Partitioning*. It is optimized for arithmetic theories and supports any SMT solver that accepts the SMT-LIB v2 format.

The project includes code from the Z3 project (MIT License) and is itself released under the [MIT License](LICENSE.txt).

Project homepage: [GitHub - AriParti](https://github.com/shaowei-cai-group/AriParti)
Project homepage: [GitHub - AriParti-Distributed](https://github.com/zmylinxi99/AriParti-Distributed)

---
## Build Instructions

### Requirements

* Python 3.7 or later
* GCC/Clang with C++17 support
* CMake and Make
* GLIBC version >= 2.29
* MPI (e.g., OpenMPI)
* python3-mpi4py
* Installed SMT solvers (CVC5, Z3, OpenSMT2 binaries provided in `binary-files/`)
* Unix-like OS (tested on Ubuntu 20.04 and 22.04)

Install Python MPI bindings:

```bash
sudo apt-get install python3-mpi4py
```

---

### Build AriParti

The provided `build.py` script automates the build process for AriParti. It performs the following steps:

1. Creates the `bin/` and `bin/binaries/` directories.
2. Copies the core Python scripts from `src/` to `bin/`.
3. Builds the partitioner by running:

   * `python scripts/mk_make.py`
   * `make -j`
4. Installs the partitioner binary to `bin/binaries/partitioner-bin`.

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
├── solver/                    # Core distributed SMT solver
│   ├── AriParti_launcher.py       # Multi-node launcher (distributed mode)
│   ├── run_AriParti.py            # Single-node entry point (local testing)
│   ├── leader.py                  # Leader process for global scheduling
│   ├── coordinator.py             # Coordinator process for intra-node scheduling
│   ├── dispatcher.py              # Orchestrates leader/coordinators/workers
│   ├── partition_tree.py          # Partition tree management & UNSAT propagation
│   ├── control_message.py         # MPI control message definitions
│   ├── partitioner.py             # Dynamic variable-level partitioner (BICP)
│   ├── binary-files/              # Prebuilt solver and partitioner binaries
│   │   ├── cvc5-1.0.8-bin
│   │   ├── z3-4.12.1-bin
│   │   ├── z3pp-at-smt-comp-2023-bin
│   │   ├── opensmt-2.5.2-bin
│   │   └── partitioner-bin
│
├── test/                      # Test suite & benchmark instances
│   ├── config/                    # Example JSON configurations for tests
│   │   ├── solve-lra-sat-6.63.json
│   ├── instances/                 # SMT-LIB v2 test formulas
│   │   ├── lia-sat-0.4.smt2
│   │   ├── lra-sat-6.63.smt2
│   │   ├── nia-unsat-112.5.smt2
│   │   ├── nra-unsat-53.43.smt2
│   │   └── README.md              # Describes benchmark categories
│   ├── output/                    # Test outputs (auto-generated)
│   │   └── input.json             # Auto-generated during test runs
│   └── run_tests.sh               # One-click test runner script
│
├── experiment-results/        # Experimental results from paper
│   ├── distributed/               # Results from distributed experiments
│   │   ├── cpu-usage/             # CPU usage data for utilization analysis
│   │   │   ├── QF_LIA-13226/
│   │   │   ├── QF_LRA-1753/
│   │   │   ├── QF_NIA-25358/
│   │   │   └── QF_NRA-12134/
│   │   ├── data/                  # Experimental data (without CPU usage)
│   │   │   ├── QF_LIA-13226/
│   │   │   ├── QF_LRA-1753/
│   │   │   ├── QF_NIA-25358/
│   │   │   └── QF_NRA-12134/
│   │   └── sumup/                 # Summary results for each theory
│   │       ├── QF_LIA-results-sumup.txt
│   │       ├── QF_LRA-results-sumup.txt
│   │       ├── QF_NIA-results-sumup.txt
│   │       └── QF_NRA-results-sumup.txt
│   ├── parallel/                  # Results from parallel (single-node) experiments
│   │   ├── QF_LIA-13226/
│   │   ├── QF_LIA-13226-results-sumup.txt
│   │   ├── QF_LRA-1753/
│   │   ├── QF_LRA-1753-results-sumup.txt
│   │   ├── QF_NIA-25358/
│   │   ├── QF_NIA-25358-results-sumup.txt
│   │   ├── QF_NRA-12134/
│   │   └── QF_NRA-12134-results-sumup.txt
├── build.py
├── README.md                  # Main documentation (English)
├── LICENSE.txt                # MIT License

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

AriParti uses MPI (`mpiexec`) for inter-node communication. Set the `network_interface` field in your configuration JSON to the name of the network interface used for cluster communication.

To find your interface name:

```bash
ip addr
```

or

```bash
ifconfig
```

Common names include `eth0`, `ens33`, and `enp1s0f1`. Replace `enp1s0f1` in the configuration if necessary.

---

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