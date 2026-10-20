#!/usr/bin/env bash
set -euo pipefail


INPUT_VCF_GZ="/path/to/HG008-IDUDI0031_somatico_vs_germinativo.PASS_annotado.vep.vcf.gz"
OUTPUT_VCF_GZ="/path/to/HG008-IDUDI0031_somatico_vs_germinativo.PASS_RTG.vcf.gz"

# Score to copy from the original calls VCF
SOURCE_INFO_TAG="TLOD"

# Score field expected later by RTG
TARGET_INFO_TAG="RTG_SCORE"

# Container with bcftools/bgzip/tabix
BCFTOOLS_IMAGE="staphb/bcftools:1.24"

# Optional temp working directory
TMP_DIR="$(mktemp -d)"


cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT


if [[ ! -f "${INPUT_VCF_GZ}" ]]; then
  echo "ERROR: Input VCF not found:"
  echo "  ${INPUT_VCF_GZ}"
  exit 1
fi

if [[ "${INPUT_VCF_GZ}" == "${OUTPUT_VCF_GZ}" ]]; then
  echo "ERROR: INPUT_VCF_GZ and OUTPUT_VCF_GZ must be different."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not available in PATH."
  exit 1
fi

OUT_DIR="$(dirname "${OUTPUT_VCF_GZ}")"
OUT_FILE="$(basename "${OUTPUT_VCF_GZ}")"
IN_DIR="$(dirname "${INPUT_VCF_GZ}")"
IN_FILE="$(basename "${INPUT_VCF_GZ}")"

mkdir -p "${OUT_DIR}"


docker_bcftools() {
  docker run --rm \
    -u "$(id -u):$(id -g)" \
    -v "${IN_DIR}:/in:ro" \
    -v "${OUT_DIR}:/out" \
    -v "${TMP_DIR}:/tmpwork" \
    "${BCFTOOLS_IMAGE}" "$@"
}


echo "Checking whether INFO/${SOURCE_INFO_TAG} exists in the input header..."

if ! docker_bcftools bash -lc "bcftools view -h /in/${IN_FILE} | grep -q '^##INFO=<ID=${SOURCE_INFO_TAG},'"; then
  echo "ERROR: INFO/${SOURCE_INFO_TAG} was not found in the input VCF header."
  exit 1
fi

echo "Header OK."


echo "Counting input variants with INFO/${SOURCE_INFO_TAG}..."

docker_bcftools bash -lc "
bcftools query -f '%INFO/${SOURCE_INFO_TAG}\n' /in/${IN_FILE} \
| awk 'BEGIN{n=0} \$1 != \".\" && \$1 != \"\" {n++} END{print n}' \
> /tmpwork/source_tag_count.txt
"

SOURCE_TAG_COUNT="$(cat "${TMP_DIR}/source_tag_count.txt")"
echo "Variants with INFO/${SOURCE_INFO_TAG}: ${SOURCE_TAG_COUNT}"


echo "Creating RTG-ready VCF with INFO/${TARGET_INFO_TAG} copied from INFO/${SOURCE_INFO_TAG}..."

docker_bcftools bash -lc "
set -euo pipefail

HEADER_FILE=/tmpwork/header.vcf
BODY_FILE=/tmpwork/body.vcf

# Build header and inject INFO/RTG_SCORE definition if absent
bcftools view -h /in/${IN_FILE} \
| awk '
  BEGIN {added=0}
  /^##INFO=<ID=${TARGET_INFO_TAG},/ {added=1}
  /^#CHROM/ && added==0 {
    print \"##INFO=<ID=${TARGET_INFO_TAG},Number=1,Type=Float,Description=\\\"Score copied from INFO/${SOURCE_INFO_TAG} for RTG vcfeval/ROC analysis\\\">\"
  }
  {print}
' > \$HEADER_FILE

# Rewrite INFO column, replacing/adding RTG_SCORE from SOURCE_INFO_TAG
bcftools view -H /in/${IN_FILE} \
| awk '
  BEGIN {FS=OFS=\"\t\"}
  {
    n = split(\$8, info, \";\")
    src_found = 0
    src_value = \"\"
    newinfo = \"\"

    for (i = 1; i <= n; i++) {
      if (info[i] ~ /^${SOURCE_INFO_TAG}=/) {
        src_found = 1
        src_value = substr(info[i], length(\"${SOURCE_INFO_TAG}\") + 2)
      }
    }

    # Remove any pre-existing TARGET_INFO_TAG before rebuilding INFO
    for (i = 1; i <= n; i++) {
      if (info[i] !~ /^${TARGET_INFO_TAG}=/) {
        if (newinfo == \"\") {
          newinfo = info[i]
        } else {
          newinfo = newinfo \";\" info[i]
        }
      }
    }

    if (src_found && src_value != \".\" && src_value != \"\") {
      if (newinfo == \"\") {
        newinfo = \"${TARGET_INFO_TAG}=\" src_value
      } else {
        newinfo = newinfo \";${TARGET_INFO_TAG}=\" src_value
      }
    }

    \$8 = newinfo
    print
  }
' > \$BODY_FILE

cat \$HEADER_FILE \$BODY_FILE \
| bgzip -c > /out/${OUT_FILE}

tabix -f -p vcf /out/${OUT_FILE}
"


echo "Validating output..."

if [[ ! -f "${OUTPUT_VCF_GZ}" ]]; then
  echo "ERROR: Output VCF was not created."
  exit 1
fi

if [[ ! -f "${OUTPUT_VCF_GZ}.tbi" ]]; then
  echo "ERROR: Output VCF index (.tbi) was not created."
  exit 1
fi

if ! docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${OUT_DIR}:/out:ro" \
  "${BCFTOOLS_IMAGE}" \
  bash -lc "bcftools view -h /out/${OUT_FILE} | grep -q '^##INFO=<ID=${TARGET_INFO_TAG},'"; then
  echo "ERROR: INFO/${TARGET_INFO_TAG} was not found in the output header."
  exit 1
fi

echo "Checking first records with INFO/${TARGET_INFO_TAG}..."
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${OUT_DIR}:/out:ro" \
  "${BCFTOOLS_IMAGE}" \
  bash -lc "bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%INFO/${TARGET_INFO_TAG}\n' /out/${OUT_FILE} | head -n 5"

echo
echo "Done."
echo "Output VCF : ${OUTPUT_VCF_GZ}"
echo "Output TBI : ${OUTPUT_VCF_GZ}.tbi"
echo "Source tag : INFO/${SOURCE_INFO_TAG}"
echo "Target tag : INFO/${TARGET_INFO_TAG}"
