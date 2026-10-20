# Requirements

## Tested environment, not minimum requirements

The HG008 tests used a Linux DGX A100 server with 256 logical CPUs, approximately 2 TiB host RAM, eight NVIDIA A100-SXM4-80GB GPUs, NVIDIA driver 535.216.03 and Docker Engine 27.1.2. Only the explicitly selected GPUs were exposed to each task. Other hardware configurations have not been validated by these tests.

The tested Nextflow version was **26.04.6**, using **OpenJDK 21.0.10** from the existing Conda environment. The workflow manifest accepts later Nextflow versions, but that is not evidence that they were tested. The Java 11 system installation was not used for successful launches.

## Container images

| Purpose | Image used by the Nextflow implementation |
| --- | --- |
| Trim Galore / Cutadapt / FastQC | `biowardrobe2/trimgalore:v0.4.4` — tools 0.4.4 / 1.13 / 0.11.5 |
| fq2bam, ApplyBQSR, MutectCaller | `nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1` |
| BAM/header/index utilities | `staphb/samtools:1.19` |
| FilterMutectCalls | `broadinstitute/gatk:4.6.2.0` |
| VCF selection, compression and indexing | `staphb/bcftools:1.21` |
| Annotation | `ensemblorg/ensembl-vep:release_113.0`, cache 113 GRCh38 |

Images must be present locally: Docker is configured with `--pull never`. An administrator or authorized user must obtain them before the run. Version tags are not immutable image digests. Preserve the actual local image digests for the released validation record; current pulls cannot establish a historical digest.

The subsampling helper additionally uses a pinned seqtk 1.4 image. It is not needed for a run on all original reads.

## Permissions and server preparation

- Permission to use the selected GPUs and CPU/RAM/disk on the shared server.
- Access to the Docker daemon and installed NVIDIA Container Toolkit with working GPU passthrough. This is a privileged capability; follow local administrator policy rather than changing Docker/socket permissions through this repository.
- Read access to FASTQs, the reference and its indexes, known-sites resources, and the shared VEP cache.
- Write access to the chosen work, results and report directories.
- Host `bash`, Java/Nextflow and, for helpers, Python 3.8 or later. The Turing launchers additionally assume Conda, GNU screen and the specific server layout.

Normal scientific runs use the invoking numeric UID/GID. The cache is mounted read-only. No tool installer, privilege escalation or system-wide configuration change is performed by the workflow.

## Configured resource limits

| Task | GPUs | Tool parameter | CPU quota | Container memory |
| --- | --- | --- | --- | --- |
| Trim Galore + FastQC | none | paired; quality 20; length 20 | 2 | 100 GB |
| fq2bam, each sample | 3 | BWA pool 16 per GPU | 64 | 256 GB |
| ApplyBQSR, each sample | 1 | worker threads 16 | 24 | 128 GB |
| SM/header adjustment | none | index `-@ 8` | 10 | 8 GB |
| MutectCaller | 2 | `--num-htvc-threads 24` | 64 | 256 GB |
| FilterMutectCalls | none | defaults shown in module | 4 | 16 GB |
| VEP | none | `--fork 8` | 10 | 32 GB |

The fq2bam sorting/postsorting limit is 128 GB, distinct from its 256 GB container ceiling. FastQC's Java heap ceiling is 8 GiB. Limits are settings, not measured minimums or constant consumption. CPU counts mean logical-CPU quota, not physical sockets or the exact number of application threads. GPU identities are configurable, but counts are currently fixed to 3/1/2. fq2bam tasks run sequentially; both finish before ApplyBQSR begins. The caller waits for both adjusted BAMs. No reservation against other users is provided.

During the full run, the normal trimming container's quota changed from 2 to 8 CPUs. The table above gives the workflow configuration; the runtime change is recorded in [Full-run validation](../validation/hg008_100pct/README.md).

## Disk space

The original compressed FASTQs total 500,242,287,130 bytes. Intermediates require substantially more space. No portable minimum or guaranteed peak has been established. Results are symlinks into `work`; deleting work invalidates those results and resume. Do not infer disk usage from `rchar/wchar` counters.

The Turing full-run launcher has a best-effort 64% preventive stop for the user-requested 65% filesystem ceiling. These thresholds are server operating policy, not BRISANCE biological settings, a storage reservation, or a guarantee.
