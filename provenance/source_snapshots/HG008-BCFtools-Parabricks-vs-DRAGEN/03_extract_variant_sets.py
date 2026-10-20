#!/usr/bin/env python3

import csv
import gzip
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, Set, Tuple


@dataclass(frozen=True, order=True)
class Variant:
    chrom: str
    pos: int
    ref: str
    alt: str
    variant_type: str   # SNV, INDEL, OTHER
    indel_subtype: str  # DEL, INS, NA


def open_textfile(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def classify_variant(ref: str, alt: str) -> Tuple[str, str]:
    ref_len = len(ref)
    alt_len = len(alt)

    if ref_len == 1 and alt_len == 1:
        return "SNV", "NA"

    if ref_len != alt_len:
        if ref_len > alt_len:
            return "INDEL", "DEL"
        return "INDEL", "INS"

    if ref_len == alt_len and ref_len > 1:
        return "OTHER", "NA"

    return "OTHER", "NA"


def parse_vcf_to_variant_set(vcf_path: str) -> Set[Variant]:
    variants: Set[Variant] = set()

    with open_textfile(vcf_path) as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue

            fields = line.rstrip("\n").split("\t")
            if len(fields) < 5:
                continue

            chrom = fields[0]
            pos = int(fields[1])
            ref = fields[3]
            alt_field = fields[4]

            alts = alt_field.split(",")

            for alt in alts:
                alt = alt.strip()
                if not alt:
                    continue

                variant_type, indel_subtype = classify_variant(ref, alt)
                variants.add(
                    Variant(
                        chrom=chrom,
                        pos=pos,
                        ref=ref,
                        alt=alt,
                        variant_type=variant_type,
                        indel_subtype=indel_subtype,
                    )
                )

    return variants


def write_variant_table(path: str, variants: Iterable[Variant]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, delimiter="\t")
        writer.writerow(["CHROM", "POS", "REF", "ALT", "TYPE", "INDEL_SUBTYPE"])
        for v in sorted(variants):
            writer.writerow([v.chrom, v.pos, v.ref, v.alt, v.variant_type, v.indel_subtype])


def summarize_variants(variants: Set[Variant]) -> Dict[str, int]:
    summary = {
        "total": len(variants),
        "snvs": 0,
        "indels": 0,
        "indel_del": 0,
        "indel_ins": 0,
        "others": 0,
    }

    for v in variants:
        if v.variant_type == "SNV":
            summary["snvs"] += 1
        elif v.variant_type == "INDEL":
            summary["indels"] += 1
            if v.indel_subtype == "DEL":
                summary["indel_del"] += 1
            elif v.indel_subtype == "INS":
                summary["indel_ins"] += 1
        else:
            summary["others"] += 1

    return summary


def write_summary(path: str, label: str, summary: Dict[str, int]) -> None:
    with open(path, "w", encoding="utf-8") as out:
        out.write(f"sample={label}\n")
        out.write(f"total={summary['total']}\n")
        out.write(f"snvs={summary['snvs']}\n")
        out.write(f"indels={summary['indels']}\n")
        out.write(f"indel_del={summary['indel_del']}\n")
        out.write(f"indel_ins={summary['indel_ins']}\n")
        out.write(f"others={summary['others']}\n")


def export_sample_outputs(sample_name: str, variants: Set[Variant], outdir: str) -> None:
    sample_dir = os.path.join(outdir, sample_name)
    os.makedirs(sample_dir, exist_ok=True)

    snvs = {v for v in variants if v.variant_type == "SNV"}
    indels = {v for v in variants if v.variant_type == "INDEL"}
    others = {v for v in variants if v.variant_type == "OTHER"}

    write_variant_table(os.path.join(sample_dir, "all_variants.tsv"), variants)
    write_variant_table(os.path.join(sample_dir, "snvs.tsv"), snvs)
    write_variant_table(os.path.join(sample_dir, "indels.tsv"), indels)
    write_variant_table(os.path.join(sample_dir, "others.tsv"), others)

    summary = summarize_variants(variants)
    write_summary(os.path.join(sample_dir, "summary.txt"), sample_name, summary)

    print(f"[INFO] Exported {sample_name}:")
    print(f"       total={summary['total']}")
    print(f"       snvs={summary['snvs']}")
    print(f"       indels={summary['indels']} "
          f"(DEL={summary['indel_del']}, INS={summary['indel_ins']})")
    print(f"       others={summary['others']}")
    print(f"       output_dir={sample_dir}")
    print()


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: python3 03_extract_variant_sets.py "
            "<clara.pass.nonsymbolic.vcf.gz> "
            "<dragen.pass.nonsymbolic.vcf.gz> "
            "<output_dir>"
        )
        sys.exit(1)

    clara_vcf = sys.argv[1]
    dragen_vcf = sys.argv[2]
    outdir = sys.argv[3]

    for path in (clara_vcf, dragen_vcf):
        if not os.path.isfile(path):
            print(f"ERROR: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    os.makedirs(outdir, exist_ok=True)

    print("[INFO] Reading CLARA/Parabricks VCF...")
    clara_variants = parse_vcf_to_variant_set(clara_vcf)

    print("[INFO] Reading DRAGEN VCF...")
    dragen_variants = parse_vcf_to_variant_set(dragen_vcf)

    export_sample_outputs("clara", clara_variants, outdir)
    export_sample_outputs("dragen", dragen_variants, outdir)

    print("[INFO] Step 3 completed successfully.")
    print(f"[INFO] Variant-set tables written to: {outdir}")


if __name__ == "__main__":
    main()
