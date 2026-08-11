#!/usr/bin/env python3
"""Check or synchronize result summaries against per-instance CSV files."""

import argparse
import csv
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


RESULT_ROOT = Path(__file__).resolve().parent
TIMEOUT_SECONDS = Decimal("1200")
PAR2_PENALTY = TIMEOUT_SECONDS * 2
SUMMARY_KEYS = ("sat", "unsat", "solved", "failed", "PAR-2")


def aggregate_csv(path):
    counts = {"sat": 0, "unsat": 0, "failed": 0}
    par2 = Decimal(0)
    benchmarks = set()

    with path.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            if len(row) != 3:
                raise ValueError(
                    "{}:{}: expected three CSV fields, found {}".format(
                        path, line_number, len(row)
                    )
                )
            benchmark, status, runtime_text = row
            if benchmark in benchmarks:
                raise ValueError(
                    "{}:{}: duplicate benchmark {}".format(
                        path, line_number, benchmark
                    )
                )
            benchmarks.add(benchmark)
            try:
                runtime = Decimal(runtime_text)
            except InvalidOperation as exc:
                raise ValueError(
                    "{}:{}: invalid runtime {}".format(
                        path, line_number, runtime_text
                    )
                ) from exc

            if status == "sat":
                counts["sat"] += 1
                par2 += runtime
            elif status == "unsat":
                counts["unsat"] += 1
                par2 += runtime
            else:
                counts["failed"] += 1
                par2 += PAR2_PENALTY

    return {
        "sat": counts["sat"],
        "unsat": counts["unsat"],
        "solved": counts["sat"] + counts["unsat"],
        "failed": counts["failed"],
        "PAR-2": int(par2.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
    }


def render_key_value_summary(values):
    return "".join("{} {}\n".format(key, values[key]) for key in SUMMARY_KEYS)


def table_data_directory(table_path):
    suffix = "-results-sumup.txt"
    dataset = table_path.name[: -len(suffix)]
    if table_path.parent.name == "parallel":
        return table_path.parent / dataset

    data_root = table_path.parent.parent / "data"
    matches = sorted(
        path
        for path in data_root.iterdir()
        if path.is_dir() and path.name.startswith(dataset + "-")
    )
    if len(matches) != 1:
        raise ValueError(
            "{}: expected one data directory for {}, found {}".format(
                table_path, dataset, len(matches)
            )
        )
    return matches[0]


def render_table(table_path):
    data_directory = table_data_directory(table_path)
    rendered = []
    seen_solvers = set()

    for line in table_path.read_text(encoding="utf-8").splitlines(keepends=True):
        bare_line = line.rstrip("\r\n")
        newline = line[len(bare_line) :]
        if not bare_line.startswith("│") or "solver" in bare_line:
            rendered.append(line)
            continue

        cells = bare_line.split("│")
        values = [cell.strip() for cell in cells[1:-1]]
        if len(values) != 6 or not all(
            re.fullmatch(r"-?\d+", value) for value in values[1:]
        ):
            rendered.append(line)
            continue

        solver = values[0]
        csv_path = data_directory / (solver + ".csv")
        if not csv_path.is_file():
            raise ValueError("{}: missing {}".format(table_path, csv_path))
        if solver in seen_solvers:
            raise ValueError("{}: duplicate solver row {}".format(table_path, solver))
        seen_solvers.add(solver)
        aggregate = aggregate_csv(csv_path)

        for index, key in enumerate(SUMMARY_KEYS, start=2):
            width = len(cells[index])
            rendered_value = str(aggregate[key])
            if len(rendered_value) > width - 2:
                raise ValueError(
                    "{}: value {} does not fit its table column".format(
                        table_path, rendered_value
                    )
                )
            cells[index] = " " + rendered_value.rjust(width - 2) + " "
        rendered.append("│".join(cells) + newline)

    csv_solvers = {path.stem for path in data_directory.glob("*.csv")}
    if seen_solvers != csv_solvers:
        raise ValueError(
            "{}: table/CSV solver sets differ (missing={}, extra={})".format(
                table_path,
                sorted(csv_solvers - seen_solvers),
                sorted(seen_solvers - csv_solvers),
            )
        )
    return "".join(rendered)


def expected_files():
    for csv_path in sorted((RESULT_ROOT / "parallel").glob("QF_*/*.csv")):
        summary_path = csv_path.with_name(csv_path.stem + "-sumup.txt")
        if not summary_path.is_file():
            raise ValueError("missing {}".format(summary_path))
        yield summary_path, render_key_value_summary(aggregate_csv(csv_path))

    tables = list((RESULT_ROOT / "parallel").glob("QF_*-results-sumup.txt"))
    tables += list(
        (RESULT_ROOT / "distributed" / "sumup").glob("QF_*-results-sumup.txt")
    )
    for table_path in sorted(tables):
        yield table_path, render_table(table_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="report stale summaries and exit nonzero without modifying files",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="synchronize stale summaries with the per-instance CSV files",
    )
    args = parser.parse_args()

    stale = []
    try:
        for path, expected in expected_files():
            if path.read_text(encoding="utf-8") == expected:
                continue
            stale.append(path)
            if args.write:
                path.write_text(expected, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2

    if stale:
        action = "updated" if args.write else "stale"
        for path in stale:
            print("{}: {}".format(action, path.relative_to(RESULT_ROOT)))
        return 0 if args.write else 1

    print("All per-run and aggregate summary files match the per-instance CSVs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
