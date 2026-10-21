# Configurable workflow

This entry point runs a paired-end tumor–normal analysis from the editable [settings file](../interface/README.md). It accepts user-selected FASTQs, reference and known-sites files, matching VEP cache, adapters, quality/length cutoffs, GPU indices and resource settings. Use the fixed runner rather than supplying `brisance.json` directly to Nextflow.

```bash
bash interface/run_brisance.sh /absolute/path/analysis.local.ini --check
bash interface/run_brisance.sh /absolute/path/analysis.local.ini --run
```

`--check` reads settings/metadata only. `--run` requires storage confirmation, successful environment checks, a regular-file publication probe, a Nextflow metadata validation and a separate `Start this analysis now? [y/N]:` confirmation. Missing-image downloads require their own approval. The default answer to every confirmation is no. Java/Nextflow executable paths may be set in the INI; environment activation is then unnecessary.

The scientific order is Trim Galore/FastQC, fq2bam, ApplyBQSR, sample-name header adjustment, MutectCaller, compressed raw VCF, FilterMutectCalls, PASS selection, VEP, annotation index and positive-TLOD selection. Lanes are grouped by sample before alignment. Both alignments must finish before recalibration; both adjusted BAMs must finish before calling. The local executor runs **one task at a time**, avoiding competition between GPU stages. This serial scheduling also bounds simultaneous task CPU/memory requests, but does not reserve host resources. Thread parameters and Docker CPU quotas are separate settings.

## Files and publication

The analysis folder contains `results`, `reports` and `work`. Outputs in `results` are regular files, not symbolic links pointing into `work`. Publication uses same-filesystem **hard links**: two directory entries share file content without allocating a second copy of each BAM. Removing a work name does not remove its published result. Editing either name edits the shared content, so results must not be edited during execution/resumption. The runner checks support with a tiny owned probe and stops if hard links cannot be used; there is no silent fallback that doubles storage. See [Nextflow publication modes](https://docs.seqera.io/nextflow/reference/process/directives/publish-dir).

References/cache and inputs are mounted read-only in containers. Internal Nextflow input staging may still use symbolic links; these are managed implementation details, not the published results. Nothing is automatically deleted. Removing work loses intermediate files, task diagnostics and the ability to resume from those task directories even when published results remain.

Each run uses the exact local image IDs checked during preflight, with image pulling and container networking disabled during analysis. It snapshots the configurable pipeline source and parameters under `reports/execution-*`, uses only that snapshot/configuration, and saves logs, trace, HTML report, timeline, start/completion records and final count summaries. A lock prevents two launchers from using the same analysis folder. Existing work/results are refused, not overwritten. This runner starts fresh runs only; it does not implicitly resume an earlier run or retry failures. Use a new analysis folder for a new attempt and preserve failed-run reports.

Storage is checked again immediately before launch. There is no continuous disk-usage monitor, quota enforcement, GPU reservation or automatic cleanup in this entry point. Other users and temporary files can change resource availability during execution.

## Evaluation scope

Modules were adapted from the preserved [HG008 workflow](../workflow/README.md). Changes expose settings, bind checked image IDs and publish regular files; the tested historical source remains unchanged. Existing HG008 results describe that preserved version, not a new full-input evaluation of this configurable entry point.

Automated tests cover parameter lowering, refusals/cancellation and publication behavior. Optional orchestration tests use real Nextflow 26.04.6 with fake scientific executables and a fake Docker CLI (no daemon/containers): a 15-task two-input-pair graph with custom adapters, and a 16-task graph with automatic adapters and multiple tumor lanes. Tests check wiring, generated Docker commands/image IDs and scientific arguments, not biological correctness or real container/GPU execution. GRCh38 was used in the HG008 study; GRCh37 and alternative hardware/resource settings require their own evaluation.
