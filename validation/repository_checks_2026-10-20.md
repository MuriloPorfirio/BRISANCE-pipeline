# Repository preparation checks — 20 October 2026

The following checks were run on the Linux Mint workstation against the reorganized local repository, **not** on Turing and not with HG008 payloads:

- Repository suite: **20 tests passed**. Checks include preservation of 13 scientific Nextflow/config/module files, preservation of 31 source-snapshot files and their original Git blob identities, metadata/counting arithmetic, documentation links, reconstructed historical recipe syntax/options, payload/credential exclusions and the reconstructed indel comparison's no-overwrite behavior.
- Preserved workflow helper suite: **62 tests discovered; 60 passed and 2 optional Nextflow integration tests skipped** because no `BRISANCE_TEST_NF` was supplied for this run. Hardware, scientific tools and sequencing inputs are simulated by these helper tests.
- The active indel comparison and downstream table were exercised on tiny synthetic SNV/indel/multiallelic/OTHER records. Expected totals and 40.00% synthetic intersection-over-union were obtained. This is not a reproduction of the HG008 manuscript table.
- Preserved and reconstructed active Bash commands passed syntax checks. Archived generic examples are deliberately kept unchanged, rather than silently repaired and represented as historical originals.

No real Docker/Parabricks/VEP/RTG job, full-input rerun, live server cleanup, FASTQ transfer, or manuscript edit was performed during these checks. The original remote full-run report archive is still to be incorporated. Passing these checks is not a substitute for the open items in the release checklist.
