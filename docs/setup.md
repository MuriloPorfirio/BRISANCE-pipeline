# Initial setup

From the repository root on the Linux x86_64 analysis server:

```bash
bash setup_brisance.sh
```

Setup requires Bash and Python 3.8+ with SSL support. It prepares Java/Nextflow and creates `analysis.local.ini`. Existing settings are preserved. No Conda activation or administrator privileges are required.

Docker Engine, NVIDIA drivers and NVIDIA Container Toolkit must be prepared separately under the server's administrator policy. FASTQs, indexed references, known-sites resources and VEP caches are supplied by the user. Scientific container images are checked later by the [analysis runner](usage.md).

## Existing installations

Setup searches its private runtime, `JAVA_CMD`, `JAVA_HOME` and `PATH` for Java 17–26. It checks for the verified standalone Nextflow 26.04.6 distribution in its private runtime, the repository root and `PATH`. Select other installed paths explicitly:

```bash
bash setup_brisance.sh \
  --java /absolute/path/to/java \
  --nextflow /absolute/path/to/nextflow-26.04.6-dist \
  --no-download
```

The generated INI records absolute executable paths for later commands. Setup does not replace other installations or alter system Java defaults, shell startup files or global PATH. An incompatible explicitly selected executable produces an error.

Use `--check` to inspect the plan without writes, downloads or prompts. This may run `java -version`; Nextflow is checked by SHA-256 without execution. Unrecognized/thin Nextflow launchers are not executed because they may bootstrap downloads.

## Downloads and local files

If a runtime is missing, setup shows the package URL/checksum and requests separate permission before downloading. Packages are fixed official HTTPS releases, verified by SHA-256:

| Package | Version | Source |
| --- | --- | --- |
| Nextflow standalone | 26.04.6 | [Nextflow release](https://github.com/nextflow-io/nextflow/releases/tag/v26.04.6) |
| Eclipse Temurin fallback JRE, Linux x64 HotSpot | 21.0.12.1+1 | [Adoptium release](https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.12.1%2B1) |

Versions, URLs and checksums are defined in [setup_brisance.py](../interface/setup_brisance.py). The fallback Java differs from the Conda 21.0.10 build used for the HG008 evaluation; setup records the actual selected runtime.

Runtime files, setup startup caches and `setup-*.json` records are kept in `.brisance/`, excluded from Git. Downloads/extraction use temporary staging within that folder. For another location, use `--runtime-dir /absolute/path/to/new-runtime`; its parent must exist. An unrecognized existing directory is refused rather than overwritten.

Use `--settings /absolute/path/analysis.local.ini` to select another personal settings file. Existing settings remain unchanged; repeated setup prints the selected runtime paths for manual updates if needed. No unattended downloads are permitted.

## After setup

Edit the INI with your inputs and resource settings, then follow [Usage](usage.md). Runtime readiness alone does not establish GPU/container compatibility or authorize shared-server resources; dependency checks occur before the final processing confirmation.

If preparation fails, inspect the error and setup record before retrying. Successfully prepared private packages may remain for reuse. Existing settings and system installations are not replaced, and no scientific processing is started by setup.

References: [Nextflow installation](https://docs.seqera.io/nextflow/install), [official Adoptium API examples](https://github.com/adoptium/api.adoptium.net/blob/main/docs/cookbook.adoc).
