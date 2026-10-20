#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  gatk_baserecal_docker.sh \
    --in-bam in.markdup.bam \
    --ref ref.fa \
    --known-sites known1.vcf.gz --known-sites known2.vcf.gz [--known-sites known3.vcf.gz ...] \
    --out-table out.recal.table \
    [--image broadinstitute/gatk:latest] \
    [--cpus 48] [--mem 128g] \
    [--java-heap 32g] \
    [--uidgid 1000:1000] \
    [--tmpdir /path/tmp] \
    [--log run.log]

Output:
  out.recal.table
EOF
}

IN_BAM=""
REF=""
OUT_TABLE=""
IMAGE="broadinstitute/gatk:latest"
CPUS=""
MEM=""
JAVA_HEAP="32g"
UIDGID="$(id -u):$(id -g)"
TMPDIR=""
LOG=""

KNOWN_SITES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --in-bam) IN_BAM="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    --known-sites) KNOWN_SITES+=("$2"); shift 2;;
    --out-table) OUT_TABLE="$2"; shift 2;;
    --image) IMAGE="$2"; shift 2;;
    --cpus) CPUS="$2"; shift 2;;
    --mem) MEM="$2"; shift 2;;
    --java-heap) JAVA_HEAP="$2"; shift 2;;
    --uidgid) UIDGID="$2"; shift 2;;
    --tmpdir) TMPDIR="$2"; shift 2;;
    --log) LOG="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$IN_BAM" || -z "$REF" || -z "$OUT_TABLE" || ${#KNOWN_SITES[@]} -lt 1 ]]; then
  echo "Missing required args." >&2
  usage
  exit 1
fi

IN_BAM="$(realpath "$IN_BAM")"
REF="$(realpath "$REF")"
OUT_TABLE="$(realpath -m "$OUT_TABLE")"

[[ -f "$IN_BAM" ]] || { echo "Not found: $IN_BAM" >&2; exit 1; }
[[ -f "$REF" ]] || { echo "Not found: $REF" >&2; exit 1; }

for ks in "${KNOWN_SITES[@]}"; do
  ks="$(realpath "$ks")"
  [[ -f "$ks" ]] || { echo "Not found: $ks" >&2; exit 1; }
done

OUT_DIR="$(dirname "$OUT_TABLE")"
mkdir -p "$OUT_DIR"

if [[ -z "$TMPDIR" ]]; then
  TMPDIR="${OUT_DIR}/tmp_baserecal"
fi
TMPDIR="$(realpath -m "$TMPDIR")"
mkdir -p "$TMPDIR"

if [[ -z "$LOG" ]]; then
  LOG="${OUT_TABLE}.log"
fi
LOG="$(realpath -m "$LOG")"
mkdir -p "$(dirname "$LOG")"

[[ -f "${IN_BAM}.bai" ]] || echo "Warning: missing BAM index: ${IN_BAM}.bai" >&2
[[ -f "${REF}.fai" ]] || echo "Warning: missing reference index: ${REF}.fai" >&2

REF_DICT=""
if [[ "$REF" == *.fasta ]]; then
  REF_DICT="${REF%.fasta}.dict"
elif [[ "$REF" == *.fa ]]; then
  REF_DICT="${REF%.fa}.dict"
fi
[[ -n "$REF_DICT" && ! -f "$REF_DICT" ]] && echo "Warning: missing reference dict: ${REF_DICT}" >&2

IN_DIR="$(dirname "$IN_BAM")"
REF_DIR="$(dirname "$REF")"
IN_NAME="$(basename "$IN_BAM")"
REF_NAME="$(basename "$REF")"
OUT_NAME="$(basename "$OUT_TABLE")"

docker_args=(run --rm -u "$UIDGID")
[[ -n "$CPUS" ]] && docker_args+=(--cpus "$CPUS")
[[ -n "$MEM"  ]] && docker_args+=(--memory "$MEM")

docker_args+=(
  -v "$IN_DIR:/in:ro"
  -v "$REF_DIR:/ref:ro"
  -v "$OUT_DIR:/out"
  -v "$TMPDIR:/tmp"
)

known_args=()
i=0
for ks in "${KNOWN_SITES[@]}"; do
  ks_abs="$(realpath "$ks")"
  ks_dir="$(dirname "$ks_abs")"
  ks_name="$(basename "$ks_abs")"
  mp="/known${i}"
  docker_args+=(-v "$ks_dir:${mp}:ro")
  known_args+=(--known-sites "${mp}/${ks_name}")
  i=$((i+1))
done

echo "BaseRecalibrator: $IN_BAM -> $OUT_TABLE" | tee "$LOG"

"${docker_args[@]}" "$IMAGE" \
  gatk --java-options "-Xmx${JAVA_HEAP} -Djava.io.tmpdir=/tmp" \
    BaseRecalibrator \
    -I "/in/${IN_NAME}" \
    -R "/ref/${REF_NAME}" \
    "${known_args[@]}" \
    -O "/out/${OUT_NAME}" \
  2>&1 | tee -a "$LOG"

echo "Done: $OUT_TABLE" | tee -a "$LOG"
