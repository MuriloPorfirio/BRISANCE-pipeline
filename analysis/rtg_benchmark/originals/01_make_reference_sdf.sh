#!/usr/bin/env bash
set -euo pipefail



if [[ ! -f "${REFERENCE_FASTA}" ]]; then
  echo "ERROR: Reference FASTA not found:"
  echo "  ${REFERENCE_FASTA}"
  exit 1
fi

if [[ -e "${OUTPUT_SDF_DIR}" ]]; then
  echo "ERROR: Output SDF directory already exists:"
  echo "  ${OUTPUT_SDF_DIR}"
  echo "Remove it or change OUTPUT_SDF_DIR before running."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not available in PATH."
  exit 1
fi

########################################
# Resolve paths for Docker mount logic #
########################################

REF_DIR="$(dirname "${REFERENCE_FASTA}")"
REF_FILE="$(basename "${REFERENCE_FASTA}")"

OUT_PARENT="$(dirname "${OUTPUT_SDF_DIR}")"
OUT_NAME="$(basename "${OUTPUT_SDF_DIR}")"

mkdir -p "${OUT_PARENT}"

########################
# Run RTG format in Docker
########################

echo "Starting RTG SDF generation..."
echo "Reference FASTA : ${REFERENCE_FASTA}"
echo "Output SDF dir  : ${OUTPUT_SDF_DIR}"
echo "Docker image    : ${RTG_IMAGE}"
echo

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${REF_DIR}:/ref:ro" \
  -v "${OUT_PARENT}:/out" \
  "${RTG_IMAGE}" \
  rtg format \
    -o "/out/${OUT_NAME}" \
    "/ref/${REF_FILE}" \
  2>&1 | tee "${LOG_FILE}"

########################
# Post-run validation  #
########################

if [[ ! -d "${OUTPUT_SDF_DIR}" ]]; then
  echo "ERROR: RTG SDF directory was not created."
  exit 1
fi

if [[ ! -f "${OUTPUT_SDF_DIR}/sdfid.txt" ]]; then
  echo "WARNING: SDF directory exists, but sdfid.txt was not found."
  echo "Please inspect the output manually."
else
  echo
  echo "SDF successfully created:"
  echo "  ${OUTPUT_SDF_DIR}"
fi

echo
echo "Log written to:"
echo "  ${LOG_FILE}"
