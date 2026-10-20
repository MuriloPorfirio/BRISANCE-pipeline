# BRISANCE

**Bioinformatics workflow for Reproducible Identification of Somatic variants and Annotation using NVIDIA and Containerized Execution.**

BRISANCE processes matched tumor–normal whole-genome sequencing reads with NVIDIA Parabricks and containerized downstream tools. This repository brings together the Nextflow implementation, the historical HG008 procedure, and the analyses supporting the study.

**Status:** private preparation draft. The original Nextflow implementation completed a full HG008 run; the reorganized repository has not been rerun on HG008. Outstanding publication checks are listed in [Release checklist](docs/release_checklist.md). This is research software, not a clinically validated diagnostic pipeline.

## Start here

| Purpose | Location |
| --- | --- |
| Run the Nextflow workflow | [Usage](docs/usage.md) and [workflow](workflow/README.md) |
| Check software, hardware and permissions | [Requirements](docs/requirements.md) |
| Identify output files and storage precautions | [Outputs](docs/outputs.md) |
| Understand the original manual HG008 procedure | [Historical Parabricks workflow](historical_workflows/parabricks/README.md) |
| Inspect the CPU comparator | [Historical CPU workflow](historical_workflows/cpu/README.md) |
| Reproduce SNV/indel comparisons | [Variant comparison](analysis/variant_comparison/README.md) |
| Inspect RTG benchmarking | [RTG benchmark](analysis/rtg_benchmark/README.md) |
| Locate VAF and runtime-analysis material | [VAF](analysis/vaf/README.md) and [runtime](analysis/runtime/README.md) |
| Review execution evidence | [Validation](validation/README.md) and [repository checks](validation/repository_checks_2026-10-20.md) |
| Trace the migrated files to their sources | [Provenance](provenance/README.md) |

## Nextflow workflow

```text
Paired FASTQs → Trim Galore / FastQC → fq2bam → ApplyBQSR
            → read-group SM adjustment and indexing → MutectCaller
            → FilterMutectCalls → PASS selection → VEP → positive-TLOD selection
```

The workflow currently supports **one tumor–normal pair**, with one or more paired FASTQ inputs per sample. The tested configuration uses **3 GPUs for fq2bam and 2 for MutectCaller**. GPU counts and thread parameters are fixed in this implementation; this is not yet a general resource-selection interface.

Nextflow's default mode is **metadata validation**, not scientific processing. After preparing a samplesheet:

```bash
nextflow run workflow/main.nf \
  --mode validate \
  --input /absolute/path/to/samplesheet.csv \
  -ansi-log false
```

No FASTQ contents are read in this mode. For reference/cache checks and an explicitly requested full run, follow [Usage](docs/usage.md). Do not run the Turing-specific launchers on another server without adapting their documented environment assumptions.

## Evidence and scope

The full HG008 execution on Turing completed **18 tasks**, all with exit code 0. Its final VCF contained **17,455 records**, all with nonempty `INFO/CSQ` and satisfying `INFO/TLOD>0 && INFO/TLOD!="."`. A comparison with the historical final VCF found 17,455 matching `CHROM/POS/REF/ALT` records and no records unique to either file. These checks do **not** establish byte-identical VCFs, matching genotypes/annotations, independent biological accuracy, or portability to another server. See the [full-run record](validation/hg008_100pct/README.md).

The study's historical CPU–GPU comparison and GPU-scaling experiments are separate from the later Nextflow implementation. Historical results have not been replaced by the new run. Counts of VCF records must not be confused with the manuscript's allele-level SNV/indel counts.

## Data, license and citation

No sequencing reads, BAMs, full VCFs, reference genomes, VEP cache, credentials or server-cleanup utilities are distributed here. Input identifiers and links are documented in [Data and references](docs/data.md).

New BRISANCE material is distributed for non-commercial research, education and personal use under [LICENSE](LICENSE). Preserved source snapshots retain their original terms; see [Licensing](docs/licensing.md). Tool and container licenses remain separate.

Citation metadata is in [CITATION.cff](CITATION.cff). A manuscript/preprint DOI and a versioned release will be added when available; no DOI or release is claimed in this draft.
