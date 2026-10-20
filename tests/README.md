# Tests

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s workflow/tests -v
```

The repository tests verify preserved source/workflow hashes, metadata counts/timing arithmetic, current documentation links, payload exclusions, reconstructed command syntax/options and a tiny synthetic allele-comparison example. They do not run Docker, real Parabricks, VEP or HG008.

The workflow helper tests are preserved from development. Two optional safety tests require `BRISANCE_TEST_NF` pointing to Nextflow 26.04.6; they run trivial task scripts with Docker disabled and simulated disk/GPU state. Without that variable they are skipped. Even when enabled, they are not additional WGS validation.

Original scripts under `provenance/source_snapshots` are retained unchanged, including known generic examples/limitations. They are not all expected to pass executable portability checks. See their section-specific documentation rather than running an archived `.sh` blindly.
