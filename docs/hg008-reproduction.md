# Reproducing the preserved HG008 workflow

These commands use the study's preserved `workflow/` entry point, not the configurable user interface. For a new analysis with your own files/settings, start with [Usage](usage.md).

Run these commands from the repository root. Use Nextflow 26.04.6/Java 21 and prepare the dependencies described in [Requirements](requirements.md). Do not run scientific processing on a backup server.

## 1. Prepare inputs

Copy `assets/hg008_samplesheet.example.csv` to your own samplesheet and replace every `/path/to` with an absolute local path. Columns must be exactly:

```text
sample,role,pair_id,fastq_1,fastq_2
```

The root `hg008_samplesheet.csv` retains the original Turing paths for provenance and the unchanged launchers; it is not a ready-to-run samplesheet for another server. Always provide your prepared `--input` explicitly.

Use one row per paired input. Only one tumor and one normal sample are supported, with distinct sample names; multiple rows per sample are supported. Roles are `tumor` and `normal`. Pair IDs must be unique, and a FASTQ must not be reused. Files must be nonempty gzip-compressed FASTQs. Names/paths have restrictions checked by `main.nf`; use simple absolute paths without whitespace or shell metacharacters.

The reference must be the uncompressed GIAB masked GRCh38 `.fasta`, with `.fai`, `.amb`, `.ann`, `.bwt`, `.pac`, `.sa` and the corresponding basename `.dict`. Each of the three known-sites VCFs must have its `.tbi`. VEP cache metadata must exist at `homo_sapiens/113_GRCh38/info.txt` beneath the cache root. See [Data](data.md).

## 2. Validate metadata only

```bash
nextflow run workflow/main.nf \
  --mode validate \
  --input /absolute/path/to/samplesheet.csv \
  -ansi-log false
```

This checks metadata, not FASTQ contents, gzip integrity, read pairing, biological sample identity or GPU availability.

## 3. Validate reference/cache paths

Copy `conf/paths.example.config` to `paths.local.config` and edit its paths and GPU indices. Then:

```bash
nextflow run workflow/main.nf \
  -c paths.local.config \
  --mode validate-annotate \
  -ansi-log false
```

This still launches no scientific tasks. It checks reference/index paths, GPU argument syntax and VEP cache metadata; it does not test GPU availability/reserve GPUs, read cache payloads, or test container access. Those checks must be performed separately with the server administrator's authorization.

## 4. Explicit full execution

Choose new output/work paths, coordinate the selected devices, and ensure that all container images exist locally. Create the report directory before running:

```bash
mkdir -p reports/my_run
nextflow -log reports/my_run/nextflow.log run workflow/main.nf \
  -c paths.local.config \
  --mode finalize \
  --outdir results/my_run/stage1 \
  -work-dir work/my_run \
  -with-trace reports/my_run/trace.tsv \
  -with-report reports/my_run/report.html \
  -with-timeline reports/my_run/timeline.html \
  -ansi-log false
```

`finalize` starts from raw FASTQs and runs all stages. It is not a final-VCF-only entry point. `--outdir` is the **stage1 directory**; stage2–stage8 default to its siblings. Keep a unique parent per run to prevent published-path collisions. Modes such as `call`, `filter` and `annotate` also include upstream processing.

The configuration and command above reproduce the documented interface, not the Turing launcher's extra environment/occupancy guard. They do not reserve resources or enforce a filesystem occupancy ceiling. The direct command has not been tested on another server.

## Restart and safety

- Inspect errors before choosing `-resume <specific_successful_run_name>`; a validation-only session is not a scientific cache. Work/cache must still exist and match the inputs/code/settings.
- Changing modes/configuration can change task hashes; confirm `CACHED` in the new trace instead of assuming reuse.
- Do not modify inputs, reference/cache payloads or completed task directories during a run.
- Do not use `-stub-run` as a safe validator: these modules do not provide scientific stubs.
- Publication uses symlinks with overwrite disabled. There is no general overwrite/cleanup safeguard for every possible output collision in a direct command; choose fresh paths.

## Turing-specific scripts

`workflow/run_hg008_100pct.sh`, `hg008_full_run.py` and the 20% launcher retain the original environment-specific implementation. They expect their original Turing data layout, executable and Conda paths. They are preserved as execution evidence, not advertised as universal installation scripts. They do not run on the Mint workstation without the server inputs.
