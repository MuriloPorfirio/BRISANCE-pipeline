#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  gatk_applybqsr_docker.sh \
    --in-bam in.markdup.bam \
    --ref ref.fa \
    --recal-table in.recal.table \
    --out-bam out.recal.bam \
    [--gatk-image broadinstitute/gatk:latest] \
    [--samtools-image staphb/samtools:latest] \
    [--cpus 48] [--mem 128g] \
    [--java-xms 4g] [--java-xmx 32g] \
    [--index-threads 8] \
    [--uidgid 1000:1000] \
    [--tmpdir /path/tmp] \
    [--log run.log]

Outputs:
  out.recal.bam
  out.recal.bam.bai
EOF
}

IN_BAM=""
REF=""
RECAL_TABLE=""
OUT_BAM=""

GATK_IMAGE="broadinstitute/gatk:latest"
SAMTOOLS_IMAGE="staphb/samtools:latest"

CPUS=""
MEM=""
JAVA_XMS="4g"
JAVA_XMX="32g"
INDEX_THREADS="8"

UIDGID="$(id -u):$(id -g)"
TMPDIR=""
LOG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --in-bam) IN_BAM="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    --recal-table) RECAL_TABLE="$2"; shift 2;;
    --out-bam) OUT_BAM="$2"; shift 2;;
    --gatk-image) GATK_IMAGE="$2"; shift 2;;
    --samtools-image) SAMTOOLS_IMAGE="$2"; shift 2;;
    --cpus) CPUS="$2"; shift 2;;
    --mem) MEM="$2"; shift 2;;
    --java-xms) JAVA_XMS="$2"; shift 2;;
    --java-xmx) JAVA_XMX="$2"; shift 2;;
    --index-threads) INDEX_THREADS="$2"; shift 2;;
    --uidgid) UIDGID="$2"; shift 2;;
    --tmpdir) TMPDIR="$2"; shift 2;;
    --log) LOG="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$IN_BAM" || -z "$REF" || -z "$RECAL_TABLE" || -z "$OUT_BAM" ]]; then
  echo "Missing required args." >&2
  usage
  exit 1
fi

IN_BAM="$(realpath "$IN_BAM")"
REF="$(realpath "$REF")"
RECAL_TABLE="$(realpath "$RECAL_TABLE")"
OUT_BAM="$(realpath -m "$OUT_BAM")"

[[ -f "$IN_BAM" ]] || { echo "Not found: $IN_BAM" >&2; exit 1; }
[[ -f "$REF" ]] || { echo "Not found: $REF" >&2; exit 1; }
[[ -f "$RECAL_TABLE" ]] || { echo "Not found: $RECAL_TABLE" >&2; exit 1; }

OUT_DIR="$(dirname "$OUT_BAM")"
mkdir -p "$OUT_DIR"

if [[ -z "$TMPDIR" ]]; then
  TMPDIR="${OUT_DIR}/tmp_applybqsr"
fi
TMPDIR="$(realpath -m "$TMPDIR")"
mkdir -p "$TMPDIR"

if [[ -z "$LOG" ]]; then
  LOG="${OUT_BAM}.log"
fi
LOG="$(realpath -m "$LOG")"
mkdir -p "$(dirname "$LOG")"

[[ -f "${REF}.fai" ]] || echo "Warning: missing reference index: ${REF}.fai" >&2
DICT=""
if [[ "$REF" == *.fasta ]]; then
  DICT="${REF%.fasta}.dict"
elif [[ "$REF" == *.fa ]]; then
  DICT="${REF%.fa}.dict"
fi
[[ -n "$DICT" && ! -f "$DICT" ]] && echo "Warning: missing reference dict: ${DICT}" >&2

IN_DIR="$(dirname "$IN_BAM")"
REF_DIR="$(dirname "$REF")"
TAB_DIR="$(dirname "$RECAL_TABLE")"

IN_NAME="$(basename "$IN_BAM")"
REF_NAME="$(basename "$REF")"
TAB_NAME="$(basename "$RECAL_TABLE")"

OUT_NAME="$(basename "$OUT_BAM")"

docker_gatk=(run --rm -u "$UIDGID")
docker_st=(run --rm -u "$UIDGID")
[[ -n "$CPUS" ]] && docker_gatk+=(--cpus "$CPUS") && docker_st+=(--cpus "$CPUS")
[[ -n "$MEM"  ]] && docker_gatk+=(--memory "$MEM") && docker_st+=(--memory "$MEM")

echo "ApplyBQSR: $IN_BAM -> $OUT_BAM" | tee "$LOG"

"${docker_gatk[@]}" \
  -v "$IN_DIR:/in:ro" \
  -v "$REF_DIR:/ref:ro" \
  -v "$TAB_DIR:/tab:ro" \
  -v "$OUT_DIR:/out" \
  -v "$TMPDIR:/tmp" \
  "$GATK_IMAGE" \
  gatk --java-options "-Xms${JAVA_XMS} -Xmx${JAVA_XMX} -Djava.io.tmpdir=/tmp" \
    ApplyBQSR \
    --tmp-dir /tmp \
    -R "/ref/${REF_NAME}" \
    -I "/in/${IN_NAME}" \
    --bqsr-recal-file "/tab/${TAB_NAME}" \
    -O "/out/${OUT_NAME}" \
  2>&1 | tee -a "$LOG"

echo "Indexing..." | tee -a "$LOG"
"${docker_st[@]}" \
  -v "$OUT_DIR:/out" \
  "$SAMTOOLS_IMAGE" \
  samtools index -@ "$INDEX_THREADS" "/out/${OUT_NAME}" \
  2>&1 | tee -a "$LOG"

echo "Quickcheck..." | tee -a "$LOG"
"${docker_st[@]}" \
  -v "$OUT_DIR:/out" \
  "$SAMTOOLS_IMAGE" \
  samtools quickcheck -v "/out/${OUT_NAME}" \
  2>&1 | tee -a "$LOG"

echo "Done: $OUT_BAM" | tee -a "$LOG"
