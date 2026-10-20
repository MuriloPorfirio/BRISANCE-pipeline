#!/usr/bin/env bash
# Separate, opt-in Turing launcher. No arguments never start an analysis.
set -eo pipefail
fail() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }
case "${1:-}" in
    --check|--run) [[ $# == 1 ]] || fail 'Argumentos inesperados.' ;;
    *) printf 'Uso: bash %s --check | --run\n' "$0"; exit 2 ;;
esac
BRISANCE_MODE=$1
BRISANCE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd -- "$BRISANCE_ROOT"
BRISANCE_CONDA_SH="${BRISANCE_CONDA_SH:-/home/murilo.aguiar/miniconda3/etc/profile.d/conda.sh}"
[[ -r "$BRISANCE_CONDA_SH" ]] || fail "Conda não encontrado: $BRISANCE_CONDA_SH"
source "$BRISANCE_CONDA_SH"
conda activate brisance-nextflow
set -u
[[ -x "$CONDA_PREFIX/bin/java" ]] || fail 'Java ausente no ambiente brisance-nextflow.'
BRISANCE_JAVA_BIN=$(readlink -f -- "$CONDA_PREFIX/bin/java")
export NXF_JAVA_HOME="${BRISANCE_JAVA_BIN%/bin/java}"
export JAVA_HOME="$NXF_JAVA_HOME"
export JAVA_CMD="$NXF_JAVA_HOME/bin/java"
export PYTHONUNBUFFERED=1
BRISANCE_NF="$BRISANCE_ROOT/nextflow-26.04.6-dist"
BRISANCE_HELPER="$BRISANCE_ROOT/workflow/hg008_full_run.py"
[[ -x "$BRISANCE_NF" && -f "$BRISANCE_HELPER" ]] || fail 'Nextflow/auxiliar do launcher ausente.'
for BRISANCE_TOOL in python3 docker nvidia-smi flock tee df; do
    command -v "$BRISANCE_TOOL" >/dev/null || fail "Ferramenta ausente: $BRISANCE_TOOL"
done

if [[ "$BRISANCE_MODE" == '--check' ]]; then
    printf 'Ambiente Conda: %s\nJava selecionado: %s\n' "$CONDA_PREFIX" "$JAVA_CMD"
    "$JAVA_CMD" -version
    "$BRISANCE_NF" -version
    exec python3 -B "$BRISANCE_HELPER" --check
fi

[[ -n "${STY:-}" ]] || fail 'Abra uma screen antes de iniciar: screen -S brisance-hg008100'
# Validate the root and fixed output destinations before creating the log/lock.
python3 -B "$BRISANCE_HELPER" --check-paths
BRISANCE_REPORT_ROOT="$BRISANCE_ROOT/reports/hg008-100pct"
mkdir -p -- "$BRISANCE_REPORT_ROOT"
[[ ! -L "$BRISANCE_REPORT_ROOT/launcher.lock" ]] || fail 'Lock simbólico não permitido.'
exec 9> "$BRISANCE_REPORT_ROOT/launcher.lock"
flock -n 9 || fail 'O launcher dos 100% já está em execução.'
BRISANCE_REPORTS=$(mktemp -d "$BRISANCE_REPORT_ROOT/execution-XXXXXX")
exec > >(tee "$BRISANCE_REPORTS/console.log") 2>&1
printf 'Relatórios: %s\nAmbiente Conda: %s\nJava selecionado: %s\n' \
    "$BRISANCE_REPORTS" "$CONDA_PREFIX" "$JAVA_CMD"
printf 'Início UTC do launcher: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
"$JAVA_CMD" -version
"$BRISANCE_NF" -version
set +e
python3 -B "$BRISANCE_HELPER" --run --reports "$BRISANCE_REPORTS"
BRISANCE_RUN_STATUS=$?
set -e
printf '\nFim UTC do launcher: %s\nCódigo de saída do launcher: %s\nRelatórios preservados: %s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$BRISANCE_RUN_STATUS" "$BRISANCE_REPORTS"
df -h -- "$BRISANCE_ROOT" || true
df -B1 -- "$BRISANCE_ROOT" || true
exit "$BRISANCE_RUN_STATUS"
