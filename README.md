# BRISANCE

Official repository of BRISANCE, a GPU-accelerated pipeline for somatic short-variant detection in matched tumor–normal whole-genome sequencing data.

BRISANCE stands for *Bioinformatics workflow for Reproducible Identification of Somatic variants and Annotation using NVIDIA and Containerized Execution*.

The pipeline uses NVIDIA Parabricks for alignment, preprocessing and somatic variant calling, followed by GATK filtering and Ensembl VEP annotation. Nextflow manages the execution of these steps with versioned Docker images. This repository also contains the procedures and analyses associated with the HG008 study.

## Workflow

```text
FASTQ → Trim Galore / FastQC → fq2bam → ApplyBQSR → read-group adjustment
      → MutectCaller → FilterMutectCalls → PASS selection → VEP → positive-TLOD selection
```

One tumor–normal pair is processed per run, with multiple paired FASTQ inputs supported for each sample. The implemented configuration uses 3 GPUs for fq2bam and 2 for MutectCaller. Software versions, resource settings and server requirements are described in [Requirements](docs/requirements.md).

## Usage

Prepare a samplesheet using [the HG008 example](assets/hg008_samplesheet.example.csv), then check the input paths:

```bash
nextflow run workflow/main.nf \
  --mode validate \
  --input /absolute/path/to/samplesheet.csv \
  -ansi-log false
```

This command checks metadata without processing the reads. Reference/cache configuration and full execution are described in [Usage](docs/usage.md). Output files and work-directory management are described in [Outputs](docs/outputs.md).

## Repository contents

| Directory | Contents |
| --- | --- |
| [workflow](workflow/README.md) | Nextflow workflow, modules and execution helpers |
| [docs](docs/usage.md) | Requirements, input preparation, execution and outputs |
| [historical_workflows](historical_workflows/README.md) | Manual Parabricks procedure and CPU comparator used in the study |
| [analysis](analysis/README.md) | Variant-set comparison, RTG benchmarking, VAF and runtime analyses |
| [validation](validation/README.md) | HG008 execution records and software tests |
| [provenance](provenance/README.md) | Original repository snapshots and source-file checksums |

## HG008 evaluation

The full-input Nextflow run completed 18 tasks successfully and produced 17,455 final VCF records. All records contained VEP annotations and met the positive-TLOD selection criterion. Comparison with the historical final VCF showed complete agreement for `CHROM`, `POS`, `REF` and `ALT`, with no records exclusive to either file. The comparison scope, execution settings and timings are reported in [Validation](validation/hg008_100pct/README.md).

The historical CPU–GPU benchmark, GPU-scaling experiments and subsequent Nextflow evaluation are reported separately. Data sources and reference resources are listed in [Data and references](docs/data.md).

## License and citation

BRISANCE is available for non-commercial research, education and personal use under [LICENSE](LICENSE). Original source copies retain their respective terms; see [Licensing](docs/licensing.md).

Citation information is provided in [CITATION.cff](CITATION.cff).
