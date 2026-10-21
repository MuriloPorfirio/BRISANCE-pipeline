# Validation

The [HG008 evaluation](hg008_100pct/README.md) used all original reads, without subsampling: four paired tumor inputs and one paired normal input, totaling ten compressed FASTQ files and 500,242,287,130 bytes. The run completed all 18 tasks with exit code 0 and produced 17,455 final VCF records.

The summaries and CSV tables were transcribed from recorded terminal outputs. The full remote report archive is identified in the execution record and is not bundled here. Source-file checksums are listed in [Provenance](../provenance/README.md).

The full-input comparison evaluates VCF record identity by CHROM/POS/REF/ALT. Genotype, annotation and byte-level equality were not assessed. Biological concordance with the DRAGEN comparator is a separate study analysis; clinical performance was outside the scope of this workflow evaluation. The execution record applies to the preserved `workflow/` implementation, not a separate full-input evaluation of the configurable interface.

Software tests use synthetic inputs and simulated dependencies, independently of the HG008 evaluation. See the [current package checks](repository_checks_2026-10-21_full_input.md), [earlier software checks](repository_checks_2026-10-21.md) and [test commands](../tests/README.md).
