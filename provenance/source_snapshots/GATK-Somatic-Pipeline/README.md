# GATK-Somatic-Pipeline

Pipeline em shell para teste de tempo de processamento de alinhamento e chamada de variantes somáticas em dados da linhagem celular **HG008**, no contexto do consórcio **Cancer Genome in a Bottle (GIAB)**.

## Purpose

This repository was created specifically to evaluate the computational time required for two major stages of a somatic variant calling workflow:

1. **Read alignment**
2. **Somatic variant calling**

The analysis was performed on **HG008 tumor-normal data** from the Cancer Genome in a Bottle context, with emphasis on execution strategy, resource control, intermediate files, and processing time.

This repository is not intended to be a polished production-grade workflow manager. Instead, it serves as a **documented experimental pipeline** for benchmarking and technical inspection of the steps involved.

## Study context

The workflow uses previously trimmed FASTQ files and processes a tumor-normal pair:

- **Tumor / somatic sample:** 4 paired-end FASTQ pairs
- **Normal / germline sample:** 1 paired-end FASTQ pair

The trimmed FASTQs used in this analysis were stored in a previous processing directory and reused for this benchmark-oriented pipeline. The tumor sample was merged from multiple FASTQ pairs before alignment, while the normal sample used a single FASTQ pair. :contentReference[oaicite:2]{index=2}

## Input data structure

### Tumor / somatic input
Four paired FASTQ files were used for the somatic sample:

- `HM22JDSX7-2-IDUDI0031_S12_L002_R1_001_val_1.fq.gz`
- `HM22JDSX7-2-IDUDI0031_S12_L002_R2_001_val_2.fq.gz`
- `HM2CNDSX7-2-IDUDI0031_S26_L002_R1_001_val_1.fq.gz`
- `HM2CNDSX7-2-IDUDI0031_S26_L002_R2_001_val_2.fq.gz`
- `HJVHNDSX7-1-IDUDI0031_S12_L001_R1_001_val_1.fq.gz`
- `HJVHNDSX7-1-IDUDI0031_S12_L001_R2_001_val_2.fq.gz`
- `HVWWFDSX7-2-IDUDI0031_S138_L002_R1_001_val_1.fq.gz`
- `HVWWFDSX7-2-IDUDI0031_S138_L002_R2_001_val_2.fq.gz`

### Normal / germline input
One paired FASTQ file was used for the germline sample:

- `HV5TMDSX7-1-IDUDI0034_S1_L001_R1_001_val_1.fq.gz`
- `HV5TMDSX7-1-IDUDI0034_S1_L001_R2_001_val_2.fq.gz`

## Reference genome

The workflow uses the following GIAB-related human reference FASTA:

`GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta`

For BWA-based alignment, the corresponding index files are required alongside the FASTA:

- `.amb`
- `.ann`
- `.bwt`
- `.pac`
- `.sa`

In this project, those files were already available and reused directly instead of being regenerated. :contentReference[oaicite:3]{index=3}

## General workflow

The pipeline is organized into sequential shell-script-based stages.

### 1. Trimming and FastQC
This stage was **not rerun** as part of this repository’s benchmark workflow. Previously trimmed FASTQs were reused as input for the alignment stage. :contentReference[oaicite:4]{index=4}

### 2. Alignment
Alignment was performed with **BWA**, using Docker in the original alignment stage, followed by **samtools** for SAM-to-BAM conversion, sorting, and indexing.

Main characteristics of this step:

- CPU-based execution
- Explicit resource limiting
- Tumor FASTQ merging before alignment
- SAM generation with `bwa mem`
- BAM sorting with `samtools sort`
- BAM indexing with `samtools index`

A key practical point in this project is that, unlike more opinionated tools such as Parabricks, the BWA + samtools approach required **manual control of CPU threads, memory, and temporary directories**. :contentReference[oaicite:5]{index=5}

### 3. Mark duplicates
Duplicate marking is part of the broader workflow structure documented for this analysis.

### 4. Generate BQSR tables
BQSR table generation is part of the pipeline design.

### 5. Apply BQSR
BQSR-applied BAMs were later validated with quick sanity checks before proceeding to variant calling.

### 6. Somatic variant calling
Variant calling was planned with **GATK Mutect2**. Initial attempts using the Docker image `broadinstitute/gatk:latest` encountered storage-related issues on the host system. After that, the strategy moved toward local execution using Conda/GATK in the computational environment. :contentReference[oaicite:6]{index=6}

## Tools and execution approach

The repository documents practical use of the following tools and environments:

- **BWA**
- **samtools**
- **GATK / Mutect2**
- **Docker**
- **screen**
- **bash**

The project emphasizes execution realism in shared infrastructure, including:

- manual resource caps
- container-based execution
- logging
- sanity checks
- inspection of generated intermediate files
- benchmarking-oriented documentation

## Alignment implementation notes

For alignment, the somatic sample was assembled from merged FASTQ files and then processed with `bwa mem`, followed by BAM sorting and indexing with samtools.

The germline alignment script was later improved to include:

- log capture with `tee`
- explicit timing files
- sanity checks for reference and index presence
- version recording for containerized tools
- `samtools quickcheck` validation

This makes the repository useful not only as a workflow example, but also as a record of iterative refinement during benchmarking. 

## Repository scope

This repository is intended to document:

- the technical structure of the pipeline
- the reasoning behind tool selection
- execution constraints observed in practice
- timing-oriented benchmarking of the workflow
- reproducible shell-based implementation details

It is especially relevant for users interested in comparing practical execution behavior between more manual CPU-based pipelines and more automated solutions.

## Current status

This repository represents an evolving technical workflow for:

- benchmark-oriented somatic pipeline execution
- alignment of HG008 tumor-normal data
- downstream somatic variant calling
- documentation of computational processing behavior

Additional documentation may be added later to describe exact software versions, command-line parameters, runtime summaries, and interpretation of output files.

## Notes

- This repository prioritizes **technical transparency** over workflow abstraction.
- Paths and infrastructure details reflect the original execution environment.
- Some steps were adapted during execution as infrastructure constraints were identified.

## Limitations

- This repository reflects a benchmarking-oriented workflow rather than a production-ready pipeline.
- Scripts were developed for a specific execution environment and may require adaptation.
- Paths, infrastructure assumptions, and external dependencies are not fully generalized.
- Some required data and preparation steps are external to this repository.
