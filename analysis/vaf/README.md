# Descriptive VAF and discordance analysis

The manuscript describes tumor `FORMAT/AF` stratification of shared and pipeline-specific SNVs into:

- AF < 0.02;
- 0.02 ≤ AF < 0.05;
- 0.05 ≤ AF < 0.10;
- AF ≥ 0.10.

These are descriptive strata, **not extra variant-calling filters**. AF values come from the corresponding pipeline's tumor sample; do not assume that AF is identical for a shared allele in both pipelines.

For pipeline-specific SNVs, the complete alternate-pipeline VCF was inspected to distinguish an absent exact allele from a detected but non-PASS allele, with FILTER tags summarized for the latter. Exact-allele identity is CHROM/POS/REF/ALT, not a region-only match or haplotype-aware RTG classification.

**Status:** the dedicated scripts and original intermediate tables were not present in the four migrated repositories. They have not been reconstructed or claimed as reproduced here. Import the actual historical scripts, versions, sample selections and Supplementary Table S1 provenance before marking this section executable/reproducible. No synthetic replacement results are provided.
