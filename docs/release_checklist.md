# Release checklist

This repository is a public preparation draft, not a declared v1.0 release. Public visibility was explicitly authorized by the maintainer; it does not indicate that the release checklist is complete.

## Included in this preparation

- [x] New root README and section-specific documentation in English.
- [x] Separate historical procedures, analysis material and Nextflow implementation.
- [x] Preserve source snapshots and record source commits without changing the original repositories.
- [x] Preserve scientific Nextflow modules byte-for-byte and distinguish the later validation from historical study results.
- [x] Record the full HG008 outcome and the manual CPU-quota intervention honestly.
- [x] Exclude FASTQs/BAMs/VCFs, cache/reference payloads, credentials, backup/deletion utilities and manuscript drafts.
- [x] Apply the maintainer's non-commercial policy to new material and retain original license notices.
- [x] Obtain the maintainer's authorization for public visibility, with draft status and outstanding checks retained.

## Required before advertising complete manuscript reproducibility

- [ ] Import the original VAF-stratification and alternate-pipeline FILTER-analysis scripts and associate them with Supplementary Table S1. Do not substitute a new unvalidated implementation and call it historical.
- [ ] Recover the original actually executed indel comparison, or validate/document the explicitly reconstructed active script 05 against historical HG008 inputs. The old public file 05 was a misnamed table builder; its unchanged source is preserved.
- [ ] Import the actual GPU-scaling/DeepSomatic launch scripts, complete raw runtime values and figure-generation scripts. Keep these separate from the fixed CPU–GPU experiment.
- [ ] Recover full-run `trace.tsv`, versions/configuration files and relevant original logs from Turing. Tables in this draft are transcriptions of terminal output supplied by the maintainer, not copies fetched from Turing.
- [ ] Confirm the exact RTG binary/version/digest used by the historical `:dev` image, and preserve its command semantics.
- [ ] Review the historical CPU comparator against the actual successful commands and logs; do not infer all runtime parameters from generic scripts.
- [ ] Resolve the manuscript statement about BQSR application being included in fq2bam timing: the displayed historical sum is fq2bam + fq2bam + MutectCaller, whereas a separate ApplyBQSR was also documented.
- [ ] Check scientific-record vs allele-level counting units; 17,455 final VCF records and 17,134 reported SNVs+indels are not interchangeable values.
- [ ] Review new path-adapted historical command recipes. They are reconstructions, not original executable files or new HG008 validation.
- [ ] Confirm contributor/author metadata in CITATION.cff and the copyright/license scope.
- [ ] Review prepared examples and remove any remaining misleading claims before a stable release.
- [ ] If scientific code/resources are changed for portability or speed, document that delta and test it separately; do not attribute the old full-run result to the changed implementation.
- [ ] Create a tagged release after review and update manuscript links/citations to that version. Add a DOI only if one has actually been assigned.
