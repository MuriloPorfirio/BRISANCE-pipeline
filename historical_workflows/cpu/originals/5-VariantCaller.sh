#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  mutect2_batch.sh --bam-dir /path/bams --ref /path/ref.fa --out-dir /path/out
                  [--threads 8]
                  [--germline-resource /path/resource.vcf.gz]
                  [--pon /path/pon.vcf.gz]
                  [--tumor-glob '*-somatic*.recal.bam']
                  [--normal-glob '*-germinativo*.recal.bam']

Expects:
  tumor BAMs and normal BAMs in --bam-dir, paired by sample_id:
    sample_id is the prefix before "-somatic" / "-germinativo" in the filename.

Outputs:
  out-dir/<sample_id>/<sample_id>_somatic.vcf.gz
  out-dir/<sample_id>/<sample_id>_mutect.bam
  out-dir/summary.tsv
EOF
}

die(){ echo "ERROR: $*" >&2; exit 1; }

ts(){ date "+%Y-%m-%d %H:%M:%S"; }

fmt_time() {
  local s="$1" h m r
  h=$((s/3600)); m=$(((s%3600)/60)); r=$((s%60))
  printf "%02d:%02d:%02d" "$h" "$m" "$r"
}

get_sm_from_bam() {
  local bam="$1"
  samtools view -H "$bam" \
    | awk -F'\t' '$1=="@RG"{for(i=1;i<=NF;i++) if($i ~ /^SM:/){sub(/^SM:/,"",$i); print $i; exit}}'
}

ensure_bai() {
  local bam="$1"
  if [[ -e "${bam}.bai" ]]; then return 0; fi
  local alt="${bam%.bam}.bai"
  if [[ -e "$alt" ]]; then ln -sf "$alt" "${bam}.bai"; return 0; fi
  samtools index -@ "${THREADS}" "$bam"
}

BAM_DIR=""
REF=""
OUT_DIR=""
THREADS=8
GERMLINE_RESOURCE=""
PON=""
TUMOR_GLOB="*-somatic*.recal.bam"
NORMAL_GLOB="*-germinativo*.recal.bam"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bam-dir) BAM_DIR="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    --out-dir) OUT_DIR="$2"; shift 2;;
    --threads) THREADS="$2"; shift 2;;
    --germline-resource) GERMLINE_RESOURCE="$2"; shift 2;;
    --pon) PON="$2"; shift 2;;
    --tumor-glob) TUMOR_GLOB="$2"; shift 2;;
    --normal-glob) NORMAL_GLOB="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) die "Unknown arg: $1";;
  esac
done

[[ -n "$BAM_DIR" && -n "$REF" && -n "$OUT_DIR" ]] || { usage; exit 1; }

[[ -d "$BAM_DIR" ]] || die "bam-dir not found: $BAM_DIR"
[[ -f "$REF" ]] || die "ref not found: $REF"
mkdir -p "$OUT_DIR"

command -v samtools >/dev/null 2>&1 || die "samtools not in PATH"
command -v gatk >/dev/null 2>&1 || die "gatk not in PATH"

if [[ -n "$GERMLINE_RESOURCE" ]]; then [[ -f "$GERMLINE_RESOURCE" ]] || die "germline-resource not found"; fi
if [[ -n "$PON" ]]; then [[ -f "$PON" ]] || die "pon not found"; fi

run_id="$(date +%Y%m%d_%H%M%S)"
summary="${OUT_DIR}/summary_${run_id}.tsv"
echo -e "sample_id\ttumor_bam\tnormal_bam\tstatus\tseconds\telapsed\tvcf_out\tlog_sample" > "$summary"

shopt -s nullglob
tumor_bams=( "${BAM_DIR}"/${TUMOR_GLOB} )
normal_bams=( "${BAM_DIR}"/${NORMAL_GLOB} )
shopt -u nullglob

[[ ${#tumor_bams[@]} -gt 0 ]] || die "no tumor BAMs matched: ${BAM_DIR}/${TUMOR_GLOB}"
[[ ${#normal_bams[@]} -gt 0 ]] || die "no normal BAMs matched: ${BAM_DIR}/${NORMAL_GLOB}"

declare -A tumor_map normal_map

for tbam in "${tumor_bams[@]}"; do
  b="$(basename "$tbam")"
  sid="${b%%-somatic*}"
  tumor_map["$sid"]="$tbam"
done

for nbam in "${normal_bams[@]}"; do
  b="$(basename "$nbam")"
  sid="${b%%-germinativo*}"
  normal_map["$sid"]="$nbam"
done

pipeline_start="$(date +%s)"
ok=0; fail=0; skip=0

for sid in "${!tumor_map[@]}"; do
  tbam="${tumor_map[$sid]}"
  nbam="${normal_map[$sid]:-}"

  if [[ -z "$nbam" ]]; then
    echo "[$(ts)] skip ${sid} (no normal)"
    echo -e "${sid}\t${tbam}\tNA\tSKIP_NO_NORMAL\t0\t00:00:00\tNA\tNA" >> "$summary"
    ((skip++))
    continue
  fi

  sample_dir="${OUT_DIR}/${sid}"
  log_dir="${sample_dir}/logs"
  mkdir -p "$log_dir"

  log_sample="${log_dir}/${sid}_mutect2_${run_id}.log"
  vcf_out="${sample_dir}/${sid}_somatic.vcf.gz"
  bamout="${sample_dir}/${sid}_mutect.bam"

  {
    echo "[$(ts)] sample=${sid}"
    echo "tumor=$tbam"
    echo "normal=$nbam"

    ensure_bai "$tbam"
    ensure_bai "$nbam"

    tumor_sm="$(get_sm_from_bam "$tbam")"
    normal_sm="$(get_sm_from_bam "$nbam")"
    [[ -n "$tumor_sm" ]] || die "no SM in tumor header: $tbam"
    [[ -n "$normal_sm" ]] || die "no SM in normal header: $nbam"

    extra=()
    if [[ -n "$GERMLINE_RESOURCE" ]]; then extra+=(--germline-resource "$GERMLINE_RESOURCE"); fi
    if [[ -n "$PON" ]]; then extra+=(--panel-of-normals "$PON"); fi

    start="$(date +%s)"
    gatk Mutect2 \
      -R "$REF" \
      -I "$tbam" -tumor "$tumor_sm" \
      -I "$nbam" -normal "$normal_sm" \
      "${extra[@]}" \
      -O "$vcf_out" \
      -bam-output "$bamout"
    end="$(date +%s)"
    secs=$((end-start))

    echo "[$(ts)] done in $(fmt_time "$secs")"
    echo "$secs" > "${log_dir}/${sid}_mutect2_${run_id}.seconds"
  } 2>&1 | tee "$log_sample"

  if [[ -f "$vcf_out" ]]; then
    secs="$(cat "${log_dir}/${sid}_mutect2_${run_id}.seconds" 2>/dev/null || echo 0)"
    echo -e "${sid}\t${tbam}\t${nbam}\tOK\t${secs}\t$(fmt_time "$secs")\t${vcf_out}\t${log_sample}" >> "$summary"
    ((ok++))
  else
    echo -e "${sid}\t${tbam}\t${nbam}\tFAIL_NO_VCF\t0\t00:00:00\tNA\t${log_sample}" >> "$summary"
    ((fail++))
  fi
done

pipeline_end="$(date +%s)"
total=$((pipeline_end - pipeline_start))

echo "[$(ts)] finished ok=${ok} fail=${fail} skip=${skip} total=$(fmt_time "$total")"
echo "summary: $summary"
