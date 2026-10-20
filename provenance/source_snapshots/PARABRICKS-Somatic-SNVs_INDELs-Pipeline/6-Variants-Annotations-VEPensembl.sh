#!/bin/bash
set -euo pipefail

docker run --rm \
  -u $(id -u):$(id -g) \
  -v /home/murilo.aguiar/raid-murilo:/workdir \
  ensemblorg/ensembl-vep:latest \
  vep \
    -i /workdir/VCFs/meu_sample.vcf \
    -o /workdir/VCFs/meu_sample_annotado.vep.txt \
    --species homo_sapiens \
    --force_overwrite
