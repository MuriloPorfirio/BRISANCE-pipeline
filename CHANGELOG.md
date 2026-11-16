# Changes

## 1.1.0 — 16 November 2026

- Optional `input_mode = bam` reuses a coordinate-sorted tumor–normal BAM pair, with input checks and no repeated read processing or BAM copies.
- Optional `[somatic] pon` adds Parabricks panel preparation, MutectCaller `--pon` and `postpon` before FilterMutectCalls. A validated, already prepared panel can be reused with `pon_prepared = true`.
- Optional `[qc] enabled = true` collects metrics independently on both recalibrated/supplied BAMs with `collectmultiplemetrics --out-qc-metrics-dir`.
- Explicit `--run --yes` supports unattended sequential analyses, records authorization and disables downloads.
- Existing INIs keep their default scientific processing. Historical HG008 workflows, benchmarks and tool versions remain unchanged.
- New behavior is covered by software and simulated-tool orchestration tests. Patient PoN comparisons are a separate scientific execution; no improved accuracy or reduced missense count is asserted.

## 1.0.0 — 4 November 2026

Initial tagged release of the configurable workflow and preserved HG008 evaluation.
