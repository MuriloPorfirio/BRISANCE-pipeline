# Historical CPU runtime comparator

The five original scripts are in `originals/`, copied unchanged from `GATK-Somatic-Pipeline`. Their original LICENSE is retained. The source commit is recorded in [Provenance](../../provenance/README.md).

| Script | Intended component |
| --- | --- |
| `1-Alignment-and-SamToBam.sh` | BWA alignment, sorting/indexing |
| `2-MarkDuplicates.sh` | GATK duplicate marking |
| `3-BQSR-table-creation.sh` | BaseRecalibrator |
| `4-ApplyBQSR.sh` | ApplyBQSR |
| `5-VariantCaller.sh` | GATK Mutect2 |

The study used BWA-MEM 0.7.19-r1273, samtools 1.21 and GATK 4.6.2.0, with step-specific settings in the CPU–GPU comparison table. The source scripts include original server paths, moving container tags and local GATK execution. In the caller wrapper, `--threads` controls samtools indexing; the Mutect2 command does not pass an explicit thread option.

These scripts document the CPU comparator and are executed separately from the BRISANCE GPU workflow. Software versions recorded in execution logs identify the historical environment; moving image tags alone do not.

Configure the paths and BAM-name matching rules before use, and select fresh output directories because scripts can overwrite files. Where the generic scripts omit a historical parameter, the corresponding execution log is needed to establish its value.
