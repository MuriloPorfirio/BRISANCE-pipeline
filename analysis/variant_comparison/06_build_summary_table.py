#!/usr/bin/env python3

import csv
import os
import sys
from typing import Dict, List


def read_key_value_summary(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()

    return data


def to_int(summary: Dict[str, str], key: str) -> int:
    if key not in summary:
        raise KeyError(f"Missing required key '{key}' in summary.")
    return int(float(summary[key]))


def to_float(summary: Dict[str, str], key: str) -> float:
    if key not in summary:
        raise KeyError(f"Missing required key '{key}' in summary.")
    return float(summary[key])


def compute_combined_summary(
    snv_summary: Dict[str, str],
    indel_summary: Dict[str, str],
) -> Dict[str, float]:
    clara_total = to_int(snv_summary, "clara_total") + to_int(indel_summary, "clara_total")
    dragen_total = to_int(snv_summary, "dragen_total") + to_int(indel_summary, "dragen_total")
    shared = to_int(snv_summary, "shared") + to_int(indel_summary, "shared")
    clara_only = to_int(snv_summary, "clara_only") + to_int(indel_summary, "clara_only")
    dragen_only = to_int(snv_summary, "dragen_only") + to_int(indel_summary, "dragen_only")
    union_total = to_int(snv_summary, "union_total") + to_int(indel_summary, "union_total")

    shared_pct = (shared / union_total * 100.0) if union_total else 0.0
    clara_only_pct = (clara_only / union_total * 100.0) if union_total else 0.0
    dragen_only_pct = (dragen_only / union_total * 100.0) if union_total else 0.0

    return {
        "clara_total": clara_total,
        "dragen_total": dragen_total,
        "shared": shared,
        "clara_only": clara_only,
        "dragen_only": dragen_only,
        "union_total": union_total,
        "shared_pct": shared_pct,
        "clara_only_pct": clara_only_pct,
        "dragen_only_pct": dragen_only_pct,
    }


def build_table_rows(
    snv_summary: Dict[str, str],
    indel_summary: Dict[str, str],
    combined_summary: Dict[str, float],
) -> List[List[str]]:
    rows: List[List[str]] = []

    rows.append([
        "SNVs",
        str(to_int(snv_summary, "clara_total")),
        str(to_int(snv_summary, "dragen_total")),
        str(to_int(snv_summary, "shared")),
        str(to_int(snv_summary, "clara_only")),
        str(to_int(snv_summary, "dragen_only")),
        f"{to_float(snv_summary, 'shared_pct'):.2f}",
    ])

    rows.append([
        "InDels",
        str(to_int(indel_summary, "clara_total")),
        str(to_int(indel_summary, "dragen_total")),
        str(to_int(indel_summary, "shared")),
        str(to_int(indel_summary, "clara_only")),
        str(to_int(indel_summary, "dragen_only")),
        f"{to_float(indel_summary, 'shared_pct'):.2f}",
    ])

    rows.append([
        "Total (SNVs + InDels)",
        str(int(combined_summary["clara_total"])),
        str(int(combined_summary["dragen_total"])),
        str(int(combined_summary["shared"])),
        str(int(combined_summary["clara_only"])),
        str(int(combined_summary["dragen_only"])),
        f"{combined_summary['shared_pct']:.2f}",
    ])

    return rows


def write_table_tsv(path: str, rows: List[List[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, delimiter="\t")
        writer.writerow([
            "Category",
            "Parabricks_total",
            "DRAGEN_total",
            "Shared",
            "Parabricks_only",
            "DRAGEN_only",
            "Shared_pct",
        ])
        writer.writerows(rows)


def write_table_csv(path: str, rows: List[List[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow([
            "Category",
            "Parabricks_total",
            "DRAGEN_total",
            "Shared",
            "Parabricks_only",
            "DRAGEN_only",
            "Shared_pct",
        ])
        writer.writerows(rows)


def write_combined_summary(path: str, combined: Dict[str, float]) -> None:
    with open(path, "w", encoding="utf-8") as out:
        out.write("category=SNVs+INDELs\n")
        out.write(f"clara_total={int(combined['clara_total'])}\n")
        out.write(f"dragen_total={int(combined['dragen_total'])}\n")
        out.write(f"shared={int(combined['shared'])}\n")
        out.write(f"clara_only={int(combined['clara_only'])}\n")
        out.write(f"dragen_only={int(combined['dragen_only'])}\n")
        out.write(f"union_total={int(combined['union_total'])}\n")
        out.write(f"shared_pct={combined['shared_pct']:.2f}\n")
        out.write(f"clara_only_pct={combined['clara_only_pct']:.2f}\n")
        out.write(f"dragen_only_pct={combined['dragen_only_pct']:.2f}\n")


def print_combined_summary(combined: Dict[str, float]) -> None:
    print("\n=========== COMBINED SUMMARY (SNVs + InDels) ===========")
    print(f"Total variants CLARA:     {int(combined['clara_total'])}")
    print(f"Total variants DRAGEN:    {int(combined['dragen_total'])}")
    print(f"Shared variants:          {int(combined['shared'])}")
    print(f"Exclusive CLARA:          {int(combined['clara_only'])}")
    print(f"Exclusive DRAGEN:         {int(combined['dragen_only'])}")
    print()
    print(f"Total variants considered: {int(combined['union_total'])}")
    print("Percentage distribution over the union:")
    print(f"  Shared:                 {combined['shared_pct']:.2f}%")
    print(f"  Exclusive CLARA:        {combined['clara_only_pct']:.2f}%")
    print(f"  Exclusive DRAGEN:       {combined['dragen_only_pct']:.2f}%")
    print("========================================================\n")


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: python3 src/06_build_summary_table.py "
            "<snv_summary.txt> <indel_summary.txt> <output_dir>"
        )
        sys.exit(1)

    snv_summary_path = sys.argv[1]
    indel_summary_path = sys.argv[2]
    outdir = sys.argv[3]

    for path in (snv_summary_path, indel_summary_path):
        if not os.path.isfile(path):
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    os.makedirs(outdir, exist_ok=True)

    snv_summary = read_key_value_summary(snv_summary_path)
    indel_summary = read_key_value_summary(indel_summary_path)
    combined_summary = compute_combined_summary(snv_summary, indel_summary)

    rows = build_table_rows(snv_summary, indel_summary, combined_summary)

    write_table_tsv(os.path.join(outdir, "manuscript_table.tsv"), rows)
    write_table_csv(os.path.join(outdir, "manuscript_table.csv"), rows)
    write_combined_summary(os.path.join(outdir, "combined_summary.txt"), combined_summary)

    print_combined_summary(combined_summary)

    print(f"[INFO] Table written to: {os.path.join(outdir, 'manuscript_table.tsv')}")
    print(f"[INFO] Table written to: {os.path.join(outdir, 'manuscript_table.csv')}")
    print(f"[INFO] Combined summary written to: {os.path.join(outdir, 'combined_summary.txt')}")
    print("[INFO] Step 5 completed successfully.")


if __name__ == "__main__":
    main()
