#!/usr/bin/env python3

import csv
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, Set


@dataclass(frozen=True, order=True)
class Variant:
    chrom: str
    pos: int
    ref: str
    alt: str
    variant_type: str
    indel_subtype: str


def load_variant_tsv(tsv_path: str) -> Set[Variant]:
    variants: Set[Variant] = set()

    with open(tsv_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required_columns = {"CHROM", "POS", "REF", "ALT", "TYPE", "INDEL_SUBTYPE"}

        missing = required_columns.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"Missing required columns in {tsv_path}: {', '.join(sorted(missing))}"
            )

        for row in reader:
            variants.add(
                Variant(
                    chrom=row["CHROM"],
                    pos=int(row["POS"]),
                    ref=row["REF"],
                    alt=row["ALT"],
                    variant_type=row["TYPE"],
                    indel_subtype=row["INDEL_SUBTYPE"],
                )
            )

    return variants


def write_variant_table(path: str, variants: Iterable[Variant]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, delimiter="\t")
        writer.writerow(["CHROM", "POS", "REF", "ALT", "TYPE", "INDEL_SUBTYPE"])
        for v in sorted(variants):
            writer.writerow([v.chrom, v.pos, v.ref, v.alt, v.variant_type, v.indel_subtype])


def compute_summary(
    clara_snvs: Set[Variant],
    dragen_snvs: Set[Variant],
    shared_snvs: Set[Variant],
    clara_only_snvs: Set[Variant],
    dragen_only_snvs: Set[Variant],
) -> Dict[str, float]:
    total_union = len(clara_snvs | dragen_snvs)

    shared_pct = (len(shared_snvs) / total_union * 100.0) if total_union else 0.0
    clara_only_pct = (len(clara_only_snvs) / total_union * 100.0) if total_union else 0.0
    dragen_only_pct = (len(dragen_only_snvs) / total_union * 100.0) if total_union else 0.0

    return {
        "clara_total": len(clara_snvs),
        "dragen_total": len(dragen_snvs),
        "shared": len(shared_snvs),
        "clara_only": len(clara_only_snvs),
        "dragen_only": len(dragen_only_snvs),
        "union_total": total_union,
        "shared_pct": shared_pct,
        "clara_only_pct": clara_only_pct,
        "dragen_only_pct": dragen_only_pct,
    }


def write_summary(path: str, summary: Dict[str, float]) -> None:
    with open(path, "w", encoding="utf-8") as out:
        out.write("category=SNVs\n")
        out.write(f"clara_total={summary['clara_total']}\n")
        out.write(f"dragen_total={summary['dragen_total']}\n")
        out.write(f"shared={summary['shared']}\n")
        out.write(f"clara_only={summary['clara_only']}\n")
        out.write(f"dragen_only={summary['dragen_only']}\n")
        out.write(f"union_total={summary['union_total']}\n")
        out.write(f"shared_pct={summary['shared_pct']:.2f}\n")
        out.write(f"clara_only_pct={summary['clara_only_pct']:.2f}\n")
        out.write(f"dragen_only_pct={summary['dragen_only_pct']:.2f}\n")


def print_summary(summary: Dict[str, float]) -> None:
    print("\n=========== SNV COMPARISON SUMMARY ===========")
    print(f"Total SNVs CLARA:        {summary['clara_total']}")
    print(f"Total SNVs DRAGEN:       {summary['dragen_total']}")
    print(f"Shared SNVs:             {summary['shared']}")
    print(f"CLARA-only SNVs:         {summary['clara_only']}")
    print(f"DRAGEN-only SNVs:        {summary['dragen_only']}")
    print()
    print(f"Total SNVs considered:   {summary['union_total']}")
    print("Percentage distribution over the union:")
    print(f"  Shared:                {summary['shared_pct']:.2f}%")
    print(f"  CLARA-only:            {summary['clara_only_pct']:.2f}%")
    print(f"  DRAGEN-only:           {summary['dragen_only_pct']:.2f}%")
    print("=============================================\n")


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: python3 04_compare_snvs.py "
            "<clara/snvs.tsv> <dragen/snvs.tsv> <output_dir>"
        )
        sys.exit(1)

    clara_tsv = sys.argv[1]
    dragen_tsv = sys.argv[2]
    outdir = sys.argv[3]

    for path in (clara_tsv, dragen_tsv):
        if not os.path.isfile(path):
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    os.makedirs(outdir, exist_ok=True)

    print("[INFO] Loading CLARA SNVs...")
    clara_snvs = load_variant_tsv(clara_tsv)

    print("[INFO] Loading DRAGEN SNVs...")
    dragen_snvs = load_variant_tsv(dragen_tsv)

    shared_snvs = clara_snvs & dragen_snvs
    clara_only_snvs = clara_snvs - dragen_snvs
    dragen_only_snvs = dragen_snvs - clara_snvs

    write_variant_table(os.path.join(outdir, "shared_snvs.tsv"), shared_snvs)
    write_variant_table(os.path.join(outdir, "clara_only_snvs.tsv"), clara_only_snvs)
    write_variant_table(os.path.join(outdir, "dragen_only_snvs.tsv"), dragen_only_snvs)

    summary = compute_summary(
        clara_snvs=clara_snvs,
        dragen_snvs=dragen_snvs,
        shared_snvs=shared_snvs,
        clara_only_snvs=clara_only_snvs,
        dragen_only_snvs=dragen_only_snvs,
    )

    write_summary(os.path.join(outdir, "summary.txt"), summary)
    print_summary(summary)

    print(f"[INFO] Results written to: {outdir}")
    print("[INFO] Step 4 completed successfully.")


if __name__ == "__main__":
    main()
