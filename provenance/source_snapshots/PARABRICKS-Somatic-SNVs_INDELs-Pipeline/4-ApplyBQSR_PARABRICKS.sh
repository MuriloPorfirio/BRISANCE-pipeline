#!/usr/bin/env bash
set -euo pipefail

SECONDS=0

# Caminho real no host
HOST_BASE="/raid/biomafia/murilo.aguiar"
OUT_DIR="${HOST_BASE}/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/3-Bams-recalibrados"
LOG_FILE="${OUT_DIR}/HG008-IDUDI0031-germinativo.applybqsr.log"

# Verifica se o diretório existe e cria log vazio
mkdir -p "$OUT_DIR"
touch "$LOG_FILE" || { echo "ERROR: Cannot create log file at $LOG_FILE"; exit 1; }

# Executa o processo com log em tempo real
{
  echo "=== Running applybqsr ==="
  date

  time docker run --rm --gpus device=7 \
    --user 1006:1002 \
    -v ${HOST_BASE}:/workdir \
    --workdir /workdir \
    nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1 \
    pbrun applybqsr \
      --ref /workdir/Genomas_de_referencia/humano/Genoma_Referencia_Cancer_in_a_Bottle/GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta \
      --in-bam /workdir/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/2-Bams-e-tabelaBQSR/HG008-IDUDI0031-germinativo.bam \
      --in-recal-file /workdir/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/2-Bams-e-tabelaBQSR/HG008-IDUDI0031-germinativo.recal.table \
      --out-bam /workdir/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/3-Bams-recalibrados/HG008-IDUDI0031-germinativo.bqsr.bam \
      --num-gpus 1 \
      --num-threads 16 \
      --tmp-dir /workdir/TMP_parabricks

  duration=$SECONDS
  echo "=== applybqsr completed in $((duration / 60)) min $((duration % 60)) sec ==="
  date
} 2>&1 | tee -a "$LOG_FILE"

