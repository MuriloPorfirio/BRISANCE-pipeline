# Nextflow implementation

This directory contains the Nextflow implementation, scientific modules and execution helpers. The full-input HG008 run used these versions of `main.nf`, `nextflow.config` and `modules/*.nf`; their checksums are recorded in [the source manifest](../provenance/workflow_manifest.json).

Evaluation included small prefix tests, a 20% subsample and all original HG008 reads. The full run completed on 20 October 2026. Results and comparison methods are described in [Validation](../validation/README.md).

For the supported user interface, see [Usage](../docs/usage.md), [Requirements](../docs/requirements.md) and [Outputs](../docs/outputs.md).

## Files

- `main.nf`: input validation and channel/dependency wiring; defaults to metadata-only validation.
- `nextflow.config`: original container/resource settings and Turing-specific default paths. Override paths explicitly; do not assume they exist on another server.
- `modules/*.nf`: scientific steps, version/configuration capture and symlink publication.
- `prepare_trim_test.py`: a first-read prefix test only; not representative sampling.
- `prepare_fraction_test.py`: deterministic paired seqtk subsetting, explicit `--execute`; not part of a full-read run.
- `run_hg008_20pct.sh`, `run_hg008_100pct.sh`, `hg008_full_run.py`: original **Turing-specific launchers**, not general installation scripts.
- `tests/`: synthetic helper tests and two optional Nextflow integration tests enabled with `BRISANCE_TEST_NF`. The integration tests use simulated hardware state and simple task scripts.

Do not use `-stub-run` as a safe validation mode. Do not delete work directories behind published symlinks. CPU/GPU quotas are not reservations against other users.
