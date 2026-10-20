# Data and references

The study used the HG008 matched tumor–normal dataset from Cancer Genome in a Bottle. No sequencing or reference payloads are bundled. Follow the [GIAB somatic data repository](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/data_somatic/HG008/) and its [BCM Illumina WGS README](https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/data_somatic/HG008/Liss_lab/BCM_Illumina-WGS_20240313/README_BCM_ILMN.md) for data provenance and checksums.

The original inputs for the Nextflow full run are listed in [input_files.csv](../validation/hg008_100pct/input_files.csv); their compressed sizes total **500,242,287,130 bytes**. They comprise four tumor pairs (IDUDI0031) and one normal pair (IDUDI0034). Prefixes/output names alone do not establish sample identity. The original samplesheet is preserved for provenance, while [the example](../assets/hg008_samplesheet.example.csv) uses placeholder local paths.

Reference basename:

```text
GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta
```

Known-sites resources:

- `Mills_and_1000G_gold_standard.indels.hg38.vcf.gz`
- `Homo_sapiens_assembly38.known_indels.vcf.gz`
- `1000G_phase1.snps.high_confidence.hg38.vcf.gz`

Their identity between the existing Turing copies and historical Apollo backup was checked with matching SHA256 values during preparation. [reference_checksums.tsv](../validation/reference_checksums.tsv) records the supplied values; it is not a new verification of all current remote files or index consistency.

The VEP cache is `homo_sapiens/113_GRCh38`, species `homo_sapiens`, assembly GRCh38/GRCh38.p14. Metadata recorded Ensembl 113, GENCODE 47, dbSNP 156, ClinVar 202404, COSMIC 99 and gnomAD exome/genome v4.1. Matching an `info.txt` is not a hash of the cache payload. Keep shared cache content unchanged/read-only during an experiment.

The study comparator is `dragen_4.2.4_HG008-mosaic_tumor.hard-filtered.vcf.gz`. It is a comparator call set, **not** an independently validated somatic truth set. Benchmark metrics are agreement with that comparator. No confident-region BED is invented here.
