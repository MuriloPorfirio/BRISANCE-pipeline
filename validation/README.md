# Validation

| Dataset | Result | Scope |
| --- | --- | --- |
| First-read prefixes | 10,000 synchronized pairs per sample; stages exercised with empty final VCF | Software behavior on a very small nonrepresentative input |
| Approximately 20% of all inputs | 18 completed tasks; final 16,917 VCF records, all CSQ-filled and positive TLOD | Integrated functional execution in the tested configuration |
| [All original reads](hg008_100pct/README.md) | 18 completed tasks; final 17,455 records; exact CHROM/POS/REF/ALT agreement with historical file | Full-input functional execution and record-identity comparison |

The summaries and CSV tables were transcribed from recorded terminal outputs. The full remote report archive is identified in the execution record and is not bundled here. Source-file checksums are listed in [Provenance](../provenance/README.md).

The full-input comparison evaluates VCF record identity by CHROM/POS/REF/ALT. Genotype, annotation and byte-level equality were not assessed. Biological concordance with the DRAGEN comparator is a separate study analysis; clinical performance was outside the scope of these workflow tests.

Software tests use synthetic inputs and simulated dependencies, independently of the HG008 runs. See [Software tests](repository_checks_2026-10-20.md).
