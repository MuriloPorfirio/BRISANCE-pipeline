# Analysis settings

Define your inputs and resource limits in one editable INI file. [Initial setup](../docs/setup.md) creates `analysis.local.ini` with Java/Nextflow paths; [brisance.example.ini](brisance.example.ini) is the reference template. Personal `*.local.ini` files are excluded from Git.

## Inputs and settings

- `[analysis] folder`: a new analysis directory with an existing, writable parent.
- `[tumor]` and `[normal]`: distinct sample names and gzip-compressed paired-end FASTQs. Use one path per line, with corresponding R1/R2 mates in the same list order. Multiple lanes are supported; pair counts and identifiers are generated automatically.
- `[reference] fasta`: an uncompressed `.fa`, `.fasta` or `.fna`, with `.fai`, BWA `.amb/.ann/.bwt/.pac/.sa` indexes and a sequence dictionary (`name.dict` or `name.fasta.dict`).
- `[reference] known_sites`: list each `.vcf.gz` explicitly, with its corresponding `.tbi`. The list is not fixed to three files or to the HG008 filenames.
- `[reference] vep_cache`: the human VEP 113 cache root, with metadata matching the selected assembly. GRCh38 was evaluated. GRCh37 is accepted but has not received that evaluation; hg19-family resources are not automatically interchangeable.
- `[trimming]`: `auto` adapter detection or `custom` with both R1/R2 DNA sequences, plus quality and minimum retained read-length thresholds.
- Resource sections: selected GPU indices, tool thread parameters and Docker CPU/memory limits. ApplyBQSR selects one GPU; alignment and calling GPU selections are configurable. CPU quota is distinct from a tool's thread parameter.

For multiple lanes:

```ini
[tumor]
sample = TUMOR_01
r1 =
    /data/tumor_lane1_R1.fastq.gz
    /data/tumor_lane2_R1.fastq.gz
r2 =
    /data/tumor_lane1_R2.fastq.gz
    /data/tumor_lane2_R2.fastq.gz
```

Use absolute paths without spaces or shell characters. Files must not be reused across pairs; sample names use letters, numbers, dots, underscores or hyphens. The parser rejects unknown/duplicate fields, unequal mate lists, conflicting filenames and invalid values. It checks file metadata, index presence and cache metadata, not FASTQ contents, biological identity, index integrity or reference/known-sites coordinate compatibility.

## Run options

From the repository root:

```bash
bash interface/run_brisance.sh analysis.local.ini --check
bash interface/run_brisance.sh analysis.local.ini --run
```

| Option | Behavior |
| --- | --- |
| `--check` | Display settings/storage and validate metadata; no writes or external commands |
| No option | Confirm settings, save configuration and check dependencies |
| `--prepare-only` | Confirm and save settings without dependency checks |
| `--run` | Check dependencies and request a fresh scientific run, with a final start confirmation |
| `--no-download` | Refuse missing or incorrect container images instead of offering downloads |

`[runtime] java` and `nextflow` select installed executables; no Conda activation is needed when these paths are set. `[runtime] check_environment = true` is required for `--run`. With `allow_downloads = true`, each necessary image download requires separate approval. Confirmations default to no.

## Environment checks

After settings/storage approval, the runner checks:

- Linux x86_64, visible CPUs and available RAM against the chosen limits, leaving at least one logical CPU beyond the largest task quota for Nextflow.
- Java 17–26, Nextflow 26.04.6 and access to a local Linux Docker daemon, version 20.10 or later.
- Selected NVIDIA GPU identities, apparent availability, absence of compute jobs and disabled/unsupported MIG mode. Non-A100-80-GB models are identified as outside the HG008 evaluation.
- The six required container images and tool versions listed in [Requirements](../docs/requirements.md), selected GPU visibility inside Parabricks, read-only input/resource access and report-directory writing.

Missing or incorrect image versions can be downloaded only with approval, then are checked again. Diagnostics use the inspected image IDs, disabled networking and limited CPU/memory. Failure cleanup targets only labelled diagnostic containers belonging to that check; it does not stop other users' jobs. Docker downloads consume daemon storage, possibly on a different filesystem from the analysis.

Successful checks establish dependency/access availability at that time, not a resource reservation or certification of every GPU architecture/input combination. Drivers, Docker installation and permissions remain administrator-managed. The standalone checker, `check_environment.py`, can inspect an existing `brisance.json` without starting analysis.

## Analysis files

```text
analysis_01/
  brisance.json
  samplesheet.csv
  results/
  reports/
    settings-*/
    environment-*/
    execution-*/
  work/
```

Confirmed settings are archived with their summary and storage estimate. Environment reports record tool/image versions and checks. Execution reports contain the pipeline snapshot, generated parameters, logs, trace, HTML report, timeline and start/completion records.

The runner generates the samplesheet and translates settings for `pipeline/main.nf`; do not pass `brisance.json` to the preserved `workflow/main.nf` entry point. Scientific tasks use the checked local image IDs, with pulling/networking disabled. One task runs at a time.

Published results are regular hard-linked files, not symbolic links into work. They share storage with work files: removing one work filename leaves the result accessible, while editing either name changes the same content. See [Outputs](../docs/outputs.md) for publication and archive handling.

Existing identical settings can be checked again. Changed configurations require a new analysis folder. Scientific runs require empty work/results folders; the runner never implicitly resumes, overwrites or cleans a previous run. Preserve failed-run reports before choosing a fresh attempt.

## Storage estimate

Estimated additional storage is `5 × compressed input bytes`; recommended free space is `max(8 × input bytes, 32 GiB)`. The factors derive from approximately 2.3 TiB of retained work for 500,242,287,130 input bytes in the HG008 full run. The 32-GiB floor is a planning policy for small inputs, not a measured minimum.

The estimate assumes retained intermediates, no extra original FASTQ copy and no duplicate BAM publication copy. Existing references, caches and images are excluded. Compression, configuration and temporary peaks can change requirements. Quotas and other users are not accounted for or reserved. `--run` refuses launch below the recommendation; disk usage is not continuously monitored after launch.
