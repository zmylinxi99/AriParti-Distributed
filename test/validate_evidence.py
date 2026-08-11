#!/usr/bin/env python3
"""Validate the current AriParti-Distributed benchmark and result archive.

This read-only checker treats the current per-instance result CSVs and benchmark
lists as authoritative.  It verifies their inventories, recomputes the public
parallel/distributed summaries, checks the pure-conjunction joins, and validates
the compact full-list ablation bundle without consulting Git history.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmark-lists"
RESULT_ROOT = ROOT / "experiment-results"
CPU_USAGE_ROOT = RESULT_ROOT / "distributed" / "cpu-usage"
DECISIVE = {"sat", "unsat"}
ALLOWED_STATUSES = DECISIVE | {"failed"}
PAR2_PENALTY_SECONDS = Decimal("2400")


class EvidenceError(RuntimeError):
    """Raised when a reader-facing evidence invariant does not hold."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_dict_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_benchmark_list(path: Path) -> list[str]:
    records = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    require(len(records) == len(set(records)), f"duplicate benchmark identifier: {relative(path)}")
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_benchmark_manifest() -> tuple[dict[str, set[str]], int]:
    rows = read_dict_rows(BENCHMARK_ROOT / "manifest.csv")
    require(rows, "benchmark manifest is empty")
    full_lists: dict[str, set[str]] = {}
    for row in rows:
        path = BENCHMARK_ROOT / row["file"]
        require(path.is_file(), f"benchmark list missing: {relative(path)}")
        records = read_benchmark_list(path)
        require(len(records) == int(row["records"]), f"benchmark count mismatch: {relative(path)}")
        if row["scope"] == "all":
            require(row["logic"] not in full_lists, f"duplicate full-list manifest row: {row['logic']}")
            full_lists[row["logic"]] = set(records)
    require(set(full_lists) == {"QF_LRA", "QF_LIA", "QF_NRA", "QF_NIA"}, "full-list logic coverage mismatch")
    return full_lists, len(rows)


def validate_result_manifest() -> int:
    rows = read_dict_rows(RESULT_ROOT / "manifest.csv")
    require(rows, "result manifest is empty")
    for row in rows:
        directory = RESULT_ROOT / row["directory"]
        require(directory.is_dir(), f"result directory missing: {relative(directory)}")
        csv_files = sorted(directory.glob("*.csv"))
        require(len(csv_files) == int(row["csv_files"]), f"CSV inventory mismatch: {relative(directory)}")
        if row["records_per_csv"]:
            expected = int(row["records_per_csv"])
            for path in csv_files:
                with path.open(newline="", encoding="utf-8") as handle:
                    actual = sum(1 for _ in csv.reader(handle))
                require(actual == expected, f"record count mismatch: {relative(path)}")
    return len(rows)


def validate_cpu_usage(full_lists: dict[str, set[str]]) -> tuple[int, int]:
    manifest_path = CPU_USAGE_ROOT / "manifest.csv"
    rows = read_dict_rows(manifest_path)
    require(rows, "CPU-usage manifest is empty")

    listed_paths: set[Path] = set()
    record_count = 0
    for row in rows:
        logic = row["logic"]
        require(logic in full_lists, f"unknown CPU-usage logic: {logic}")
        path = CPU_USAGE_ROOT / row["file"]
        require(path.is_file(), f"CPU-usage file missing: {relative(path)}")
        require(path not in listed_paths, f"duplicate CPU-usage manifest file: {relative(path)}")
        listed_paths.add(path)

        expected_benchmarks = full_lists[logic]
        require(
            int(row["benchmark_list_records"]) == len(expected_benchmarks),
            f"CPU-usage benchmark-list size mismatch: {relative(path)}",
        )
        records: set[str] = set()
        counts: Counter[str] = Counter()
        with path.open(newline="", encoding="utf-8") as handle:
            for line_number, values in enumerate(csv.reader(handle), 1):
                require(len(values) == 4, f"expected 4 CPU-usage CSV columns: {relative(path)}:{line_number}")
                benchmark, status, runtime_text, cpu_text = values
                require(
                    benchmark not in records,
                    f"duplicate CPU-usage benchmark: {relative(path)}:{line_number}",
                )
                require(
                    benchmark in expected_benchmarks,
                    f"CPU-usage benchmark outside stated list: {relative(path)}:{line_number}",
                )
                require(
                    status in ALLOWED_STATUSES,
                    f"unsupported CPU-usage status {status!r}: {relative(path)}:{line_number}",
                )
                try:
                    runtime = Decimal(runtime_text)
                    cpu_usage = Decimal(cpu_text)
                except InvalidOperation as error:
                    raise EvidenceError(f"invalid CPU-usage numeric value: {relative(path)}:{line_number}") from error
                require(
                    runtime.is_finite() and runtime >= 0,
                    f"invalid CPU-usage runtime: {relative(path)}:{line_number}",
                )
                require(
                    cpu_usage.is_finite() and cpu_usage >= 0,
                    f"invalid CPU-usage value: {relative(path)}:{line_number}",
                )
                records.add(benchmark)
                counts[status] += 1

        require(len(records) == int(row["records"]), f"CPU-usage record count mismatch: {relative(path)}")
        for status in ("sat", "unsat", "failed"):
            require(
                counts[status] == int(row[status]),
                f"CPU-usage {status} count mismatch: {relative(path)}",
            )
        require(sha256_file(path) == row["sha256"], f"CPU-usage SHA-256 mismatch: {relative(path)}")
        record_count += len(records)

    actual_paths = set(CPU_USAGE_ROOT.glob("QF_*/*.csv"))
    require(actual_paths == listed_paths, "CPU-usage manifest file inventory mismatch")
    return len(rows), record_count


def read_result_csv(path: Path, expected_benchmarks: set[str]) -> tuple[dict[str, tuple[str, Decimal]], dict[str, int]]:
    records: dict[str, tuple[str, Decimal]] = {}
    counts: Counter[str] = Counter()
    total_for_par2 = Decimal(0)
    with path.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.reader(handle), 1):
            require(len(row) == 3, f"expected 3 CSV columns: {relative(path)}:{line_number}")
            benchmark, status, runtime_text = row
            require(benchmark not in records, f"duplicate result benchmark: {relative(path)}:{line_number}")
            require(status in ALLOWED_STATUSES, f"unsupported result status {status!r}: {relative(path)}:{line_number}")
            try:
                runtime = Decimal(runtime_text)
            except InvalidOperation as error:
                raise EvidenceError(f"invalid runtime: {relative(path)}:{line_number}") from error
            require(runtime.is_finite() and runtime >= 0, f"invalid runtime: {relative(path)}:{line_number}")
            records[benchmark] = (status, runtime)
            counts[status] += 1
            total_for_par2 += runtime if status in DECISIVE else PAR2_PENALTY_SECONDS
    require(set(records) == expected_benchmarks, f"benchmark membership mismatch: {relative(path)}")
    aggregate = {
        "sat": counts["sat"],
        "unsat": counts["unsat"],
        "solved": counts["sat"] + counts["unsat"],
        "failed": len(records) - counts["sat"] - counts["unsat"],
        "PAR-2": int(total_for_par2.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
    }
    return records, aggregate


def parse_key_value_summary(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        require(len(parts) == 2, f"invalid summary line: {relative(path)}:{line_number}")
        values[parts[0]] = int(parts[1])
    return values


def parse_box_table(path: Path) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("│") or "solver" in line:
            continue
        cells = [cell.strip() for cell in line.strip("│").split("│")]
        if len(cells) != 6:
            continue
        solver = cells[0]
        require(solver not in rows, f"duplicate summary row: {relative(path)}: {solver}")
        rows[solver] = dict(zip(("sat", "unsat", "solved", "failed", "PAR-2"), map(int, cells[1:])))
    require(rows, f"no data rows found in summary: {relative(path)}")
    return rows


def logic_from_dataset_name(name: str) -> str:
    match = re.match(r"(QF_[A-Z]+)-\d+$", name)
    require(match is not None, f"unrecognized dataset directory: {name}")
    return match.group(1)


def validate_raw_results(
    full_lists: dict[str, set[str]],
) -> tuple[dict[Path, dict[str, tuple[str, Decimal]]], int, int, int, int]:
    result_records: dict[Path, dict[str, tuple[str, Decimal]]] = {}
    aggregates: dict[Path, dict[str, int]] = {}
    raw_paths = sorted((RESULT_ROOT / "parallel").glob("QF_*-*/*.csv"))
    raw_paths += sorted((RESULT_ROOT / "distributed" / "data").glob("QF_*-*/*.csv"))
    require(raw_paths, "no per-instance result CSVs found")
    record_count = 0
    post_cutoff_decisive = 0
    for path in raw_paths:
        logic = logic_from_dataset_name(path.parent.name)
        records, aggregate = read_result_csv(path, full_lists[logic])
        result_records[path] = records
        aggregates[path] = aggregate
        record_count += len(records)
        post_cutoff_decisive += sum(status in DECISIVE and runtime > Decimal("1200") for status, runtime in records.values())

        if "parallel" in path.parts:
            summary_path = path.with_name(f"{path.stem}-sumup.txt")
            require(summary_path.is_file(), f"per-run summary missing: {relative(summary_path)}")
            require(parse_key_value_summary(summary_path) == aggregate, f"per-run summary mismatch: {relative(summary_path)}")

    table_rows = 0
    for mode in ("parallel", "distributed"):
        if mode == "parallel":
            summary_paths = sorted((RESULT_ROOT / mode).glob("QF_*-results-sumup.txt"))
            data_root = RESULT_ROOT / mode
        else:
            summary_paths = sorted((RESULT_ROOT / mode / "sumup").glob("QF_*-results-sumup.txt"))
            data_root = RESULT_ROOT / mode / "data"
        for summary_path in summary_paths:
            logic_match = re.search(r"(QF_[A-Z]+)", summary_path.name)
            require(logic_match is not None, f"unrecognized summary name: {relative(summary_path)}")
            datasets = [path for path in data_root.glob(f"{logic_match.group(1)}-*") if path.is_dir()]
            require(len(datasets) == 1, f"expected one data directory for {relative(summary_path)}")
            expected = {path.stem: aggregates[path] for path in datasets[0].glob("*.csv")}
            actual = parse_box_table(summary_path)
            require(actual == expected, f"aggregate summary mismatch: {relative(summary_path)}")
            table_rows += len(actual)
    return result_records, len(raw_paths), record_count, table_rows, post_cutoff_decisive


def validate_archive_metadata(post_cutoff_decisive: int) -> None:
    metadata = json.loads((RESULT_ROOT / "metadata.json").read_text(encoding="utf-8"))
    aggregation = metadata["aggregation"]
    require(aggregation["decisive_statuses"] == ["sat", "unsat"], "archive metadata decisive-status mismatch")
    require(aggregation["nominal_timeout_seconds"] == 1200, "archive metadata timeout mismatch")
    require(aggregation["par2_penalty_seconds"] == 2400, "archive metadata PAR-2 penalty mismatch")
    require(
        aggregation["observed_decisive_records_above_nominal_timeout"] == post_cutoff_decisive,
        "archive metadata post-cutoff count mismatch",
    )


def comparison_row(
    subset: list[str],
    ariparti: dict[str, tuple[str, Decimal]],
    baseline: dict[str, tuple[str, Decimal]],
    baseline_only_field: str,
    baseline_faster_field: str,
) -> dict[str, int | str]:
    counts: Counter[str] = Counter()
    for benchmark in subset:
        a_status, a_time = ariparti[benchmark]
        b_status, b_time = baseline[benchmark]
        a_solved = a_status in DECISIVE
        b_solved = b_status in DECISIVE
        if a_solved and b_solved:
            counts["both_solved"] += 1
            if a_time < b_time:
                counts["ariparti_faster"] += 1
            elif b_time < a_time:
                counts[baseline_faster_field] += 1
            else:
                counts["equal_runtime"] += 1
        elif a_solved:
            counts["ariparti_only"] += 1
        elif b_solved:
            counts[baseline_only_field] += 1
        else:
            counts["neither_solved"] += 1
    return {
        "instances": len(subset),
        "both_solved": counts["both_solved"],
        "ariparti_only": counts["ariparti_only"],
        baseline_only_field: counts[baseline_only_field],
        "neither_solved": counts["neither_solved"],
        "ariparti_faster": counts["ariparti_faster"],
        baseline_faster_field: counts[baseline_faster_field],
        "equal_runtime": counts["equal_runtime"],
    }


def validate_derived_summary(
    filename: str,
    logics: tuple[str, ...],
    ariparti_name: str,
    baseline_name: str,
    baseline_only_field: str,
    baseline_faster_field: str,
    result_records: dict[Path, dict[str, tuple[str, Decimal]]],
) -> int:
    path = RESULT_ROOT / "parallel" / filename
    actual_rows = read_dict_rows(path)
    actual = {row.pop("scope"): {key: int(value) for key, value in row.items()} for row in actual_rows}
    expected: dict[str, dict[str, int | str]] = {}
    subsets: dict[str, list[str]] = {}
    for logic in logics:
        subset_path = next((BENCHMARK_ROOT / "pure-conjunction").glob(f"{logic}-pure_conjunction_list-*.txt"))
        subsets[logic] = read_benchmark_list(subset_path)
        dataset = next(path for path in (RESULT_ROOT / "parallel").glob(f"{logic}-*") if path.is_dir())
        a_path = dataset / ariparti_name
        b_path = dataset / baseline_name
        expected[logic] = comparison_row(
            subsets[logic], result_records[a_path], result_records[b_path], baseline_only_field, baseline_faster_field
        )
    grouped_scopes = {"linear": ("QF_LRA", "QF_LIA"), "nonlinear": ("QF_NRA", "QF_NIA")}
    for scope, members in grouped_scopes.items():
        if all(member in logics for member in members):
            expected[scope] = {
                key: sum(int(expected[member][key]) for member in members)
                for key in next(iter(expected.values()))
            }
    require(actual == expected, f"derived pure-conjunction summary mismatch: {relative(path)}")
    return len(actual)


def validate_ablation_bundle(full_lists: dict[str, set[str]]) -> int:
    bundle = RESULT_ROOT / "ablation" / "full-list-p8-1200s"
    checksum_entries = 0
    for line in (bundle / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, filename = line.split(maxsplit=1)
        path = bundle / filename
        require(path.is_file(), f"ablation checksum target missing: {relative(path)}")
        require(sha256_file(path) == digest, f"ablation checksum mismatch: {relative(path)}")
        checksum_entries += 1

    summaries = read_dict_rows(bundle / "summary.csv")
    require(len(summaries) == 12, "ablation summary must contain twelve rows")
    keyed = {(row["theory"], row["variant"]): row for row in summaries}
    launcher_hash = sha256_file(ROOT / "linux-pre_built" / "AriParti_launcher.py")
    partitioner_hash = sha256_file(ROOT / "linux-pre_built" / "binaries" / "partitioner-bin")
    for row in summaries:
        require(int(row["sat"]) + int(row["unsat"]) == int(row["solved"]), "ablation solved-count mismatch")
        require(int(row["solved"]) + int(row["failed"]) == int(row["benchmark_count"]), "ablation benchmark-count mismatch")
        require(int(row["benchmark_count"]) == len(full_lists[row["theory"]]), "ablation list-size mismatch")
        require(row["timeout_seconds"] == "1200" and row["cores"] == "8", "ablation configuration mismatch")
        require(row["launcher_sha256"] == launcher_hash, "ablation launcher identity mismatch")
        require(row["partitioner_sha256"] == partitioner_hash, "ablation partitioner identity mismatch")
        require(row["required_partitioner_sha256"] == partitioner_hash, "ablation required partitioner mismatch")

    deltas = read_dict_rows(bundle / "delta.csv")
    require(len(deltas) == 8, "ablation delta must contain eight rows")
    for row in deltas:
        full = keyed[(row["theory"], "full")]
        variant = keyed[(row["theory"], row["variant"])]
        require(int(row["full_solved"]) == int(full["solved"]), "ablation full solved mismatch")
        require(int(row["variant_solved"]) == int(variant["solved"]), "ablation variant solved mismatch")
        require(int(row["solved_gap_full_minus_variant"]) == int(full["solved"]) - int(variant["solved"]), "ablation solved delta mismatch")
        require(int(row["full_PAR-2"]) == int(full["PAR-2"]), "ablation full PAR-2 mismatch")
        require(int(row["variant_PAR-2"]) == int(variant["PAR-2"]), "ablation variant PAR-2 mismatch")
        require(int(row["par2_gap_variant_minus_full"]) == int(variant["PAR-2"]) - int(full["PAR-2"]), "ablation PAR-2 delta mismatch")

    metadata = json.loads((bundle / "result-metadata.json").read_text(encoding="utf-8"))
    identities = metadata["evaluated_implementation_identity"]
    require(identities["launcher"]["sha256"] == launcher_hash, "ablation metadata launcher mismatch")
    require(identities["partitioner"]["sha256"] == partitioner_hash, "ablation metadata partitioner mismatch")
    return checksum_entries


def main() -> int:
    try:
        full_lists, benchmark_manifest_rows = validate_benchmark_manifest()
        result_manifest_rows = validate_result_manifest()
        cpu_usage_csvs, cpu_usage_records = validate_cpu_usage(full_lists)
        records, raw_csvs, raw_records, table_rows, post_cutoff = validate_raw_results(full_lists)
        validate_archive_metadata(post_cutoff)
        derived_rows = validate_derived_summary(
            "pure-conjunction-p16-summary.csv",
            ("QF_LRA", "QF_LIA", "QF_NRA", "QF_NIA"),
            "AriParti-cvc5-p16.csv",
            "cvc5-1.0.8-p16.csv",
            "cvc5_only",
            "cvc5_faster",
            records,
        )
        derived_rows += validate_derived_summary(
            "pure-conjunction-opensmt2-p16-summary.csv",
            ("QF_LRA", "QF_LIA"),
            "AriParti-osmt2-p16.csv",
            "opensmt-2.5.2-p16.csv",
            "opensmt2_only",
            "opensmt2_faster",
            records,
        )
        checksum_entries = validate_ablation_bundle(full_lists)
    except (EvidenceError, KeyError, StopIteration, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("OK: current-snapshot evidence is internally consistent")
    print(f"  benchmark manifest rows: {benchmark_manifest_rows}")
    print(f"  result manifest rows: {result_manifest_rows}")
    print(f"  per-instance result CSVs/records: {raw_csvs}/{raw_records}")
    print(f"  CPU-usage CSVs/records: {cpu_usage_csvs}/{cpu_usage_records}")
    print(f"  recomputed parallel/distributed table rows: {table_rows}")
    print(f"  recomputed pure-conjunction rows: {derived_rows}")
    print(f"  verified ablation checksum entries: {checksum_entries}")
    print(f"  decisive records above nominal 1200-second cutoff: {post_cutoff} (documented archive behavior)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
