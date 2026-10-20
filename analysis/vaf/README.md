# Descriptive VAF and discordance analysis

The manuscript describes tumor `FORMAT/AF` stratification of shared and pipeline-specific SNVs into:

- AF < 0.02;
- 0.02 ≤ AF < 0.05;
- 0.05 ≤ AF < 0.10;
- AF ≥ 0.10.

These are descriptive strata rather than additional variant-calling filters. AF is taken from each pipeline's tumor sample and may differ between pipelines for the same allele.

For pipeline-specific SNVs, the complete alternate-pipeline VCF was inspected to distinguish an absent exact allele from a detected but non-PASS allele, with FILTER tags summarized for the latter. Exact-allele identity is CHROM/POS/REF/ALT, not a region-only match or haplotype-aware RTG classification.

This section documents the method used for Supplementary Table S1. Dedicated analysis scripts and intermediate tables are not included in the repository.
