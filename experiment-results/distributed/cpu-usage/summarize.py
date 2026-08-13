#!/usr/bin/env python3
"""Recompute runtime-weighted CPU-utilization summaries from archived rows."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TWO_PLACES = Decimal("0.01")


def rounded(value: Decimal) -> str:
    return str(value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def group_name(configuration: str) -> str:
    if configuration.startswith("AriParti-"):
        return "AriParti"
    if configuration.startswith("SMTS-"):
        return "SMTS"
    if configuration.startswith("cvc5-"):
        return "cvc5-cloud"
    raise ValueError(f"unknown CPU-usage configuration: {configuration}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="check the rounded per-run means and pooled observation counts reported in the paper and response",
    )
    args = parser.parse_args()

    with (ROOT / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))

    expected_means = {
        ("QF_LIA", "AriParti-s4-p128"): "81.44",
        ("QF_LIA", "SMTS-s4-p128"): "78.66",
        ("QF_LRA", "AriParti-s4-p128"): "81.63",
        ("QF_LRA", "SMTS-s4-p128"): "46.74",
        ("QF_NIA", "AriParti-s4-p128"): "98.40",
        ("QF_NRA", "AriParti-s4-p128"): "97.22",
        ("QF_NRA", "cvc5-1.0.8-parti512"): "8.87",
    }
    expected_pooled_counts = {"AriParti": 52274, "SMTS": 14979, "cvc5-cloud": 12134}
    pooled: dict[str, list[Decimal | int]] = defaultdict(lambda: [0, Decimal(0), Decimal(0)])
    output_rows: list[tuple[str, str, str, int, str]] = []

    for entry in manifest:
        count = 0
        runtime_sum = Decimal(0)
        weighted_sum = Decimal(0)
        with (ROOT / entry["file"]).open(newline="", encoding="utf-8") as handle:
            for _benchmark, _status, runtime_text, cpu_text in csv.reader(handle):
                runtime = Decimal(runtime_text)
                cpu_usage = Decimal(cpu_text)
                count += 1
                runtime_sum += runtime
                weighted_sum += runtime * cpu_usage

        mean = weighted_sum / runtime_sum
        key = (entry["logic"], entry["configuration"])
        if args.check and rounded(mean) != expected_means[key]:
            raise SystemExit(f"FAIL: runtime-weighted mean mismatch for {key}: {rounded(mean)}")
        output_rows.append(("run", entry["logic"], entry["configuration"], count, rounded(mean)))

        group = pooled[group_name(entry["configuration"])]
        group[0] += count
        group[1] += runtime_sum
        group[2] += weighted_sum

    for group_name_value in ("AriParti", "SMTS", "cvc5-cloud"):
        count, runtime_sum, weighted_sum = pooled[group_name_value]
        if args.check and count != expected_pooled_counts[group_name_value]:
            raise SystemExit(f"FAIL: pooled observation-count mismatch for {group_name_value}: {count}")
        output_rows.append(
            ("pooled", "pooled", group_name_value, int(count), rounded(weighted_sum / runtime_sum))
        )

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(("scope", "logic", "configuration", "observations", "runtime_weighted_mean_percent"))
    writer.writerows(output_rows)
    if args.check:
        print("OK: CPU-utilization summaries match the reported values", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
