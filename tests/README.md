# Tests

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s workflow/tests -v
```

The repository tests verify preserved source/workflow hashes, metadata counts/timing arithmetic, current documentation links, payload exclusions, reconstructed command syntax/options and a tiny synthetic allele-comparison example. They do not run Docker, real Parabricks, VEP or HG008.

Initial-setup tests cover read-only planning, existing executable selection, wrong versions/digests, per-package download approval, cancellation before writes, refusal of unrecognized folders/symlinks, preservation of existing settings, isolated startup environment and failed-probe records. Synthetic archive/download tests check HTTPS, byte/digest limits, archive traversal/device/hardlink rejection and safe internal license links. These tests mock downloads/runtime probes; they do not install system software or start analysis.

A local setup rehearsal on 2026-10-21 also used the checksum-verified official Java/Nextflow artifacts from a temporary download cache. It exercised real JRE extraction, Java and Nextflow version probes, a second preparation without downloads, preservation of the generated settings and read-only planning. All runtime/settings files were confined to a temporary folder. This was not a Docker/GPU or sequencing-data test; the installer download transport itself was mocked to reuse those cached artifacts.

Configuration-assistant tests cover multiple input lanes, duplicate files/hardlinks and names, explicit known-sites lists and indices, cache metadata, adapter/resource settings, storage arithmetic and warnings, confirmation/cancellation, exclusive output-folder creation and read-only configuration checks. These tests use tiny synthetic placeholders, not scientifically valid FASTQs or reference/index payloads. They do not demonstrate correct execution with other reference builds, GPU counts or user-defined parameters.

Environment-check tests simulate Java, Nextflow, Docker and NVIDIA responses. They cover per-image download consent/refusal, wrong-version refresh/recheck, daemon/permission failures, local-versus-remote Docker contexts, occupied/missing/MIG GPUs, GPU UUID mismatches, read-only input mounts, owned diagnostic-container cleanup, low space, and report preservation. No real dependency download, Docker container, GPU operation or remote scientific run is performed by these tests.

Fixed-file interface tests cover parsing the editable INI without code evaluation, automatic pair counts/IDs, unequal lists, unknown/duplicate fields, custom parameters, read-only summary checks, storage confirmation/cancellation, settings-source changes during confirmation, safe retries, executable/download policy forwarding and source-settings archival. The optional local Turing settings are compared with all ten recorded HG008 input filenames without accessing those remote files.

Configurable-execution tests cover parameter lowering, immutable image IDs, refusal to overwrite existing work/results, publication probes, mandatory environment checks, incomplete-trace failure and visible exit/log propagation. Optional real Nextflow tests run 15- and 16-task graphs with **fake scientific executables, a fake Docker CLI and synthetic placeholders**. The fake CLI records the generated Docker command and executes the fake task shell locally; it never contacts a daemon or starts containers. Tests verify image IDs by task, absence of undefined-parameter warnings, custom/automatic adapters, multiple tumor lanes, changed quality/thread settings reaching commands and regular published results surviving removal of a work filename. These are not biological/container/GPU tests. To enable them with an already installed Nextflow 26.04.6:

```bash
BRISANCE_NEXTFLOW_TEST=/absolute/path/nextflow-26.04.6-dist python3 -B -m unittest discover -s tests -q
```

The helper `fake_scientific_tool.py` is a test double only. Never install it on an analysis execution PATH.

The workflow helper tests are preserved from development. Two optional safety tests require `BRISANCE_TEST_NF` pointing to Nextflow 26.04.6; they run trivial task scripts with Docker disabled and simulated disk/GPU state. Without that variable they are skipped. Even when enabled, they are not additional WGS validation.

Original scripts under `provenance/source_snapshots` are retained unchanged, including known generic examples/limitations. They are not all expected to pass executable portability checks. See their section-specific documentation rather than running an archived `.sh` blindly.
