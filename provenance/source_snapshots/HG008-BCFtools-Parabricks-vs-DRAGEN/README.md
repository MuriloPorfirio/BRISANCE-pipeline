# HG008-BCFtools-Parabricks-vs-DRAGEN

This repository contains the scripts used to reproduce the **variant-set comparison** between the **Parabricks tumor–normal call set** and the **Cancer Genome in a Bottle (GIAB)-provided DRAGEN hard-filtered baseline** for the HG008 matched tumor–normal dataset.

The workflow implemented here supports the analyses reported in the manuscript section on **variant-set comparison between pipelines**. In brief, the repository:

- prepares the two input VCFs in the same way used for the manuscript comparison,
- generates an initial comparative summary with `bcftools stats`,
- extracts allele-level variant sets from both VCFs,
- computes shared and pipeline-specific counts for **SNVs** and **InDels**, and
- builds the final summary table used for manuscript reporting.

---

## Overview

The comparison was designed to evaluate agreement between:

- the **Parabricks-derived somatic tumor–normal VCF** (after filtering/selection), and
- the **GIAB DRAGEN hard-filtered baseline VCF**.

The final manuscript-level counts are based on **PASS-filtered, non-symbolic variants**, compared at the **allele level** using the tuple:

`(CHROM, POS, REF, ALT)`

This means that two variants are considered matching only when they have the same chromosome, genomic position, reference allele, and alternate allele.

---

## What this repository reproduces

This repository reproduces the following analytical components:

1. **Preparation of the two VCFs**
   - retain only `PASS` records,
   - exclude symbolic ALT alleles,
   - compress/index the prepared VCFs.

2. **Pairwise comparative summary using `bcftools stats`**
   - generate a `.stats` file for the two prepared VCFs,
   - preserve the intermediate comparative summary stage used during inspection.

3. **Allele-level post-processing in Python**
   - split multi-allelic entries into individual variants,
   - classify variants as **SNVs**, **InDels**, or **other**,
   - calculate shared and pipeline-specific counts.

4. **Final manuscript table generation**
   - SNVs,
   - InDels,
   - combined total (**SNVs + InDels**).

---

## Required software

### Containerized tools

The workflow relies on the following containerized tools:

#### 1. `bcftools`
Used to:
- filter VCFs,
- index prepared VCFs,
- generate pairwise comparative statistics.

Recommended image:
- `staphb/bcftools.1.21`

#### 2. NVIDIA Parabricks
This repository does **not** run the full upstream Parabricks variant-calling workflow itself, but the repository assumes that the Parabricks-derived somatic VCF has already been generated upstream.

Recorded upstream image used to generate the accelerated call set:
- `nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1`

### Python

The Python scripts in this repository use only the **Python standard library**. No external Python packages are required for the six scripts currently included here.

Recommended:
- Python 3

---

## Input files required

You will need two bgzip-compressed VCFs:

1. **Parabricks / CLARA call set**
   - the filtered tumor–normal somatic VCF produced upstream from the Parabricks workflow

2. **DRAGEN baseline call set**
   - `dragen_4.2.4_HG008-mosaic_tumor.hard-filtered.vcf.gz`

Both files should be:
- indexed (`.tbi` or `.csi`)
- readable by `bcftools`

---

## Repository contents

### `01_prepare_pass_vcfs.sh`
Prepares both input VCFs for comparison.

What it does:
- keeps only `PASS` variants,
- removes symbolic ALT alleles,
- writes compressed/indexed output VCFs,
- generates simple per-file summaries.

Outputs:
- `clara.pass.nonsymbolic.vcf.gz`
- `dragen.pass.nonsymbolic.vcf.gz`

---

### `02_run_bcftools_stats.sh`
Runs `bcftools stats` on the two prepared VCFs.

What it does:
- generates a pairwise `.stats` file,
- runs `plot-vcfstats`,
- preserves the comparative summary stage used for inspection.

Outputs include:
- `comparison_pass.stats`
- `comparison_pass_plots/`

---

### `03_extract_variant_sets.py`
Reads the prepared VCFs and converts them into comparable allele-level variant sets.

What it does:
- parses each VCF record,
- splits multi-allelic sites into individual variants,
- classifies variants as `SNV`, `INDEL`, or `OTHER`,
- exports per-sample tables.

Comparison identity is based on:
- chromosome
- position
- REF
- ALT

Outputs include:
- `all_variants.tsv`
- `snvs.tsv`
- `indels.tsv`
- `others.tsv`
- `summary.txt`

---

### `04_compare_snvs.py`
Compares the SNV sets from the two pipelines.

What it does:
- computes shared SNVs,
- computes Parabricks-only SNVs,
- computes DRAGEN-only SNVs,
- writes a summary file for downstream manuscript reporting.

Outputs include:
- `shared_snvs.tsv`
- `clara_only_snvs.tsv`
- `dragen_only_snvs.tsv`
- `summary.txt`

---

### `05_compare_indels.py`
Compares the InDel sets from the two pipelines.

What it does:
- computes shared InDels,
- computes Parabricks-only InDels,
- computes DRAGEN-only InDels,
- separately summarizes deletions and insertions.

Outputs include:
- `shared_indels.tsv`
- `clara_only_indels.tsv`
- `dragen_only_indels.tsv`
- `summary.txt`

---

### `06_build_summary_table.py`
Builds the final manuscript summary table from the SNV and InDel summaries.

What it does:
- combines the outputs of steps 4 and 5,
- generates the final comparison table,
- writes a combined summary for **SNVs + InDels**.

Outputs include:
- `manuscript_table.tsv`
- `manuscript_table.csv`
- `combined_summary.txt`

---

## Recommended execution order

Run the scripts in the following order:

```bash
bash 01_prepare_pass_vcfs.sh \
    /path/to/clara_calls.vcf.gz \
    /path/to/dragen_baseline.vcf.gz \
    results/01_prepared

bash 02_run_bcftools_stats.sh \
    results/01_prepared/clara.pass.nonsymbolic.vcf.gz \
    results/01_prepared/dragen.pass.nonsymbolic.vcf.gz \
    results/02_bcftools_stats

python3 03_extract_variant_sets.py \
    results/01_prepared/clara.pass.nonsymbolic.vcf.gz \
    results/01_prepared/dragen.pass.nonsymbolic.vcf.gz \
    results/03_variant_sets

python3 04_compare_snvs.py \
    results/03_variant_sets/clara/snvs.tsv \
    results/03_variant_sets/dragen/snvs.tsv \
    results/04_snv_comparison

python3 05_compare_indels.py \
    results/03_variant_sets/clara/indels.tsv \
    results/03_variant_sets/dragen/indels.tsv \
    results/05_indel_comparison

python3 06_build_summary_table.py \
    results/04_snv_comparison/summary.txt \
    results/05_indel_comparison/summary.txt \
    results/06_final_summary
