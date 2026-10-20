#!/usr/bin/env bash
set -euo pipefail

# Ajuste estes dois caminhos UMA VEZ e evite repetir:
IN_DIR="/home/murilo.aguiar/raid-murilo/Processos/1-Alinhamento-ExomaCompleto-LeticiaFerro-Parabricks_06-08-2025"
OUT_DIR="/home/murilo.aguiar/raid-murilo/Processos/1-Alinhamento-ExomaCompleto-LeticiaFerro-Parabricks_06-08-2025/2-BAMs-Cabecalho-Corrigido"
IMG="broadinstitute/gatk:latest"

# ============================
# AMOSTRA: TUMOR (exemplo)
# ============================
docker run --rm \
  -v "${IN_DIR}":/input \
  -v "${OUT_DIR}":/output \
  "${IMG}" \
  gatk AddOrReplaceReadGroups \
    -I /input/KOO311_TUMOR.bam \
    -O /output/KOO311_TUMOR_fixed.bam \
    -RGID TUMOR \
    -RGLB lib1 \
    -RGPL ILLUMINA \
    -RGPU UNIT1 \
    -RGSM KOO311_TUMOR \
    --CREATE_INDEX true

# ============================
# AMOSTRA: NORMAL (exemplo)
# ============================
docker run --rm \
  -v "${IN_DIR}":/input \
  -v "${OUT_DIR}":/output \
  "${IMG}" \
  gatk AddOrReplaceReadGroups \
    -I /input/KOO311_NORMAL.bam \
    -O /output/KOO311_NORMAL_fixed.bam \
    -RGID NORMAL \
    -RGLB lib1 \
    -RGPL ILLUMINA \
    -RGPU UNIT1 \
    -RGSM KOO311_NORMAL \
    --CREATE_INDEX true
