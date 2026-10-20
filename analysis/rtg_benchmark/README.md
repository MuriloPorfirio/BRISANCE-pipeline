# RTG benchmarking

The original four RTG scripts are preserved in `originals/`, copied unchanged from `HG008-ROC-Parabricks-vs-DRAGEN`. They document the historical command pattern; **do not execute them unchanged on another server**. They contain original Turing paths and require additional review described below.

| Script | Intended step |
| --- | --- |
| `01_make_reference_sdf.sh` | `rtg format`: FASTA to reference SDF |
| `02_add_rtg_score_to_calls_vcf.sh` | Copy caller-specific confidence into `INFO.RTG_SCORE` |
| `03_run_vcfeval_annotate.sh` | Haplotype-aware comparison in annotate mode |
| `04_run_vcf2rocplot_and_rocplot.sh` | Weighted ROC-style table and plot |

The source scripts are not a fully portable executable package. Script 01 references environment variables that must be supplied; scripts 02–04 include original paths. Script 03 also creates its output directory before calling vcfeval; confirm the actual successful historical command/log and the tool's output-directory requirements before using it. These issues are not retrospectively attributed to the successful original analysis.

## Historical scientific settings

- Reference: the same masked GIAB GRCh38 FASTA, converted with the documented `realtimegenomics/rtg-tools:3.12.1` image; recorded SDF version 13.
- Baseline: PASS-filtered DRAGEN comparator.
- Calls: PASS-filtered, positive-TLOD Parabricks calls prepared for RTG scoring.
- Sample mapping in the recovered scripts: `HG008-T-mosaic,somatico`.
- `rtg vcfeval -m annotate --squash-ploidy --ref-overlap --threads 8 --vcf-score-field INFO.RTG_SCORE`.
- Subsequent curves use `rtg vcf2rocplot -f INFO.RTG_SCORE` and `rtg rocplot`.

The vcfeval/curve scripts use `ghcr.io/uclahs-cds/rtg-tools:dev`. A moving tag does not identify the historical binary or image digest. The manuscript's statement of RTG Tools 3.12.1 must be reconciled with the actual vcfeval version record, not assumed from the separate format image.

## Reported interpretation

The manuscript's optimized score threshold is **17.520**, distinct from the upstream `TLOD>0` input criterion. TP/FP/FN, precision, sensitivity and F-measure are relative to the DRAGEN comparator, not a validated somatic truth set. Baseline-side and call-side TP counts can differ under haplotype-aware representation matching.

No new threshold is applied to normal BRISANCE final outputs by this section. No RTG execution has been rerun during repository preparation. The original commands, actual version evidence, raw `weighted_roc.tsv.gz` and figure-generation inputs remain items for the [release checklist](../../docs/release_checklist.md).
