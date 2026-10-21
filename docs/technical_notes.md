# Technical notes

## Workflow configuration

The preserved HG008 configuration processes one tumor–normal pair per run, using three alignment GPUs, one ApplyBQSR GPU and two caller GPUs. Thread parameters and resource limits are defined in the scientific modules and `workflow/nextflow.config`. Other GPU counts and execution environments have not received that full-input evaluation.

The separate [settings-file interface](../interface/README.md) generates identifiers/configuration and checks dependencies/access. Its `--run` option requests the [configurable entry point](../pipeline/README.md), with an additional confirmation after successful checks. GPU indices, CPU/memory/thread settings, adapters and reference-resource paths are propagated to separate configurable modules. The local executor runs one task at a time. Results use regular hard-linked publication without a second full BAM copy; no automatic cleanup occurs. The configuration schema is not accepted by the preserved HG008 entry point. Synthetic orchestration tests evaluate software behavior, not HG008 variant-calling accuracy.

## Historical analysis material

The VAF/FILTER-analysis scripts and the complete GPU-scaling scripts, raw timing matrices and plotting inputs are not included in the repository. Their respective analysis sections describe the methods and available material.

The original public file named `05_compare_indels.py` contained table-building code. Its source is retained under `provenance/source_snapshots`. The active replacement implements the documented allele-set comparison and has synthetic test coverage; its HG008 counts have not been re-evaluated.

## Software and record provenance

The [initial setup](setup.md) is separate from dependency preflight and scientific execution. It pins the standalone Nextflow 26.04.6 distribution and can install a verified private Temurin Java 21 fallback, without changing system Java/Docker/drivers. Runtime/setup checks do not constitute another biological evaluation. Setup records actual selected versions; it does not relabel its fallback Java as the HG008 study's Conda build.

The full-run tables were transcribed from recorded terminal outputs. The original Turing report archive is identified in the validation record but is not bundled here. Historical RTG scripts use a `:dev` image whose binary version and digest have not been recovered. Historical CPU parameters require the corresponding execution logs where generic scripts do not specify them.

The path-adapted manual HG008 commands are generated from the documented execution sequence. They are maintained separately from both the original script snapshots and the tested Nextflow implementation.

## Counting and timing conventions

The full Nextflow output contained 17,455 VCF records. The manuscript's 17,134 SNV+indel total uses allele-level extraction and classification, excluding other variant classes. These values use different counting units.

The historical GPU timing total is the sum of two fq2bam runs and MutectCaller. Separate ApplyBQSR times are reported separately. A total including that step must account for it explicitly. See [Runtime](../analysis/runtime/README.md).
