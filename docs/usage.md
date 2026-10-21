# Running an analysis

Start with the [repository quick start](../README.md#getting-started). Run on the Linux server containing your data. After [initial setup](setup.md), edit `analysis.local.ini` in a text editor.

## Prepare the configuration

Set a new analysis folder, distinct tumor/normal sample names and the FASTQ paths. For multiple lanes, list each R1/R2 path on its own line, with corresponding mates in the same order. Enter the reference FASTA, each known-sites VCF and the VEP cache root. Indexes and resources must match the chosen reference build.

Choose automatic/custom adapters, quality and minimum read length, GPU indices, thread parameters and CPU/memory limits. The [settings reference](../interface/README.md) lists accepted inputs and options. Keep the executable paths selected by setup under `[runtime]`; no Conda activation is required.

Use absolute paths without spaces or shell characters. The analysis folder's parent must already exist. Coordinate shared-server resources before requesting processing.

## Check and run

Review the inputs, resources and storage estimate without writing outputs or processing reads:

```bash
bash interface/run_brisance.sh analysis.local.ini --check
```

Correct any reported errors in the INI. To request processing:

```bash
bash interface/run_brisance.sh analysis.local.ini --run
```

The runner asks for settings/storage approval, saves configuration and checks the host, GPUs, Docker, tool versions and file access. Each necessary image download requires permission. Nextflow validates the generated configuration, then `Start this analysis now? [y/N]:` requires a final confirmation before trimming begins.

Omit `--run` to prepare configuration and check dependencies only. Add `--no-download` to refuse image downloads. The interface requires an interactive terminal for approvals; long runs should use the server's approved persistent-session method. One task runs at a time, without scheduler submission or resource reservation.

## Results and further runs

The analysis folder contains [results, reports and work files](outputs.md). Inputs/shared caches remain read-only. Reports preserve confirmed settings, dependency observations and the executed pipeline snapshot.

Dependency-check failures can be corrected and retried with unchanged settings. Driver/Docker/permissions failures may require the server administrator. A scientific failure preserves diagnostics and intermediates; the fixed runner does not automatically resume, overwrite or clean previous runs. Use a new analysis folder for a fresh attempt or changed configuration.

Metadata/access checks do not establish FASTQ integrity, biological sample identity or reference/index consistency. Storage estimates are planning guidance, not guaranteed temporary peaks. Other users and quotas can affect capacity; disk usage is not continuously monitored.

## HG008 reproduction

The [preserved HG008 workflow](hg008-reproduction.md) has a separate samplesheet/parameter interface and Turing-specific launchers. Use it to inspect the evaluated execution procedure; use the settings-file entry point above for a new analysis.
