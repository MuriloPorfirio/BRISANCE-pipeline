#!/bin/bash
# Trim Galore via Docker (biowardrobe2/trimgalore:v0.4.4)
# Input: paired files R1/R2

set -euo pipefail  # stop the script if there is any error

##### CONFIGURATION: EDIT HERE #####
INPUT_DIR="/path/to/input"
OUTPUT_PARENT="/path/to/output"
FILES=("sample1_R1.fastq.gz" "sample1_R2.fastq.gz"
       "sample2_R1.fastq.gz" "sample2_R2.fastq.gz")
QUALITY=20        # Phred cutoff for trimming read ends (Q20 ~ 99% accuracy)
MIN_LENGTH=20     # Throw away reads shorter than 20 bases after trimming
ADAPTER_TYPE="auto"   # "illumina" | "nextera" | "auto" (auto = default detection)
RUN_FASTQC="yes"      # "yes" to run FastQC; "no" to skip FastQC
CUSTOM_UID="$(id -u)" # UID of the user running the script
CUSTOM_GID="$(id -g)" # GID of the user running the script
RAM=8                 # Limit container RAM (GB) and set FastQC Java memory (not a Trim Galore flag)

##### NO NEED TO CHANGE ANYTHING BELOW #####

# Choose adapter type (Trim Galore v0.4.4 options)
case "$ADAPTER_TYPE" in
  illumina) ADAPTER_OPTION="--illumina" ;;
  nextera)  ADAPTER_OPTION="--nextera"  ;;
  *)        ADAPTER_OPTION="" ;;
esac

# Enable FastQC if requested
if [[ "$RUN_FASTQC" == "yes" ]]; then
  FASTQC_OPTION="--fastqc"
  FASTQC_ARGS=""
else
  FASTQC_OPTION=""
  FASTQC_ARGS=""
fi

# Prepare output folder: trimmed fastq files, quality reports and log.
# A subfolder will be created inside $OUTPUT_PARENT, named with date+time.
TIMESTAMP=$(date +"%d-%m-%Y_%Hh%Mm")
OUTPUT_DIR="$OUTPUT_PARENT/1-PARABRICKS_trimmed_files_$TIMESTAMP"
mkdir -p "$OUTPUT_DIR"
LOG_FILE="$OUTPUT_DIR/trimming_log_$(date +"%Y-%m-%d_%H%M%S").log"

echo "Starting trimming..." | tee -a "$LOG_FILE"

# Basic validations to avoid common errors
# 1) Check if the file list has an even number (R1/R2 pairs)
if (( ${#FILES[@]} % 2 != 0 )); then
  echo "ERROR: FILES list must contain an even number of items (pairs R1/R2)." | tee -a "$LOG_FILE"
  exit 1
fi

# 2) Check if all files exist
for f in "${FILES[@]}"; do
  if [[ ! -f "$INPUT_DIR/$f" ]]; then
    echo "ERROR: File not found: $INPUT_DIR/$f" | tee -a "$LOG_FILE"
    exit 1
  fi
done

START_TIME=$(date +%s)

# Process two files at a time (R1 and R2 from the same sample).
# Show which files are being processed and run Trim Galore on them.
i=0 # i=0 means we start with the first files in the list
while [[ $i -lt ${#FILES[@]} ]]; do
  R1="${FILES[$i]}"
  R2="${FILES[$((i+1))]}"
  echo "Processing: $R1 and $R2" | tee -a "$LOG_FILE"

  # Run a temporary Docker container (--rm deletes it after finishing)
  # Use the same user/group IDs so the output files are not owned by root
  # Limit container RAM and set Java memory for FastQC
  # Mount input folder as /data (read-only) and output folder as /output
  # Inside the container run trim_galore in paired-end mode
  set +e
  docker run --rm \
    --user "${CUSTOM_UID}:${CUSTOM_GID}" \
    --memory "${RAM}g" \
    -e _JAVA_OPTIONS="-Xmx${RAM}g" \
    -v "$INPUT_DIR":/data:ro \
    -v "$OUTPUT_DIR":/output \
    biowardrobe2/trimgalore:v0.4.4 \
    trim_galore --paired \
      --quality "$QUALITY" \
      --length "$MIN_LENGTH" \
      $ADAPTER_OPTION \
      $FASTQC_OPTION \
      $FASTQC_ARGS \
      -o /output \
      "/data/$R1" "/data/$R2" \
    2>&1 | tee -a "$LOG_FILE"
  status=${PIPESTATUS[0]}
  set -e

  # Check if it failed or succeeded
  if [[ $status -ne 0 ]]; then
    echo "Error while processing $R1 and $R2" | tee -a "$LOG_FILE"
  else
    echo "Finished: $R1 and $R2" | tee -a "$LOG_FILE"
  fi

  i=$((i + 2)) # move to the next pair
done

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo "Trimming finished." | tee -a "$LOG_FILE"
echo "Total time: ${TOTAL_TIME}s" | tee -a "$LOG_FILE"
echo "Results saved in: $OUTPUT_DIR"
echo "Log file: $LOG_FILE"
