# Nextflow implementation

This directory contains the tested scientific implementation and its development test helpers. `main.nf`, `nextflow.config` and `modules/*.nf` are copied without scientific edits from the implementation used on Turing. Their source hashes are recorded in [the provenance manifest](../provenance/workflow_manifest.json).

The small prefix tests, integrated 20% test and integrated full-read HG008 run are different experiments. Completion and limits are summarized in [Validation](../validation/README.md). The full run completed on 20 October 2026; older development prose describing it as pending is not reused as current documentation.

For the supported user interface, see [Usage](../docs/usage.md), [Requirements](../docs/requirements.md) and [Outputs](../docs/outputs.md).

## Files

- `main.nf`: input validation and channel/dependency wiring; defaults to metadata-only validation.
- `nextflow.config`: original container/resource settings and Turing-specific default paths. Override paths explicitly; do not assume they exist on another server.
- `modules/*.nf`: scientific steps, version/configuration capture and symlink publication.
- `prepare_trim_test.py`: a first-read prefix test only; not representative sampling.
- `prepare_fraction_test.py`: deterministic paired seqtk subsetting, explicit `--execute`; not part of a full-read run.
- `run_hg008_20pct.sh`, `run_hg008_100pct.sh`, `hg008_full_run.py`: original **Turing-specific launchers**, not general installation scripts.
- `tests/`: synthetic/helper tests. Two safety tests are opt-in with `BRISANCE_TEST_NF`; they use real Nextflow but mock hardware and trivial tasks, not real Parabricks or HG008.

Do not use `-stub-run` as a safe validation mode. Do not delete work directories behind published symlinks. CPU/GPU quotas are not reservations against other users.
