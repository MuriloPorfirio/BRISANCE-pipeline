#!/usr/bin/env bash
# Turing-specific launcher for the integrated HG008 20% functional test.
# Usage: ./workflow/run_hg008_20pct.sh [--check]
# --check verifies Conda/Java/Nextflow only. The default runs all stages.
set -eo pipefail

fail() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

if [[ $# -gt 1 || ( $# -eq 1 && "${1:-}" != '--check' ) ]]; then
    fail 'Uso: ./workflow/run_hg008_20pct.sh [--check]'
fi
BRISANCE_CHECK_ONLY=false
[[ "${1:-}" == '--check' ]] && BRISANCE_CHECK_ONLY=true

BRISANCE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd -- "$BRISANCE_ROOT"
BRISANCE_CONDA_SH="${BRISANCE_CONDA_SH:-/home/murilo.aguiar/miniconda3/etc/profile.d/conda.sh}"
[[ -r "$BRISANCE_CONDA_SH" ]] || fail "Conda não encontrado: $BRISANCE_CONDA_SH"

# Conda initialization/activation is done before nounset: activation scripts
# may inspect optional, unset environment variables.
source "$BRISANCE_CONDA_SH"
conda activate brisance-nextflow
set -u

[[ -x "$CONDA_PREFIX/bin/java" ]] || fail 'Java ausente no ambiente brisance-nextflow.'
BRISANCE_JAVA_BIN=$(readlink -f -- "$CONDA_PREFIX/bin/java")
export NXF_JAVA_HOME="${BRISANCE_JAVA_BIN%/bin/java}"
export JAVA_HOME="$NXF_JAVA_HOME"
export JAVA_CMD="$NXF_JAVA_HOME/bin/java"

BRISANCE_NF="$BRISANCE_ROOT/nextflow-26.04.6-dist"
[[ -x "$BRISANCE_NF" ]] || fail "Nextflow não encontrado/executável: $BRISANCE_NF"

if "$BRISANCE_CHECK_ONLY"; then
    printf 'Ambiente Conda: %s\nJava selecionado: %s\n' "$CONDA_PREFIX" "$JAVA_CMD"
    "$JAVA_CMD" -version
    "$BRISANCE_NF" -version
    printf '\nChecagem encerrada; nenhum processamento iniciado.\n'
    exit 0
fi

[[ -n "${STY:-}" ]] || fail 'Abra uma screen antes de iniciar: screen -S brisance-hg00820'
for BRISANCE_TOOL in flock tar sha256sum tee; do
    command -v "$BRISANCE_TOOL" >/dev/null || fail "Ferramenta necessária ausente: $BRISANCE_TOOL"
done

BRISANCE_DATASET='hg008-20pct-m_8ryr9u'
BRISANCE_INPUT="data/subsample/$BRISANCE_DATASET/samplesheet.csv"
BRISANCE_MANIFEST="data/subsample/$BRISANCE_DATASET/manifest.json"
BRISANCE_REPORT_ROOT="reports/$BRISANCE_DATASET"
BRISANCE_RESULTS="results/$BRISANCE_DATASET"
BRISANCE_WORK="work/$BRISANCE_DATASET"
[[ -s "$BRISANCE_INPUT" && -s "$BRISANCE_MANIFEST" ]] || fail 'Samplesheet/manifesto da subamostra ausente ou vazio.'

mkdir -p -- "$BRISANCE_REPORT_ROOT"
exec 9> "$BRISANCE_REPORT_ROOT/launcher.lock"
flock -n 9 || fail 'Este launcher já está em execução. Não será iniciada uma segunda análise.'

# Do not overwrite previous scientific outputs or silently rerun a large job.
# A failed/partial scientific run should be reviewed and resumed separately.
[[ ! -e "$BRISANCE_RESULTS" && ! -L "$BRISANCE_RESULTS" && ! -e "$BRISANCE_WORK" && ! -L "$BRISANCE_WORK" ]] ||
    fail 'Já existe results/work deste teste. Nada foi apagado; precisamos avaliar uma retomada, não iniciar do zero.'

BRISANCE_REPORTS=$(mktemp -d "$BRISANCE_REPORT_ROOT/execution-XXXXXX")
exec > >(tee "$BRISANCE_REPORTS/console.log") 2>&1
printf 'Relatórios: %s/%s\n' "$BRISANCE_ROOT" "$BRISANCE_REPORTS"
printf 'Dados: %s\nResultados: %s\nTrabalho: %s\n' "$BRISANCE_INPUT" "$BRISANCE_RESULTS" "$BRISANCE_WORK"
printf 'Ambiente Conda: %s\nJava selecionado: %s\n' "$CONDA_PREFIX" "$JAVA_CMD"
printf 'Início UTC: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
"$JAVA_CMD" -version
"$BRISANCE_NF" -version

tar -czf "$BRISANCE_REPORTS/execution-inputs.tar.gz" -- \
    workflow "$BRISANCE_INPUT" "$BRISANCE_MANIFEST"
sha256sum "$BRISANCE_NF" > "$BRISANCE_REPORTS/nextflow.sha256"
printf 'GPUs configuradas: alinhamento 7,6,5; BQSR 7; chamada 7,6. Este launcher não reserva GPUs.\n'

set +e
"$BRISANCE_NF" \
    -log "$BRISANCE_REPORTS/nextflow.log" \
    run workflow/main.nf \
    --mode finalize \
    --input "$BRISANCE_INPUT" \
    --outdir "$BRISANCE_RESULTS/stage1" \
    --gpu_devices 7,6,5 \
    --bqsr_gpu_device 7 \
    --caller_gpu_devices 7,6 \
    --vep_cache_dir /home/leticia.santos/vep_data \
    -work-dir "$BRISANCE_WORK" \
    -with-trace "$BRISANCE_REPORTS/trace.tsv" \
    -with-report "$BRISANCE_REPORTS/report.html" \
    -with-timeline "$BRISANCE_REPORTS/timeline.html" \
    -ansi-log false
BRISANCE_RUN_STATUS=$?
set -e
printf '\nFim UTC: %s\nCódigo de saída do Nextflow: %s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$BRISANCE_RUN_STATUS"
printf 'Relatórios preservados: %s/%s\n' "$BRISANCE_ROOT" "$BRISANCE_REPORTS"
exit "$BRISANCE_RUN_STATUS"
