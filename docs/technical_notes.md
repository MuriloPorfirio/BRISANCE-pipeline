# Technical notes

## Workflow configuration

The implemented configuration processes one tumor–normal pair per run, using three alignment GPUs, one ApplyBQSR GPU and two caller GPUs. Thread parameters and resource limits are defined in the scientific modules and `workflow/nextflow.config`. Other GPU counts and execution environments have not been evaluated with this implementation.

## Historical analysis material

The VAF/FILTER-analysis scripts and the complete GPU-scaling scripts, raw timing matrices and plotting inputs are not included in the repository. Their respective analysis sections describe the methods and available material.

The original public file named `05_compare_indels.py` contained table-building code. Its source is retained under `provenance/source_snapshots`. The active replacement implements the documented allele-set comparison and has synthetic test coverage; its HG008 counts have not been re-evaluated.

## Software and record provenance

The full-run tables were transcribed from recorded terminal outputs. The original Turing report archive is identified in the validation record but is not bundled here. Historical RTG scripts use a `:dev` image whose binary version and digest have not been recovered. Historical CPU parameters require the corresponding execution logs where generic scripts do not specify them.

The path-adapted manual HG008 commands are generated from the documented execution sequence. They are maintained separately from both the original script snapshots and the tested Nextflow implementation.

## Counting and timing conventions

The full Nextflow output contained 17,455 VCF records. The manuscript's 17,134 SNV+indel total uses allele-level extraction and classification, excluding other variant classes. These values use different counting units.

The historical GPU timing total is the sum of two fq2bam runs and MutectCaller. Separate ApplyBQSR times are reported separately. A total including that step must account for it explicitly. See [Runtime](../analysis/runtime/README.md).
