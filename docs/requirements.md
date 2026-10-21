# Requirements

## Before initial setup

The configurable entry point supports Linux x86_64, Bash and Python 3.8+ with standard SSL support. Git is needed to clone the repository. [Initial setup](setup.md) can reuse compatible Java or prepare a private Java/Nextflow runtime, without Conda activation or changes to system installations.

Before requesting analysis, the server administrator must have prepared compatible NVIDIA drivers, Docker Engine (20.10+), NVIDIA Container Toolkit and authorized access to the local Docker daemon. Initial setup does not install or certify these. FASTQs, indexed reference, known-sites resources and the human VEP 113 cache must already exist. [Usage](usage.md) is the primary entry point for new analyses.

## Tested environment, not minimum requirements

The HG008 tests used a Linux DGX A100 server with 256 logical CPUs, approximately 2 TiB host RAM, eight NVIDIA A100-SXM4-80GB GPUs, NVIDIA driver 535.216.03 and Docker Engine 27.1.2. Only the explicitly selected GPUs were exposed to each task. Other hardware configurations have not been validated by these tests.

The tested Nextflow version was **26.04.6**, using **OpenJDK 21.0.10** from the existing Conda environment. The preserved HG008 workflow manifest accepts later Nextflow versions, but that is not evidence that they were tested. The configurable entry point requires 26.04.6; initial setup pins its verified standalone distribution and accepts Java 17–26. Its optional Temurin Java 21 fallback is documented separately in [Setup](setup.md). The Java 11 system installation was not used for successful launches.

## Container images

| Purpose | Image used by the Nextflow implementation |
| --- | --- |
| Trim Galore / Cutadapt / FastQC | `biowardrobe2/trimgalore:v0.4.4` — tools 0.4.4 / 1.13 / 0.11.5 |
| fq2bam, ApplyBQSR, MutectCaller | `nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1` |
| BAM/header/index utilities | `staphb/samtools:1.19` |
| FilterMutectCalls | `broadinstitute/gatk:4.6.2.0` |
| VCF selection, compression and indexing | `staphb/bcftools:1.21` |
| Annotation | `ensemblorg/ensembl-vep:release_113.0`, cache 113 GRCh38 |

Scientific tasks use `--pull never`. The settings-file runner checks required images before analysis and offers a separate approval for each necessary download; `--no-download` refuses them. The preserved direct HG008 workflow instead expects the images to have been obtained beforehand. Version tags are not immutable image digests. The configurable runner records and binds the exact checked local image IDs. Current pulls cannot establish a historical digest.

The subsampling helper additionally uses a pinned seqtk 1.4 image. It is not needed for a run on all original reads.

## Permissions and server preparation

- Permission to use the selected GPUs and CPU/RAM/disk on the shared server.
- Access to the Docker daemon and installed NVIDIA Container Toolkit with working GPU passthrough. This is a privileged capability; follow local administrator policy rather than changing Docker/socket permissions through this repository.
- Read access to FASTQs, the reference and its indexes, known-sites resources, and the shared VEP cache.
- Write access to the chosen work, results and report directories.
- Host `bash`, Java/Nextflow and, for helpers, Python 3.8 or later. The Turing launchers additionally assume Conda, GNU screen and the specific server layout.

Normal scientific runs use the invoking numeric UID/GID. The cache is mounted read-only. No tool installer, privilege escalation or system-wide configuration change is performed by the workflow.

## Evaluated HG008 resource configuration

| Task | GPUs | Tool parameter | CPU quota | Container memory |
| --- | --- | --- | --- | --- |
| Trim Galore + FastQC | none | paired; quality 20; length 20 | 2 | 100 GB |
| fq2bam, each sample | 3 | BWA pool 16 per GPU | 64 | 256 GB |
| ApplyBQSR, each sample | 1 | worker threads 16 | 24 | 128 GB |
| SM/header adjustment | none | index `-@ 8` | 10 | 8 GB |
| MutectCaller | 2 | `--num-htvc-threads 24` | 64 | 256 GB |
| FilterMutectCalls | none | defaults shown in module | 4 | 16 GB |
| VEP | none | `--fork 8` | 10 | 32 GB |

The fq2bam sorting/postsorting limit is 128 GB, distinct from its 256 GB container ceiling. FastQC's Java heap ceiling is 8 GiB. Limits are settings, not measured minimums or constant consumption. CPU counts mean logical-CPU quota, not physical sockets or the exact number of application threads. The preserved HG008 workflow fixes GPU counts at 3/1/2. The configurable entry point exposes alignment/calling GPU selections and CPU/memory/thread settings; ApplyBQSR selects one GPU. Other choices have not received the HG008 full-input evaluation. Tasks run sequentially; both alignments finish before ApplyBQSR begins. The caller waits for both adjusted BAMs. No reservation against other users is provided.

During the full run, the normal trimming container's quota changed from 2 to 8 CPUs. The table above gives the workflow configuration; the runtime change is recorded in [Full-run validation](../validation/hg008_100pct/README.md).

## Disk space

The original compressed FASTQs total 500,242,287,130 bytes. Intermediates require substantially more space. No portable minimum or guaranteed peak has been established. The settings-file runner estimates additional storage from this input size and observed HG008 work, with a planning margin; it is not a guarantee or reservation. See [Storage estimate](../interface/README.md#storage-estimate).

New configurable results are regular hard-linked files in the analysis folder, not symbolic links into `work`. No second full BAM copy is created. The preserved HG008 workflow still uses symbolic links: deleting its work invalidates published results. Both implementations lose resumability/task diagnostics if their work directories are removed. Do not infer disk usage from `rchar/wchar` counters. See [Outputs](outputs.md).

The Turing full-run launcher has a best-effort 64% preventive stop for the user-requested 65% filesystem ceiling. These thresholds are server operating policy, not BRISANCE biological settings, a storage reservation, or a guarantee.
