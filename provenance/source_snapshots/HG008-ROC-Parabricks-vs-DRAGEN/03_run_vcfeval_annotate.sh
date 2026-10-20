#!/usr/bin/env bash
set -euo pipefail


# Root directory mounted into the container as /workdir
WORKDIR_ROOT="/raid/biomafia/murilo.aguiar"

# RTG container used in the final working flow
RTG_IMAGE="ghcr.io/uclahs-cds/rtg-tools:dev"

# Baseline VCF (DRAGEN)
BASELINE_VCF="${WORKDIR_ROOT}/Arquivos_Cancer_in_a_Bottle/vcf_HG008_original-variant-calling-output/dragen_4.2.4_HG008-mosaic_tumor.hard-filtered.vcf.gz"

# Calls VCF prepared for RTG (contains INFO.RTG_SCORE)
CALLS_VCF="${WORKDIR_ROOT}/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/6-Anotacao-de-Variantes-PASS/HG008-IDUDI0031_somatico_vs_germinativo.PASS_RTG.vcf.gz"

# RTG reference SDF
REFERENCE_SDF="${WORKDIR_ROOT}/Genomas_de_referencia/humano/Genoma_Referencia_Cancer_in_a_Bottle/ref_sdf_rtg"

# Output directory
OUTPUT_DIR="${WORKDIR_ROOT}/Processos/PROCESSOS-RELACIONADOS-AO-CANCER-IN-A-BOTTLE/15-10-2025_GIAB_tumor-normal/7-RTG-Results/vcfeval_annot_DEV"

# Sample mapping: baseline_sample,calls_sample
SAMPLE_MAP="HG008-T-mosaic,somatico"

# ROC score field already added to the calls VCF
SCORE_FIELD="INFO.RTG_SCORE"

# Threads
THREADS="8"


if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not available in PATH."
  exit 1
fi

for f in "${BASELINE_VCF}" "${CALLS_VCF}"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: input file not found:"
    echo "  ${f}"
    exit 1
  fi
done

if [[ ! -d "${REFERENCE_SDF}" ]]; then
  echo "ERROR: reference SDF directory not found:"
  echo "  ${REFERENCE_SDF}"
  exit 1
fi

if [[ -e "${OUTPUT_DIR}" ]]; then
  echo "ERROR: output directory already exists:"
  echo "  ${OUTPUT_DIR}"
  echo "Remove it or change OUTPUT_DIR before running."
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"


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
REFERENCE_SDF_C="$(to_container_path "${REFERENCE_SDF}")"
OUTPUT_DIR_C="$(to_container_path "${OUTPUT_DIR}")"


echo "Running RTG vcfeval in annotate mode..."
echo "Container      : ${RTG_IMAGE}"
echo "Baseline VCF   : ${BASELINE_VCF}"
echo "Calls VCF      : ${CALLS_VCF}"
echo "Reference SDF  : ${REFERENCE_SDF}"
echo "Output dir     : ${OUTPUT_DIR}"
echo "Sample map     : ${SAMPLE_MAP}"
echo "Score field    : ${SCORE_FIELD}"
echo "Threads        : ${THREADS}"
echo

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${WORKDIR_ROOT}:/workdir" \
  "${RTG_IMAGE}" \
  rtg vcfeval \
    -b "${BASELINE_VCF_C}" \
    -c "${CALLS_VCF_C}" \
    -t "${REFERENCE_SDF_C}" \
    -o "${OUTPUT_DIR_C}" \
    --sample "${SAMPLE_MAP}" \
    -m annotate \
    --vcf-score-field "${SCORE_FIELD}" \
    --squash-ploidy \
    --ref-overlap \
    --threads "${THREADS}" \
  2>&1 | tee "${OUTPUT_DIR}/vcfeval.run.log"



echo
echo "Checking expected outputs..."

expected_files=(
  "${OUTPUT_DIR}/baseline.vcf.gz"
  "${OUTPUT_DIR}/baseline.vcf.gz.tbi"
  "${OUTPUT_DIR}/calls.vcf.gz"
  "${OUTPUT_DIR}/calls.vcf.gz.tbi"
  "${OUTPUT_DIR}/summary.txt"
  "${OUTPUT_DIR}/vcfeval.log"
)

for f in "${expected_files[@]}"; do
  if [[ -e "${f}" ]]; then
    echo "[OK] ${f}"
  else
    echo "[MISSING] ${f}"
  fi
done

echo
echo "Done."
echo "Main output directory:"
echo "  ${OUTPUT_DIR}"
