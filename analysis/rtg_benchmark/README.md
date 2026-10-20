# RTG benchmarking

`originals/` contains the four scripts from `HG008-ROC-Parabricks-vs-DRAGEN`, covering the RTG analysis used in the study. They retain the original server paths and environment variables, which require configuration before execution on another system.

| Script | Step |
| --- | --- |
| `01_make_reference_sdf.sh` | `rtg format`: FASTA to reference SDF |
| `02_add_rtg_score_to_calls_vcf.sh` | Copy caller-specific confidence into `INFO.RTG_SCORE` |
| `03_run_vcfeval_annotate.sh` | Haplotype-aware comparison in annotate mode |
| `04_run_vcf2rocplot_and_rocplot.sh` | Weighted ROC-style table and plot |

Script 01 requires reference, output and image variables. Scripts 02–04 use the original paths. Script 03 creates its output directory before vcfeval; check this behavior against the installed RTG version's output-directory requirements.

## Analysis settings

- Reference: the same masked GIAB GRCh38 FASTA, converted with the documented `realtimegenomics/rtg-tools:3.12.1` image; recorded SDF version 13.
- Baseline: PASS-filtered DRAGEN comparator.
- Calls: PASS-filtered, positive-TLOD Parabricks calls prepared for RTG scoring.
- Sample mapping in the recovered scripts: `HG008-T-mosaic,somatico`.
- `rtg vcfeval -m annotate --squash-ploidy --ref-overlap --threads 8 --vcf-score-field INFO.RTG_SCORE`.
- Subsequent curves use `rtg vcf2rocplot -f INFO.RTG_SCORE` and `rtg rocplot`.

The vcfeval and curve scripts use `ghcr.io/uclahs-cds/rtg-tools:dev`. The historical binary version and digest for that image have not been recovered. The 3.12.1 reference-format image is recorded separately.

## Interpretation

The manuscript's optimized score threshold is **17.520**, distinct from the upstream `TLOD>0` input criterion. TP/FP/FN, precision, sensitivity and F-measure are relative to the DRAGEN comparator, not a validated somatic truth set. Baseline-side and call-side TP counts can differ under haplotype-aware representation matching.

The optimized RTG threshold is part of this benchmarking analysis and is not applied by the standard FASTQ-to-VCF workflow. Additional source and software-version details are listed in [Technical notes](../../docs/technical_notes.md).
