# Study analyses

This directory contains the analyses associated with the HG008 study. They are separate from FASTQ-to-VCF processing and are not executed by Nextflow's `--mode finalize`.

| Section | Purpose | Contents |
| --- | --- | --- |
| [Variant comparison](variant_comparison/README.md) | Allele-level SNV/indel intersection and summary table | Scripts, input requirements and counting rules |
| [RTG benchmark](rtg_benchmark/README.md) | Haplotype-aware comparison and score-dependent curves | Historical scripts and execution settings |
| [VAF](vaf/README.md) | Descriptive VAF strata and alternative-pipeline FILTER characterization | Methods; dedicated scripts are not included |
| [Runtime](runtime/README.md) | Fixed CPU–GPU comparison, scaling and Nextflow timing | Timing definitions and full-run measurements; complete scaling inputs are not included |

Benchmark metrics describe agreement with the DRAGEN-derived comparator. The positive-TLOD input selection is distinct from the RTG score threshold of 17.520.
