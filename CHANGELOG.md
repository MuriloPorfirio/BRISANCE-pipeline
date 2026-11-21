# Changes

## 1.2.0 — 21 November 2026

- Configure read-orientation artifact modeling and cross-sample contamination independently in the FASTQ or BAM INI. Each section accepts `off`, `auto` or `provided`. Both default to `off`.
- With automatic orientation modeling, MutectCaller saves F1R2 counts and GATK learns tumor-specific priors for FilterMutectCalls.
- With automatic contamination estimation, GATK uses pileups from the tumor and matched normal and a reference-matched, indexed common-SNP resource. It passes the estimate and segmentation to FilterMutectCalls.
- Reuse existing GATK priors or a tumor contamination table with optional segments. The runner checks the requested inputs and records the models used for filtering.
- A GRCh38 WGS pilot completed calling, filtering, annotation and final VCF publication for five matched tumor–normal pairs using existing BAMs, a prepared PoN and both automatic modes. The pilot evaluated end-to-end execution. The software tests cover additional settings, including supplied models and FASTQ input.

See the [INI examples, resource requirements and output paths](docs/somatic-filtering.md).

## 1.1.0 — 16 November 2026

- Optional `input_mode = bam` reuses a coordinate-sorted tumor–normal BAM pair, with input checks and no repeated read processing or BAM copies.
- Optional `[somatic] pon` adds Parabricks panel preparation, MutectCaller `--pon` and `postpon` before FilterMutectCalls. A validated, already prepared panel can be reused with `pon_prepared = true`.
- Optional `[qc] enabled = true` collects metrics independently on both recalibrated/supplied BAMs with `collectmultiplemetrics --out-qc-metrics-dir`.
- Explicit `--run --yes` supports unattended sequential analyses, records authorization and disables downloads.
- Existing INIs keep their default scientific processing. Historical HG008 workflows, benchmarks and tool versions remain unchanged.
- New behavior is covered by software and simulated-tool orchestration tests. Patient PoN comparisons are a separate scientific execution; no improved accuracy or reduced missense count is asserted.

## 1.0.0 — 4 November 2026

Initial tagged release of the configurable workflow and preserved HG008 evaluation.
