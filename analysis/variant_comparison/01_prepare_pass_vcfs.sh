#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <clara.vcf.gz> <dragen.vcf.gz> <output_dir>"
    exit 1
fi

CLARA_VCF="$1"
DRAGEN_VCF="$2"
OUTDIR="$3"

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

prepare_vcf() {
    local input_vcf="$1"
    local sample_name="$2"
    local output_vcf="${OUTDIR}/${sample_name}.pass.nonsymbolic.vcf.gz"
    local summary_txt="${OUTDIR}/${sample_name}.summary.txt"

    echo "[INFO] Preparing ${sample_name}..."

    # Keep only PASS records and remove symbolic ALT entries:
    #   - ALT="*"   -> spanning deletion allele
    #   - ALT~"^<"  -> symbolic alleles such as <DEL>, <NON_REF>, etc.
    bcftools view \
        -f PASS \
        -e 'ALT="*" || ALT~"^<"' \
        -Oz \
        -o "${output_vcf}" \
        "${input_vcf}"

    bcftools index -t -f "${output_vcf}"

    {
        echo "sample=${sample_name}"
        echo "file=${output_vcf}"
        echo -n "total_records="
        bcftools view -H "${output_vcf}" | wc -l
        echo -n "snvs="
        bcftools view -H -v snps "${output_vcf}" | wc -l
        echo -n "indels="
        bcftools view -H -v indels "${output_vcf}" | wc -l
        echo -n "mnps="
        bcftools view -H -v mnps "${output_vcf}" | wc -l
    } > "${summary_txt}"

    echo "[INFO] Done: ${output_vcf}"
    echo "[INFO] Summary: ${summary_txt}"
    echo
}

prepare_vcf "${CLARA_VCF}" "clara"
prepare_vcf "${DRAGEN_VCF}" "dragen"

echo "[INFO] Step 1 completed successfully."
echo "[INFO] Prepared VCFs are in: ${OUTDIR}"
