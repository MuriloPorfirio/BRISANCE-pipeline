# Allele-level variant comparison

These scripts compare the Parabricks-derived call set with the GIAB DRAGEN hard-filtered comparator. Files 01–04 and 06 originate from `HG008-BCFtools-Parabricks-vs-DRAGEN`. Their source versions are retained in [Provenance](../../provenance/README.md).

File 05 implements exact-allele indel comparison and insertion/deletion summaries. It replaces a misnamed table-building script in the original repository. The replacement is covered by synthetic tests; its counts have not been re-evaluated on the historical HG008 inputs.

## Inputs and counting unit

- Parabricks: the final PASS-filtered, positive-TLOD VCF.
- DRAGEN: `dragen_4.2.4_HG008-mosaic_tumor.hard-filtered.vcf.gz`, using PASS records.
- Exclude symbolic ALT entries according to the historical preparation script.
- Matching key: `CHROM,POS,REF,ALT`. The Python extraction splits multiallelic ALT entries into individual alleles and uses sets. Matching is representation-specific, without normalization or haplotype-aware comparison.
- SNV: REF and ALT length 1; indel: unequal lengths; equal lengths greater than 1 are classified as OTHER. OTHER entries are not included in the manuscript's SNV+indel total.

VCF records, extracted alleles, SNV+indel totals and RTG haplotype-aware counts use different units. The manuscript's 17,134 SNVs+indels exclude OTHER entries; the final Nextflow VCF contained 17,455 records before this allele-level classification.

## Execution

The shell scripts require `bcftools` and `plot-vcfstats` on PATH. Supply an already selected Parabricks PASS_TLOD file: script 01 applies PASS/symbolic-allele selection but does not apply the TLOD criterion. The study used BCFtools 1.24 for comparative statistics; the upstream Nextflow workflow uses BCFtools 1.21.

From this directory, using new output directories:

```bash
bash 01_prepare_pass_vcfs.sh /path/to/parabricks.PASS_TLOD.vcf.gz /path/to/dragen.vcf.gz /path/to/comparison/01_prepared
bash 02_run_bcftools_stats.sh /path/to/comparison/01_prepared/clara.pass.nonsymbolic.vcf.gz /path/to/comparison/01_prepared/dragen.pass.nonsymbolic.vcf.gz /path/to/comparison/02_stats
python3 03_extract_variant_sets.py /path/to/comparison/01_prepared/clara.pass.nonsymbolic.vcf.gz /path/to/comparison/01_prepared/dragen.pass.nonsymbolic.vcf.gz /path/to/comparison/03_sets
python3 04_compare_snvs.py /path/to/comparison/03_sets/clara/snvs.tsv /path/to/comparison/03_sets/dragen/snvs.tsv /path/to/comparison/04_snvs
python3 05_compare_indels.py /path/to/comparison/03_sets/clara/indels.tsv /path/to/comparison/03_sets/dragen/indels.tsv /path/to/comparison/05_indels
python3 06_build_summary_table.py /path/to/comparison/04_snvs/summary.txt /path/to/comparison/05_indels/summary.txt /path/to/comparison/06_table
```

Use a fresh output root because several scripts can overwrite individual files. Symbolic-allele exclusion is applied at record level and can remove an entire mixed multiallelic record.

The Python scripts use the standard library. Synthetic tests cover extraction, set comparison and table generation. VAF/FILTER characterization is described [separately](../vaf/README.md).
