# BRISANCE

BRISANCE is a GPU-accelerated pipeline for somatic short-variant detection in matched tumor–normal whole-genome sequencing data.

BRISANCE stands for *Bioinformatics workflow for Reproducible Identification of Somatic variants and Annotation using NVIDIA and Containerized Execution*.

Nextflow coordinates NVIDIA Parabricks alignment and variant calling, GATK filtering and Ensembl VEP annotation using versioned Docker images. One tumor–normal pair is processed per run, with multiple sequencing lanes supported for each sample.

## Workflow

```text
FASTQ → Trim Galore / FastQC → fq2bam → ApplyBQSR → read-group adjustment
      → MutectCaller → FilterMutectCalls → PASS selection → VEP → positive-TLOD selection
```

## Getting started

Run on a Linux x86_64 server with compatible NVIDIA GPUs, Docker and NVIDIA Container Toolkit. Bash, Python 3.8+ and Git are required. Input data and reference resources must be available on that server. See [Requirements](docs/requirements.md) for software versions and hardware details.

1. Download the repository:

   ```bash
   git clone https://github.com/MuriloPorfirio/BRISANCE-pipeline.git
   cd BRISANCE-pipeline
   ```

2. Prepare Java/Nextflow and create your editable settings file:

   ```bash
   bash setup_brisance.sh
   ```

   Setup reuses existing programs or offers local downloads, then creates `analysis.local.ini`. It does not install Docker or drivers. See [Setup options](docs/setup.md).

3. Edit `analysis.local.ini`: enter your tumor/normal FASTQs, reference FASTA, known-sites VCFs and VEP cache. Set the adapters, quality cutoff, GPU devices and CPU/memory/thread limits for your analysis. [Settings reference](interface/README.md).

4. Check the configuration:

   ```bash
   bash interface/run_brisance.sh analysis.local.ini --check
   ```

5. Run the analysis:

   ```bash
   bash interface/run_brisance.sh analysis.local.ini --run
   ```

   BRISANCE displays the inputs and storage estimate, checks dependencies and asks for confirmation before processing. Missing container images are downloaded only with permission. `--check` performs metadata checks without starting analysis.

See [Usage](docs/usage.md) for run options and [Outputs](docs/outputs.md) for the results layout.

## Repository contents

| Directory | Contents |
| --- | --- |
| [workflow](workflow/README.md) | Preserved HG008 workflow, modules and execution helpers |
| [pipeline](pipeline/README.md) | Configurable execution and regular-file publication |
| [interface](interface/README.md) | Initial setup, editable settings, dependency checks and confirmed launch |
| [docs](docs/usage.md) | Requirements, input preparation, execution and outputs |
| [historical_workflows](historical_workflows/README.md) | Manual Parabricks procedure and CPU comparator used in the study |
| [analysis](analysis/README.md) | Variant-set comparison, RTG benchmarking, VAF and runtime analyses |
| [validation](validation/README.md) | HG008 execution records and software tests |
| [provenance](provenance/README.md) | Original repository snapshots and source-file checksums |

## HG008 evaluation

The full-input HG008 run completed 18 tasks and produced 17,455 final VCF records, matching the historical output for `CHROM`, `POS`, `REF` and `ALT`. [Execution settings, timings and comparison scope](validation/hg008_100pct/README.md) are provided with the validation record. The settings-file interface was tested separately with [small HG008 inputs](validation/interface_hg008_small/README.md).

The original HG008 commands are retained under [HG008 reproduction](docs/hg008-reproduction.md). Dataset and reference sources are listed in [Data and references](docs/data.md).

## Project and authors

BRISANCE is part of InovaCriança — Inovação terapêutica em crianças com tumores sólidos: uma jornada de precisão, supported by the Brazilian Ministry of Health and CNPq through Chamada nº 16/2023 – Saúde de Precisão (MS-SECTICS-Decit/CNPq nº 444217/2023-1).

Authors: Murilo Porfírio de Aguiar; Saloe Bispo; Silvia Aparecida Teixeira; Rui Manuel Reis; Luciane Sussuchi da Silva; Letícia Graziela Costa Santos.

## License

BRISANCE is available for non-commercial research, education and personal use under [LICENSE](LICENSE). Original source copies retain their respective terms; see [Licensing](docs/licensing.md).
