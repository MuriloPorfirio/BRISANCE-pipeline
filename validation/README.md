# Execution evidence

| Test | Evidence | Scope |
| --- | --- | --- |
| First-read prefixes | 10,000 synchronized pairs per sample; stages exercised with empty final VCF | Software behavior on a very small nonrepresentative input |
| Approximately 20% of all inputs | 18 completed tasks; final 16,917 VCF records, all CSQ-filled and positive TLOD | Integrated functional execution in the tested configuration |
| [All original reads](hg008_100pct/README.md) | 18 completed tasks; final 17,455 records; exact CHROM/POS/REF/ALT agreement with historical file | Full-input functional execution and record-identity comparison |

The validation records were prepared from the maintainer's terminal transcripts. Full original remote report files have **not** been downloaded during this migration. Do not describe transcribed tables as untouched raw reports or the reorganized repository as a fresh HG008 rerun.

No new clinical validation, DRAGEN accuracy calculation, genotype/annotation equality test, VCF byte comparison or independent-server test is claimed. The workflow's original source hashes are recorded in [Provenance](../provenance/README.md).

Unit/mock tests are separate from these biological-data executions. They do not require GPUs or the HG008 FASTQs and must not be counted as new sequencing validation.
