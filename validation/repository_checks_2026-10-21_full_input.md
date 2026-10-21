# Software checks — 21 October 2026

Checks after focusing the published HG008 evaluation on the full-input execution:

- Repository and interface suite: 140 tests discovered; 138 passed and 2 optional Nextflow orchestration tests skipped.
- Full-input workflow-helper suite: 34 tests discovered; 32 passed and 2 optional Nextflow safety tests skipped.
- All 13 preserved scientific workflow/configuration/module checksums and all 31 original source-file identities matched their manifests.
- Documentation links, full-input metadata and timing arithmetic, active shell syntax and package checks passed.
- The full-input HG008 execution records and scientific modules were unchanged.

Commands:

```bash
python3 -B -m unittest discover -s tests -q
python3 -B -m unittest discover -s workflow/tests -q
git diff --check
```

These are software and packaging checks with synthetic inputs and simulated dependencies. No sequencing-data analysis, Docker/GPU job or new HG008 evaluation was started.
