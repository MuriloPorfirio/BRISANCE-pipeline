#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  gatk_markdup_docker.sh --in-bam in.bam --out-bam out.markdup.bam
                         [--metrics out.metrics.txt]
                         [--tmpdir /path/tmp_markdup]
                         [--image broadinstitute/gatk:latest]
                         [--cpus 48] [--mem 128g]
                         [--java-xms 16g] [--java-xmx 64g] [--gc-threads 8]
                         [--uidgid 1000:1000]
                         [--log run.log]

Notes:
  - Marca duplicatas (não remove).
  - Cria índice do BAM de saída.
EOF
}

IN_BAM=""
OUT_BAM=""
METRICS=""
TMPDIR=""
IMAGE="broadinstitute/gatk:latest"
CPUS=""
MEM=""
JAVA_XMS="16g"
JAVA_XMX="64g"
GC_THREADS="8"
UIDGID="$(id -u):$(id -g)"
LOG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --in-bam) IN_BAM="$2"; shift 2;;
    --out-bam) OUT_BAM="$2"; shift 2;;
    --metrics) METRICS="$2"; shift 2;;
    --tmpdir) TMPDIR="$2"; shift 2;;
    --image) IMAGE="$2"; shift 2;;
    --cpus) CPUS="$2"; shift 2;;
    --mem) MEM="$2"; shift 2;;
    --java-xms) JAVA_XMS="$2"; shift 2;;
    --java-xmx) JAVA_XMX="$2"; shift 2;;
    --gc-threads) GC_THREADS="$2"; shift 2;;
    --uidgid) UIDGID="$2"; shift 2;;
    --log) LOG="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$IN_BAM" || -z "$OUT_BAM" ]]; then
  echo "Missing --in-bam or --out-bam" >&2
  usage
  exit 1
fi

IN_BAM="$(realpath "$IN_BAM")"
OUT_BAM="$(realpath -m "$OUT_BAM")"

[[ -f "$IN_BAM" ]] || { echo "Not found: $IN_BAM" >&2; exit 1; }

OUT_DIR="$(dirname "$OUT_BAM")"
mkdir -p "$OUT_DIR"

if [[ -z "$METRICS" ]]; then
  METRICS="${OUT_BAM}.metrics.txt"
fi
METRICS="$(realpath -m "$METRICS")"

if [[ -z "$TMPDIR" ]]; then
  TMPDIR="${OUT_DIR}/tmp_markdup"
fi
TMPDIR="$(realpath -m "$TMPDIR")"
mkdir -p "$TMPDIR"

if [[ -z "$LOG" ]]; then
  LOG="${OUT_BAM}.log"
fi
LOG="$(realpath -m "$LOG")"
mkdir -p "$(dirname "$LOG")"

IN_DIR="$(dirname "$IN_BAM")"
OUT_DIR="$(dirname "$OUT_BAM")"
MET_DIR="$(dirname "$METRICS")"

IN_NAME="$(basename "$IN_BAM")"
OUT_NAME="$(basename "$OUT_BAM")"
MET_NAME="$(basename "$METRICS")"

docker_args=(run --rm -u "$UIDGID")
[[ -n "$CPUS" ]] && docker_args+=(--cpus "$CPUS")
[[ -n "$MEM"  ]] && docker_args+=(--memory "$MEM")

docker_args+=(
  -v "$IN_DIR:/in:ro"
  -v "$OUT_DIR:/out"
  -v "$MET_DIR:/metrics"
  -v "$TMPDIR:/tmp"
)

echo "MarkDuplicates: $IN_BAM -> $OUT_BAM" | tee "$LOG"

"${docker_args[@]}" "$IMAGE" \
  gatk --java-options "-Xms${JAVA_XMS} -Xmx${JAVA_XMX} -XX:ParallelGCThreads=${GC_THREADS}" \
    MarkDuplicates \
    -I "/in/${IN_NAME}" \
    -O "/out/${OUT_NAME}" \
    -M "/metrics/${MET_NAME}" \
    --TMP_DIR "/tmp" \
    --CREATE_INDEX true \
    --REMOVE_DUPLICATES false \
    --VALIDATION_STRINGENCY SILENT \
  2>&1 | tee -a "$LOG"

echo "Done: $OUT_BAM" | tee -a "$LOG"
