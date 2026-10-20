# Historical HG008 Parabricks procedure

This section documents the manual HG008 procedure used before the Nextflow implementation, based on the study notebook, BAM/VCF headers and execution logs. Original examples from the earlier repository are retained in [Source snapshots](../../provenance/README.md).

## Procedure

1. Trim five paired inputs with Trim Galore 0.4.4/Cutadapt 1.13 and FastQC 0.11.5: paired mode, quality 20, minimum length 20, adapter autodetection.
2. fq2bam on the four tumor pairs together. The successful tumor output is attempt 2, with `--tmp-dir`, `--gpusort --gpuwrite` and one exposed GPU (historically 7). The command used the default BWA thread-pool, GPU-count and memory settings.
3. fq2bam on the single normal pair, historically GPU 6, same reference/known-sites resources, `--gpusort --gpuwrite`. No explicit temporary-directory flag was in that recovered normal command.
4. Separate ApplyBQSR on each corresponding BAM/table, `--num-gpus 1 --num-threads 16 --tmp-dir`. Historically normal used GPU 7 and tumor GPU 6.
5. samtools 1.19 `reheader -c`, changing SM to `somatico` or `germinativo`, followed by `index -@ 8`. Other read-group fields are retained. The earlier addreplacerg/fixed-BAM attempt was not used for the final analysis.
6. Parabricks 4.5.1-1 MutectCaller on the already recalibrated/reheadered BAMs, `--num-htvc-threads 32`, one exposed GPU (historically 7), names `somatico`/`germinativo`, the reference and a temporary directory. The recovered successful script does **not** pass the recalibration tables again into the caller.
7. Raw VCF compression/indexing; GATK FilterMutectCalls with original `.vcf.stats`, reference and `--create-output-variant-index true`; selection of PASS records.
8. VEP offline/cache 113 GRCh38, `--everything --fork 8 --vcf --compress_output bgzip`, read-only cache; output indexing.
9. Select `INFO/TLOD>0 && INFO/TLOD!="."` from the annotated PASS VCF and index the result.

No AF cutoff, new panel of normals, germline resource, confident-region BED, optimized RTG threshold or extra caller flag is added to this sequence.

## Versions: recorded tags versus actual software

The historical notebook specifies Parabricks `4.5.1-1`, samtools `1.19` and a pinned htslib compression image. Some downstream commands used `:latest`; their output headers/logs identify GATK 4.6.2.0, BCFtools 1.21 and VEP 113.0/cache 113.

The command recipe uses version tags corresponding to the recorded tools. Historical image digests are unavailable, and the present VEP image differs from the historical header in some internal API commit identifiers.

## Manual commands

`hg008_commands.py` generates shell commands from the documented procedure, using HG008 filenames and configurable local paths. It prints commands without running Docker or processing data. This path-adapted version is maintained separately from the original 2025 scripts.

For example:

```bash
python3 historical_workflows/parabricks/hg008_commands.py \
  --base /absolute/path/to/hg008_manual \
  --cache /absolute/path/to/vep_data \
  --stage call
```

Use `--stage all` to display every stage. Place the inputs under `raw/HG008_somatic`, `raw/HG008_germline`, `reference` and `known-sites` beneath the supplied base directory. GPU indices are configurable. Coordinate GPU availability and storage before executing the printed commands. Primary-output checks prevent overwriting existing files; the generator itself does not manage execution or reserve resources. Evaluation of the generated recipes is limited to command and syntax tests.

Separate ApplyBQSR runs are part of this procedure; their timing scope is described in [Runtime](../../analysis/runtime/README.md). The older repository's optional dbSNP GPU-annotation example is outside this HG008 execution sequence.
