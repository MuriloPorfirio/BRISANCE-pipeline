#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <clara.pass.nonsymbolic.vcf.gz> <dragen.pass.nonsymbolic.vcf.gz> <output_dir>"
    exit 1
fi

CLARA_VCF="$1"
DRAGEN_VCF="$2"
OUTDIR="$3"

STATS_FILE="${OUTDIR}/comparison_pass.stats"
PLOTS_DIR="${OUTDIR}/comparison_pass_plots"

mkdir -p "${OUTDIR}"

check_file() {
    local f="$1"
    if [[ ! -f "${f}" ]]; then
        echo "ERROR: File not found: ${f}" >&2
        exit 1
    fi
}

check_tool() {
    local t="$1"
    if ! command -v "${t}" >/dev/null 2>&1; then
        echo "ERROR: Required tool not found in PATH: ${t}" >&2
        exit 1
    fi
}

check_file "${CLARA_VCF}"
check_file "${DRAGEN_VCF}"

check_tool bcftools
check_tool plot-vcfstats

echo "[INFO] Running bcftools stats..."
echo "[INFO] Input 0 (CLARA/Parabricks): ${CLARA_VCF}"
echo "[INFO] Input 1 (DRAGEN): ${DRAGEN_VCF}"

bcftools stats \
    "${CLARA_VCF}" \
    "${DRAGEN_VCF}" \
    > "${STATS_FILE}"

echo "[INFO] Stats file written to: ${STATS_FILE}"

echo "[INFO] Generating plot-vcfstats outputs..."
plot-vcfstats \
    -p "${PLOTS_DIR}" \
    "${STATS_FILE}"

echo "[INFO] Plot files written to: ${PLOTS_DIR}"
echo
echo "[INFO] Expected useful outputs include:"
echo "  - ${STATS_FILE}"
echo "  - ${PLOTS_DIR}/indels.0.dat"
echo "  - ${PLOTS_DIR}/indels.1.dat"
echo
echo "[INFO] Step 2 completed successfully."
