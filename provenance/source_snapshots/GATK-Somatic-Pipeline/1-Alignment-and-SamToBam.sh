#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bwa_docker_align.sh --ref ref.fa --r1-list r1.txt --r2-list r2.txt --out-prefix out/sample
                    [--threads 32] [--sort-threads 16] [--sort-mem 2G]
                    [--sample SAMPLE] [--platform ILLUMINA] [--library LIB1] [--unit UNIT1]

r1.txt / r2.txt: one FASTQ(.gz) path per line (in order).
Output:
  <out-prefix>.sorted.bam
  <out-prefix>.sorted.bam.bai
EOF
}

THREADS=32
SORT_THREADS=16
SORT_MEM="2G"
SAMPLE="SAMPLE"
PLATFORM="ILLUMINA"
LIBRARY="LIB1"
UNIT="UNIT1"

IMG_BWA="biocontainers/bwa:v0.7.17_cv1"
IMG_SAMTOOLS="biocontainers/samtools:v1.20-3-deb_cv1"

REF=""
R1_LIST=""
R2_LIST=""
OUT_PREFIX=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="$2"; shift 2;;
    --r1-list) R1_LIST="$2"; shift 2;;
    --r2-list) R2_LIST="$2"; shift 2;;
    --out-prefix) OUT_PREFIX="$2"; shift 2;;
    --threads) THREADS="$2"; shift 2;;
    --sort-threads) SORT_THREADS="$2"; shift 2;;
    --sort-mem) SORT_MEM="$2"; shift 2;;
    --sample) SAMPLE="$2"; shift 2;;
    --platform) PLATFORM="$2"; shift 2;;
    --library) LIBRARY="$2"; shift 2;;
    --unit) UNIT="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$REF" || -z "$R1_LIST" || -z "$R2_LIST" || -z "$OUT_PREFIX" ]]; then
  echo "Missing required arguments." >&2
  usage
  exit 1
fi

for f in "$REF" "$R1_LIST" "$R2_LIST"; do
  [[ -e "$f" ]] || { echo "Not found: $f" >&2; exit 1; }
done

WORKDIR="$(pwd)"
OUT_BAM="${OUT_PREFIX}.sorted.bam"
LOG="${OUT_PREFIX}.align.log"

RG="@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:${PLATFORM}\tLB:${LIBRARY}\tPU:${UNIT}"

MERGED_R1="${OUT_PREFIX}.R1.merged.fq.gz"
MERGED_R2="${OUT_PREFIX}.R2.merged.fq.gz"

mkdir -p "$(dirname "$OUT_PREFIX")"

echo "Merging R1 -> ${MERGED_R1}" | tee "${LOG}"
xargs -a "${R1_LIST}" cat > "${MERGED_R1}"

echo "Merging R2 -> ${MERGED_R2}" | tee -a "${LOG}"
xargs -a "${R2_LIST}" cat > "${MERGED_R2}"

UIDGID="$(id -u):$(id -g)"

echo "Aligning and sorting..." | tee -a "${LOG}"
docker run --rm \
  -u "${UIDGID}" \
  -v "${WORKDIR}:/work" \
  -w /work \
  "${IMG_BWA}" \
  bwa mem -t "${THREADS}" -R "${RG}" \
    "/work/${REF##*/}" \
    "/work/${MERGED_R1##*/}" \
    "/work/${MERGED_R2##*/}" 2>> "${LOG}" \
| docker run --rm \
    -u "${UIDGID}" \
    -v "${WORKDIR}:/work" \
    -w /work \
    "${IMG_SAMTOOLS}" \
    samtools sort -@ "${SORT_THREADS}" -m "${SORT_MEM}" -o "/work/${OUT_BAM##*/}" - 2>> "${LOG}"

echo "Indexing..." | tee -a "${LOG}"
docker run --rm \
  -u "${UIDGID}" \
  -v "${WORKDIR}:/work" \
  -w /work \
  "${IMG_SAMTOOLS}" \
  samtools index -@ "${SORT_THREADS}" "/work/${OUT_BAM##*/}" 2>> "${LOG}"

echo "Done: ${OUT_BAM}" | tee -a "${LOG}"
