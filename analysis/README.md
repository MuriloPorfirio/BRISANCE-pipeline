# Study analyses

These analyses are separate from normal FASTQ-to-VCF Nextflow processing. They are not all automatically run by `--mode finalize`.

| Section | Purpose | Preparation status |
| --- | --- | --- |
| [Variant comparison](variant_comparison/README.md) | Allele-level SNV/indel intersection and summary table | Original Python comparison scripts migrated; input-selection requirements documented |
| [RTG benchmark](rtg_benchmark/README.md) | Haplotype-aware comparison and score-dependent curves | Historical scripts preserved; environment/image review required |
| [VAF](vaf/README.md) | Descriptive VAF strata and alternative-pipeline FILTER characterization | Original analysis scripts still to be incorporated |
| [Runtime](runtime/README.md) | Fixed CPU–GPU comparison, scaling and later Nextflow timing | Timing scope documented; full raw scaling material still to be incorporated |

The DRAGEN-derived call set is a comparator, not an independently validated truth set. Do not describe agreement metrics as clinical accuracy. The positive-TLOD input criterion and the later RTG threshold of 17.520 are distinct operations.
