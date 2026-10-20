# Historical CPU runtime comparator

The five original scripts are in `originals/`, copied unchanged from `GATK-Somatic-Pipeline`. Their original LICENSE is retained. The source commit is recorded in [Provenance](../../provenance/README.md).

| Script | Intended component |
| --- | --- |
| `1-Alignment-and-SamToBam.sh` | BWA alignment, sorting/indexing |
| `2-MarkDuplicates.sh` | GATK duplicate marking |
| `3-BQSR-table-creation.sh` | BaseRecalibrator |
| `4-ApplyBQSR.sh` | ApplyBQSR |
| `5-VariantCaller.sh` | GATK Mutect2 |

The manuscript documents BWA-MEM 0.7.19-r1273, samtools 1.21 and GATK 4.6.2.0, with step-specific settings in its CPU–GPU comparison table. Some source scripts use moving container tags, original paths, or local GATK. The generic `--threads` argument in the caller wrapper must not be assumed to set Mutect2's scientific thread option; verify the actual invocation/log before asserting that it does.

These files are retained for historical inspection, not advertised as a newly validated portable CPU pipeline. The new BRISANCE GPU workflow does not run them automatically. Preserve the distinction between command versions observed in logs and tags written in scripts.

Do not run them unchanged against existing outputs: they include output creation/overwriting behavior and assumptions about BAM name matching. Actual successful commands/logs and the timing scope must be reconciled before a release claims full CPU comparator reproducibility. No fresh CPU analysis or runtime validation was performed during migration.
