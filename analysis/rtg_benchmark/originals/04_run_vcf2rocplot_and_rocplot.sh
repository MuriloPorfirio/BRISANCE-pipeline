#!/usr/bin/env bash
set -euo pipefail


# Root directory mounted into the container as /workdir
WORKDIR_ROOT="/raid/biomafia/murilo.aguiar"

# RTG container used in the final working flow
RTG_IMAGE="ghcr.io/uclahs-cds/rtg-tools:dev"

# vcfeval output directory from script 03
VCFEVAL_DIR="${WORKDIR_ROOT}/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/7-RTG-Results/vcfeval_annot_DEV"

# Score field used in ROC generation
SCORE_FIELD="INFO.RTG_SCORE"

# Derived paths
BASELINE_VCF="${VCFEVAL_DIR}/baseline.vcf.gz"
CALLS_VCF="${VCFEVAL_DIR}/calls.vcf.gz"
ROC_DIR="${VCFEVAL_DIR}/rocdata"
WEIGHTED_ROC="${ROC_DIR}/weighted_roc.tsv.gz"
ROC_PNG="${VCFEVAL_DIR}/roc.png"


if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not available in PATH."
  exit 1
fi

for f in "${BASELINE_VCF}" "${CALLS_VCF}"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: required input file not found:"
    echo "  ${f}"
    exit 1
  fi
done

mkdir -p "${ROC_DIR}"


to_container_path() {
  local host_path="$1"
  if [[ "${host_path}" != "${WORKDIR_ROOT}"* ]]; then
    echo "ERROR: path is outside WORKDIR_ROOT and cannot be mapped cleanly:"
    echo "  ${host_path}"
    exit 1
  fi
  echo "/workdir${host_path#${WORKDIR_ROOT}}"
}

BASELINE_VCF_C="$(to_container_path "${BASELINE_VCF}")"
CALLS_VCF_C="$(to_container_path "${CALLS_VCF}")"
ROC_DIR_C="$(to_container_path "${ROC_DIR}")"
WEIGHTED_ROC_C="$(to_container_path "${WEIGHTED_ROC}")"
ROC_PNG_C="$(to_container_path "${ROC_PNG}")"


echo "Generating ROC TSV outputs with rtg vcf2rocplot..."
echo "Container     : ${RTG_IMAGE}"
echo "vcfeval dir   : ${VCFEVAL_DIR}"
echo "Baseline VCF  : ${BASELINE_VCF}"
echo "Calls VCF     : ${CALLS_VCF}"
echo "ROC dir       : ${ROC_DIR}"
echo "Score field   : ${SCORE_FIELD}"
echo

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${WORKDIR_ROOT}:/workdir" \
  "${RTG_IMAGE}" \
  rtg vcf2rocplot \
    -o "${ROC_DIR_C}" \
    -f "${SCORE_FIELD}" \
    "${BASELINE_VCF_C}" \
    "${CALLS_VCF_C}" \
  2>&1 | tee "${ROC_DIR}/vcf2rocplot.run.log"


echo
echo "Generating default ROC PNG with rtg rocplot..."

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${WORKDIR_ROOT}:/workdir" \
  "${RTG_IMAGE}" \
  rtg rocplot \
    "${WEIGHTED_ROC_C}" \
    --png "${ROC_PNG_C}" \
  2>&1 | tee "${VCFEVAL_DIR}/rocplot.run.log"


echo
echo "Checking expected outputs..."

expected_files=(
  "${ROC_DIR}/weighted_roc.tsv.gz"
  "${ROC_DIR}/summary.txt"
  "${ROC_DIR}/vcf2rocplot.log"
  "${ROC_PNG}"
)

for f in "${expected_files[@]}"; do
  if [[ -e "${f}" ]]; then
    echo "[OK] ${f}"
  else
    echo "[MISSING] ${f}"
  fi
done

echo
echo "Preview of weighted_roc.tsv.gz header:"
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${WORKDIR_ROOT}:/workdir" \
  "${RTG_IMAGE}" \
  bash -lc "gzip -dc '${WEIGHTED_ROC_C}' | head -n 8" || true

echo
echo "Done."
echo "ROC TSV directory:"
echo "  ${ROC_DIR}"
echo
echo "Default ROC PNG:"
echo "  ${ROC_PNG}"
