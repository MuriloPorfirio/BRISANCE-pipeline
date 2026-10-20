# Historical HG008 Parabricks procedure

This section describes the **manual execution behind the study**, before the later Nextflow implementation. It is recovered from the maintainer's HG008 notebook, BAM/VCF headers and log excerpts. The older public repository also contained generic examples; those remain unchanged in [source snapshots](../../provenance/README.md), rather than being mislabeled as the HG008 commands.

## Recovered sequence

1. Trim five paired inputs with Trim Galore 0.4.4/Cutadapt 1.13 and FastQC 0.11.5: paired mode, quality 20, minimum length 20, adapter autodetection.
2. fq2bam on the four tumor pairs together. The successful tumor output is **attempt 2**, with `--tmp-dir`, `--gpusort --gpuwrite`, one exposed GPU (historically 7). No explicit BWA thread-pool/num-GPU/memory flags were present in that recovered command; do not silently add the later Nextflow settings.
3. fq2bam on the single normal pair, historically GPU 6, same reference/known-sites resources, `--gpusort --gpuwrite`. No explicit temporary-directory flag was in that recovered normal command.
4. Separate ApplyBQSR on each corresponding BAM/table, `--num-gpus 1 --num-threads 16 --tmp-dir`. Historically normal used GPU 7 and tumor GPU 6.
5. samtools 1.19 `reheader -c`, changing **SM only** to `somatico` or `germinativo`, followed by `index -@ 8`. The discarded addreplacerg/fixed-BAM branch was not the final method. Other read-group fields, including the recorded PL value, are not silently corrected.
6. Parabricks 4.5.1-1 MutectCaller on the already recalibrated/reheadered BAMs, `--num-htvc-threads 32`, one exposed GPU (historically 7), names `somatico`/`germinativo`, the reference and a temporary directory. The recovered successful script does **not** pass the recalibration tables again into the caller.
7. Raw VCF compression/indexing; GATK FilterMutectCalls with original `.vcf.stats`, reference and `--create-output-variant-index true`; selection of PASS records.
8. VEP offline/cache 113 GRCh38, `--everything --fork 8 --vcf --compress_output bgzip`, read-only cache; output indexing.
9. Select `INFO/TLOD>0 && INFO/TLOD!="."` from the annotated PASS VCF and index the result.

No AF cutoff, new panel of normals, germline resource, confident-region BED, optimized RTG threshold or extra caller flag is added to this sequence.

## Versions: recorded tags versus actual software

The historical notebook used Parabricks `4.5.1-1`, samtools `1.19`, and a pinned htslib compression image. It used `:latest` for some downstream containers; the inspected output/log evidence recorded **GATK 4.6.2.0**, **BCFtools 1.21** and **VEP 113.0/cache 113**. Therefore `:latest` in an old script is not evidence that the historical study used a version different from the later Nextflow run.

Historical image digests remain unknown. The reconstructed recipe below uses version tags corresponding to the observed software, not a claim that a present-day image has the same bytes or every internal API commit as the historical container. In particular, VEP API commit metadata in the available new image was not identical in every component to the historical header.

## Path-adapted command recipe (not executed during migration)

`hg008_commands.py` prints a reviewable shell recipe; it **never runs Docker, creates outputs or reads sequencing data**. It is a new reconstruction, not an original 2025 script. It fixes unrelated example names/paths while retaining the recovered scientific options. Image tags for previously moving tags are normalized to observed tool versions, and output/log paths are organized under a supplied root. Its filename layout is documented by the generated commands.

For example:

```bash
python3 historical_workflows/parabricks/hg008_commands.py \
  --base /absolute/path/to/hg008_manual \
  --cache /absolute/path/to/vep_data \
  --stage call
```

Use `--stage all` to inspect every stage. Prepare the `raw/HG008_somatic`, `raw/HG008_germline`, `reference`, `known-sites` inputs under that base before any real use. GPU indices are configurable; no idle/reservation check is claimed. Review storage, permissions, versions and output paths before copying/executing a printed command. The recipes include no-overwrite checks for primary outputs, but are not an orchestrator or a validated replacement for the original Nextflow implementation.

The separate historical ApplyBQSR was real and must be accounted for when defining runtime scope. See [Runtime](../../analysis/runtime/README.md). A generic historical dbSNP GPU-annotation example is not inserted into the recovered HG008 chain merely because it existed in the old repository.
