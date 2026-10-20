# Software tests — 20 October 2026

The following tests were run on Linux Mint with synthetic inputs and simulated dependencies:

- Repository suite: **20 tests passed**, covering 13 scientific Nextflow/configuration/module file checksums, 31 original source-file identities, metadata and timing arithmetic, documentation links, manual command syntax and options, payload/credential exclusions, and indel-comparison output handling.
- Workflow helper suite: **62 tests discovered; 60 passed and 2 optional Nextflow integration tests skipped** because `BRISANCE_TEST_NF` was not supplied. Hardware and scientific tools are simulated in this suite.
- Synthetic SNV, indel, multiallelic and OTHER records produced the expected comparison table and 40.00% intersection-over-union.
- Active shell scripts and generated manual commands passed Bash syntax checks. Archived source examples retain their original contents.

These tests evaluate software behavior and repository consistency, separately from the HG008 execution results. Current commands are listed in [Tests](../tests/README.md); analysis-specific limitations are listed in [Technical notes](../docs/technical_notes.md).
