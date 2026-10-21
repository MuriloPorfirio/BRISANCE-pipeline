# Outputs

The settings-file runner creates an analysis folder with `brisance.json`, `samplesheet.csv`, `results/`, `reports/` and `work/`. All input files remain at their original locations. `reports/settings-*` records the confirmed INI/summary/storage estimate. `reports/environment-*` records dependency/access checks, and `reports/execution-*` records each launch's source snapshot, parameters, versions/image IDs, logs, trace, HTML report, timeline and completion status.

Stage outputs below are inside that analysis folder's `results/`. For the preserved HG008 direct entry point, the same stage layout starts at the parent of `--outdir results/my_run/stage1`.

| Directory | Contents |
| --- | --- |
| `stage1/trimmed/<sample>/<pair_id>/` | Trimmed mates, trimming reports, FastQC HTML/ZIP and versions |
| `stage2/aligned/<sample>/` | BAM/index, duplicate metrics, recalibration table, versions/configuration |
| `stage3/recalibrated/<sample>/` | Separate ApplyBQSR BAM/index, versions/configuration |
| `stage4/read_groups/<sample>/` | SM-adjusted BAM/new index, before/after headers and versions |
| `stage5/variants/<tumor>_vs_<normal>/` | Raw MutectCaller VCF and `.vcf.stats` |
| `stage6/filtered/<tumor>_vs_<normal>/` | Compressed raw VCF, FilterMutectCalls VCF, filtering statistics, PASS VCF and indexes/counts |
| `stage7/annotated/<tumor>_vs_<normal>/` | VEP VCF/index, HTML statistics, warnings when produced, versions/cache metadata/counts |
| `stage8/final/<tumor>_vs_<normal>/` | `*.PASS_TLOD.vcf.gz`, index, expression/configuration and counts |

## Publication and work files

In the configurable entry point, published outputs are **regular files**, not symbolic links. Same-filesystem hard links share the stored content with work files without allocating another full BAM copy. Removing one work filename does not invalidate a published result, but editing either name edits the shared content. Do not modify outputs during execution. Keep work/intermediates and reports for diagnostics and possible controlled resumption; the fixed runner does not automatically resume or clean anything. Disk space shared by hard links is released only after every link is removed.

In the preserved HG008 workflow, published outputs are **symbolic links into work**. These are not independent copies; deleting work invalidates them. When moving/archiving an existing analysis, choose a link strategy deliberately and verify the destination before considering cleanup. No server-cleanup command is part of the public runner.

The final expression is `INFO/TLOD>0 && INFO/TLOD!="."` on VEP-annotated PASS records. It is not an optimized RTG score threshold, an AF cutoff, an allele-level SNV/indel classification, or an independently validated clinical confidence criterion.

The settings-file runner requests Nextflow trace/report/timeline files automatically; the preserved direct command requires their corresponding options. Trace `realtime` and `duration` are different fields. Host peak RSS is not GPU memory; logical-CPU quota is not observed CPU usage; summed task times can double-count overlapping tasks. See [runtime scope](../analysis/runtime/README.md).

Do not remove a zero-variant VCF as a software failure solely because it is empty. The small prefix test exercised valid empty outputs; scientific adequacy must be evaluated separately.
