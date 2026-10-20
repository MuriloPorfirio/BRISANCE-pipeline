# Parabricks SNVs & INDELs GPU Pipeline (Docker, Linux server)

**GPU‑accelerated** pipeline for NGS processing using **NVIDIA Parabricks**. Runs on a **Linux server** with **Docker** and **NVIDIA GPUs**. The focus is performance (GPU) and reproducibility (pinned Docker images).

---

## What this pipeline does

* Trim paired‑end FASTQs with optional FastQC
* FASTQ alignment/mapping (**FASTQ → BAM**) using Parabricks, mark duplicates, and produce a **BQSR table**
* Validate / fix **Read Groups (RG)** if needed
* Apply **BQSR** (GPU)
* Call somatic variants (Parabricks Mutect2)
* Annotate variants (VEP and dbSNP using GPU)

---

## Requirements

* **Linux server** (tested on modern Ubuntu 22.04.5 LTS (Jammy Jellyfish))
* **NVIDIA A100-SXM4-80GB** (CUDA Version: 12.2) and **NVIDIA Driver Version: 535.216.03** installed on host
* **Docker version 27.1.2, build d01f264** installed
* **Toolkit NVIDIA Container Toolkit CLI version 1.17.4
commit: 9b69590c7428470a72f2ae05f826412976af1395** (so containers can see the GPU)
* Enough **RAM** and **disk** for your datasets

Quick checks:

```bash
nvidia-smi            # GPU visible?
docker --version      # Docker installed?
nvidia-ctk --version
```

---

## Docker images (with versions)

| Purpose                                                         | Image                                   | Version   |
| --------------------------------------------------------------- | --------------------------------------- | --------- |
| Trimming + FastQC                                               | `biowardrobe2/trimgalore`               | `v0.4.4`  |
| Parabricks (core tools: fq2bam, applybqsr, mutectcaller, dbsnp) | `nvcr.io/nvidia/clara/clara-parabricks` | `4.5.1-1` |
| BAM utilities (index, header checks)                            | `staphb/samtools`                       | `1.19`    |
| GATK (RG fixes, BaseRecalibrator)                               | `broadinstitute/gatk`                   | `latest`  |
| Variant Effect Predictor                                        | `ensemblorg/ensembl-vep`                | `latest`  |

---

## Folder layout (suggested)

```
/Genomes/                 # reference FASTA, .fai, .dict, known sites (VCFs)
/FASTQ/                   # raw or trimmed FASTQs
/BAM/                     # BAMs and indices
/VCFs/                    # VCF outputs
/logs/                    # logs from each step
```

---

## End‑to‑end flow (with RG‑dependent branch)

```mermaid
flowchart LR
    A["1. Trimming_w_fastqc.sh (Trim Galore + optional FastQC)"] --> B["2. fq2bam_PARABRICKS_n_BQRS-table-creation.sh (fq2bam + dup-mark + BQSR table)"]
    B --> C["3. Indexing-n-ReadGroupsChecking.sh (check @RG / SM / ID / PU; index if missing)"]
    C -->|RG OK| E["4. ApplyBQSR_PARABRICKS.sh (apply BQSR on GPU)"]
    C -->|RG wrong| D["3.1 Indexing-n-AddOrReplaceReadGroups_GATK.sh (fix RG with GATK)"]
    D --> F["3.2 BaseRecalibrator_GATK.sh (recreate BQSR table)"]
    F --> E
    E --> G["4.1 indexing (index recalibrated BAM)"]
    G --> H["5. Mutect2_PARABRICKS.sh (somatic SNVs/indels)"]
    H --> I["6. Variants-Annotations-VEPensembl.sh (VEP functional annotation)"]
    H --> J["7. Variant_Annotation-dbSNP_PARABRICKS.sh (add rsIDs with dbSNP on GPU)"]
```

---

## How to run (script by script)

Edit paths/variables **inside each script** before running (mounts, reference, known sites, output folders, GPU selection like `--gpus device=7` or `--gpus all`).

### 1) Trimming + (optional) FastQC

**Script:** `1-Trimming_w_fastqc.sh`
**Image:** `biowardrobe2/trimgalore:v0.4.4`

* Trims adapters and low‑quality ends (e.g., Q20, min length 20)
* **FastQC optional** (enable/disable in script)
* Outputs: trimmed FASTQs, QC reports, logs

### 2) FASTQ → BAM + duplicates + BQSR table (GPU)

**Script:** `2-fq2bam_PARABRICKS_n_BQRS-table-creation.sh`
**Image:** `nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1`

* Converts paired FASTQs to BAM, marks duplicates
* Creates **BQSR table** and duplicate metrics
* GPU sort/write enabled (fast)

### 3) Index + Read Group checking

**Script:** `3-Indexing-n-ReadGroupsChecking.sh`
**Image:** `staphb/samtools:1.19`

* Shows `@RG` blocks and key tags (`SM`, `ID`, `PU`, `PL`, `LB`)
* Checks sort order (`@HD SO`)
* Indexes BAM if `.bai` missing

### 3.1) Fix Read Groups (if needed)

**Script:** `3.1-Indexing-n-AddOrReplaceReadGroups_GATK.sh`
**Image:** `broadinstitute/gatk:latest`

* Adds or replaces RG fields (`RGID`, `RGLB`, `RGPL`, `RGPU`, `RGSM`)
* Writes `*_fixed.bam` and creates `.bai`

### 3.2) Recreate BQSR table (if RG was fixed)

**Script:** `3.2-BaseRecalibrator_GATK.sh`
**Image:** `broadinstitute/gatk:latest`

* Runs **GATK BaseRecalibrator**
* Uses known sites (Mills indels, 1000G, etc.)
* Outputs a new `.recal.table`

### 4) Apply BQSR (GPU)

**Script:** `4-ApplyBQSR_PARABRICKS.sh`
**Image:** `nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1`

* Applies BQSR to BAM using Parabricks (fast)

### 4.1) Index recalibrated BAM

**Script:** `4.1-indexing`
**Image:** `staphb/samtools:1.19`

* Indexes `*.recal.bam` (or `*.bqsr.bam`) → creates `.bai`

### 5) Somatic variant calling (GPU)

**Script:** `5-Mutect2_PARABRICKS.sh`
**Image:** `nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1`

* **Mutect2 (Parabricks MutectCaller)** — tumor‑only or tumor/normal
* Requires correct `SM` tags in BAM headers (match `--tumor-name` / `--normal-name`)
* Outputs: somatic VCF + log

### 6) Functional annotation (VEP)

**Script:** `6-Variants-Annotations-VEPensembl.sh`
**Image:** `ensemblorg/ensembl-vep:latest`

* Adds gene/transcript consequences (missense, stop‑gain, etc.)
* Output: `*.vep.txt` (can also output VCF if configured)

### 7) Add rsIDs with dbSNP (GPU)

**Script:** `7-Variant_Annotation-dbSNP_PARABRICKS.sh`
**Image:** `nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1`

* Annotates VCF with **dbSNP** identifiers (`rsID`)
* Output: `*_annotado_dbsnp.vcf.gz`

---

## Notes & tips

* **GPU selection**: you can target a specific GPU, e.g. `--gpus device=7`, or use all with `--gpus all`.
* **Threads/Memory**: tune thread counts and RAM according to your server. Parabricks tools expose knobs like `--num-htvc-threads`.
* **Known sites**: make sure VCFs are indexed (`.tbi`) and match your reference build (e.g., GRCh38).
* **Reproducibility**: keep image versions pinned; record exact references/VCFs used in each run.

---

## Troubleshooting (quick)

* **RG mismatch**: If `SM` in BAM header does not match names passed to Mutect2, fix RGs (step **3.1**), then **recreate BQSR** (step **3.3**) and **re‑apply** (step **4**).
* **Missing indexes**: If BAM or VCF lacks index, create with samtools (`samtools index file.bam`) or `tabix` for bgzipped VCFs.
* **GPU not visible in container**: check NVIDIA Container Toolkit install; try `docker run --rm --gpus all nvidia/cuda:12.3.2-base nvidia-smi`.

---

## License (Non‑Commercial)

This project is released for **personal, educational, or research use only**. **Commercial use is not allowed** without explicit permission from the author. See the **LICENSE** file for full terms.

> Copyright (c) 2025 **Murilo Porfírio de Aguiar**
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to use, copy, and modify the Software for personal, educational, or research purposes only, subject to the following conditions:
>
> 1. **Non‑Commercial Use Only**: The Software may not be used, in whole or in part, for any commercial purpose. Commercial use includes, but is not limited to: selling copies of the Software; selling products or services that include or are derived from the Software; using the Software in paid projects, whether for direct sale or internal commercial benefit.
> 2. **No Resale**: You may not sell, sublicense, rent, lease, or otherwise distribute the Software for financial gain.
> 3. **Credit to Original Author**: All copies or substantial portions of the Software must retain the above copyright notice and this permission notice. The original author, **Murilo Porfírio de Aguiar**, must be clearly credited in any use, distribution, or derivative work.
> 4. **No Warranty**: The Software is provided "as is", without warranty of any kind, express or implied.
> 5. **Modification and Distribution**: You may modify and share the Software only if the new work also follows this same license (non‑commercial) and clear attribution to the original author is maintained.
>
> Any violation of these terms will result in automatic termination of this license. For commercial use or special exceptions, contact: **[murilo.porfirio@yahoo.com](mailto:murilo.porfirio@yahoo.com)**.

---

## Citation

If this pipeline helps your work, please cite this repository and the Docker images used (Parabricks, GATK, VEP, samtools, Trim Galore).

---

## Maintainer

**Murilo Porfírio de Aguiar** — issues and questions welcome.
