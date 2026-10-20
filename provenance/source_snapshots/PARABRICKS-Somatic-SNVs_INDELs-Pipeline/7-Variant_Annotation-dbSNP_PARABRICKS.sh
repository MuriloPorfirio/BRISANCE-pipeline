docker run --rm --gpus all \
  -u $(id -u):$(id -g) \
  -v /home/murilo.aguiar/raid-murilo:/workdir \
  -v /home/murilo.aguiar/raid-murilo/anotados:/outputdir \
  --workdir /workdir \
  nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1 \
  pbrun dbsnp \
    --in-vcf /workdir/VCFs/paciente01_raw.vcf.gz \
    --in-dbsnp-file /workdir/Genomas_de_referencia/humano/VCF-para-dbSNP-anotacao/dbsnp_hg38.vcf.gz \
    --out-vcf /outputdir/paciente01_annotado_dbsnp.vcf.gz
