#!/usr/bin/env bash
set -euo pipefail

# Set default BAM path if not provided
BAM_HOST="${1:-/raid/biomafia/murilo.aguiar/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/2-Bams-e-tabelaBQSR/HG008-IDUDI0031-somatico-tentativa2.bam}"

# Convert to absolute path if needed
if [[ "${BAM_HOST}" != /* ]]; then
  BAM_HOST="$(cd "$(dirname "$BAM_HOST")" && pwd -P)/$(basename "$BAM_HOST")"
fi

# Docker image with samtools
SAMTOOLS_IMG="staphb/samtools:1.19"

# Extract path and filename
HOST_DIR="$(dirname "$BAM_HOST")"
BAM_BASE="$(basename "$BAM_HOST")"

# Helper function to run samtools in Docker
s() { docker run --rm -v "${HOST_DIR}:/data" "$SAMTOOLS_IMG" bash -lc "$*"; }

# Display @RG entries
echo "== @RG in header =="
s "samtools view -H /data/${BAM_BASE} | grep -n '^@RG' || true"

echo "== SM =="
s "samtools view -H /data/${BAM_BASE} | awk -F'\t' '/^@RG/{for(i=1;i<=NF;i++) if(\$i ~ /^SM:/) print substr(\$i,4)}' | sort -u"

echo "== ID =="
s "samtools view -H /data/${BAM_BASE} | awk -F'\t' '/^@RG/{for(i=1;i<=NF;i++) if(\$i ~ /^ID:/) print substr(\$i,4)}' | sort -u"

echo "== PU =="
s "samtools view -H /data/${BAM_BASE} | awk -F'\t' '/^@RG/{for(i=1;i<=NF;i++) if(\$i ~ /^PU:/) print substr(\$i,4)}' | sort -u"

echo "== PL/LB =="
s "samtools view -H /data/${BAM_BASE} | awk -F'\t' '/^@RG/{pl=\"\";lb=\"\";for(i=1;i<=NF;i++){if(\$i ~ /^PL:/) pl=substr(\$i,4); if(\$i ~ /^LB:/) lb=substr(\$i,4);} if(pl!=\"\"||lb!=\"\") print \"PL=\"pl\"\tLB=\"lb}' | sort -u"

# Show RG tags in actual reads
echo "== RG tags in reads (first 10k) =="
s "samtools view /data/${BAM_BASE} | head -10000 | grep -o 'RG:Z:[^[:space:]]\\+' | head -20 || true"

# Count RGs in reads
echo "== Count by RG (first 200k) =="
s "samtools view /data/${BAM_BASE} | head -200000 | grep -o 'RG:Z:[^[:space:]]\\+' | sort | uniq -c | sort -nr | head || true"

# Sort order of BAM
echo "== Sort order (@HD SO) =="
s "samtools view -H /data/${BAM_BASE} | awk -F'\t' '/^@HD/{for(i=1;i<=NF;i++) if(\$i ~ /^SO:/) print \$i}'"

# Validation before prompting
RG_COUNT=$(s "samtools view -H /data/${BAM_BASE} | grep -c '^@RG'")
SM_COUNT=$(s "samtools view -H /data/${BAM_BASE} | awk -F'\t' '/^@RG/ {for(i=1;i<=NF;i++) if(\$i ~ /^SM:/) print substr(\$i,4)}' | sort -u | wc -l")

if [[ "$RG_COUNT" -eq 0 ]]; then
  echo "== ERROR: No @RG found. Indexing aborted. =="
  exit 1
fi

if [[ "$SM_COUNT" -eq 0 ]]; then
  echo "== ERROR: No SM tag found in @RG. Indexing aborted. =="
  exit 1
fi

# Ask user whether to proceed
echo ""
read -p "Deseja prosseguir com a indexação? (sim/nao): " RESPOSTA
if [[ "$RESPOSTA" != "sim" ]]; then
  echo "== Indexação cancelada pelo usuário. =="
  exit 0
fi

# Only index if .bai does not exist
if [ ! -f "${BAM_HOST}.bai" ]; then
  echo "== Indexing (no .bai was present) =="
  s "samtools index /data/${BAM_BASE}"
else
  echo "== Index already exists (.bai found) =="
fi
