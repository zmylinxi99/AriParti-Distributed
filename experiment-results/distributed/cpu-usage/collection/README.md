# CPU-Utilization Collector

This directory contains the collector used for the CPU-instrumented runs. It
explains how the `cpu_usage_percent` field in the adjacent CSV files was
produced, including the normalization constants, network settings, and
file-based termination protocol.

## Collection Topology

`workload_monitor_with_config.py` creates an Open MPI hostfile from
`monitor.json` and launches one unbound monitor rank on each listed server.
The `s4-p128.json` configuration specifies four servers and 128 allocated CPU slots
per server. The launcher then reads each rank's final mean and takes an
unweighted arithmetic mean over the four servers. This final value is the
per-run CPU-utilization value later stored with that run's status and runtime.

The launcher selects the `ens6f0` MPI TCP interface. Reusing the
collector elsewhere requires adapting this interface and the host list.

## Sampling and Normalization

On each server, `monitor.py` calls
`psutil.cpu_percent(interval=0.02, percpu=True)`, averages the returned
percentages over all logical CPUs visible to `psutil`, and then sleeps for
0.08 seconds. The intended cycle is therefore 0.1 seconds plus loop and I/O
overhead.

For host-wide mean percentage \(h_{n,k}\) at sample \(k\) on server \(n\), the
archived script computes

```text
x[n,k] = min(100, h[n,k] * 512 / worker_node_core)
```

The configuration sets `worker_node_core` to 128, so the multiplier is four.
The hard-coded value 512 is the number of logical CPUs visible on each server;
the multiplication expresses host-wide usage
relative to the 128 slots allocated to the solver run. Values above the
allocation are capped at 100%.

For each server, the reported run-level value is the arithmetic mean of all
normalized samples:

```text
node_mean[n] = sum_k x[n,k] / number_of_samples[n]
```

The launcher then computes:

```text
cpu_usage_percent = sum_n node_mean[n] / 4
```

Thus the archived value is equally weighted over servers after each server's
samples have been averaged. It measures all CPU activity visible on each host,
normalized to the configured allocation.

The paper's runtime-weighted summaries are a later aggregation across runs:
for a CSV row with runtime \(t_i\) and the run-level value \(u_i\) above, they
use \(\sum_i t_i u_i / \sum_i t_i\).

## Output and Termination

Each rank appends a diagnostic line approximately once per second:

```text
elapsed_seconds recent_sample_mean cumulative_sample_mean
```

The final mean uses every approximately 0.1-second sample; the diagnostic lines
are a separate once-per-second log. When a `terminate` sentinel
appears in the request directory, each rank writes `rank-N-overall.txt` with
elapsed time on the first line and its final mean on the second. The sentinel
is checked at the next diagnostic-log boundary. The wrapper writes the mean of
the rank values to `overall.txt`.

The archived monitor does not use its timeout-based exit. The experiment
driver was responsible for creating the termination sentinel.

## Measurement Scope

The collector defines a host-wide, allocation-normalized utilization measure
for each complete configuration. The code and configuration specify its
sampling, normalization, temporal aggregation, and cross-server aggregation
semantics.

`SHA256SUMS` identifies the collector files.
