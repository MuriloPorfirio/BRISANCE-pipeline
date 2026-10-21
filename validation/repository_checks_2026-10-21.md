# Software tests — 21 October 2026

- Repository suite: **142 tests passed**, including the two optional Nextflow orchestration tests.
- Preserved workflow-helper suite: **60 tests passed; 2 optional tests skipped** because `BRISANCE_TEST_NF` was not supplied.
- Source consistency: all 13 preserved scientific workflow/configuration/module checksums and all 31 original source-file identities matched their manifests.
- Documentation links, author order, project acknowledgement, package exclusions and active shell syntax checks passed.

The orchestration tests used real Nextflow 26.04.6 with synthetic inputs, fake scientific executables and a fake Docker CLI. They exercised 15- and 16-task graphs, including custom adapters and multiple tumor lanes. They did not start containers, use GPUs or measure biological performance.

The setup tests covered runtime selection, download consent, checksum/archive checks, cancellation and preservation of existing settings. A separate local rehearsal used checksum-verified official Java/Nextflow artifacts from a temporary cache.

Commands and test scope are described in [Tests](../tests/README.md). These software tests are separate from the HG008 scientific execution records.
