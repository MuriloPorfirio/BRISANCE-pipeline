# Outputs

For `--outdir results/my_run/stage1`, default outputs are:

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

**Published files are symlinks into the work directory.** They are not independent copies. Preserve work for access and resume. Copy with a deliberately chosen link strategy and verify the destination before any cleanup; this repository does not delete results or supply a server-cleanup script.

The final expression is `INFO/TLOD>0 && INFO/TLOD!="."` on VEP-annotated PASS records. It is not an optimized RTG score threshold, an AF cutoff, an allele-level SNV/indel classification, or an independently validated clinical confidence criterion.

Nextflow trace/report/timeline files are generated only when their options are supplied. Trace `realtime` and `duration` are different fields. Host peak RSS is not GPU memory; logical-CPU quota is not observed CPU usage; summed task times can double-count overlapping tasks. See [runtime scope](../analysis/runtime/README.md).

Do not remove a zero-variant VCF as a software failure solely because it is empty. The small prefix test exercised valid empty outputs; scientific adequacy must be evaluated separately.
