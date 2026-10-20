time docker run --rm --gpus device=7 \
  --volume /home/murilo.aguiar/raid-murilo:/workdir \
  --volume /home/murilo.aguiar/raid-murilo/Processos/06-08-2025-Fastq2bam_output_EXOMAS-LETICIA-FERRO:/outputdir \
  --workdir /workdir \
  nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1 \
  pbrun fq2bam \
  --ref /workdir/Genomas_de_referencia/humano/Genoma_Referencia_Cancer_in_a_Bottle/GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta \
  --in-fq /workdir/Processos/Fastq_Trimados_11-07-2025/HJVHNDSX7-1-IDUDI0031_S12_L001_R1_001_val_1.fq.gz \
          /workdir/Processos/Fastq_Trimados_11-07-2025/HJVHNDSX7-1-IDUDI0031_S12_L001_R2_001_val_2.fq.gz \
  --in-fq /workdir/Processos/Fastq_Trimados_11-07-2025/HJVHNDSX7-1-IDUDI0031_S12_L002_R1_001_val_1.fq.gz \
          /workdir/Processos/Fastq_Trimados_11-07-2025/HJVHNDSX7-1-IDUDI0031_S12_L002_R2_001_val_2.fq.gz \
  --in-fq /workdir/Processos/Fastq_Trimados_11-07-2025/HJVHNDSX7-1-IDUDI0031_S12_L003_R1_001_val_1.fq.gz \
          /workdir/Processos/Fastq_Trimados_11-07-2025/HJVHNDSX7-1-IDUDI0031_S12_L003_R2_001_val_2.fq.gz \
  --knownSites /workdir/Genomas_de_referencia/humano/variantes_conhecidas_para_BaseRecalibrator-ApplyBQSR/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
  --knownSites /workdir/Genomas_de_referencia/humano/variantes_conhecidas_para_BaseRecalibrator-ApplyBQSR/Homo_sapiens_assembly38.known_indels.vcf.gz \
  --knownSites /workdir/Genomas_de_referencia/humano/variantes_conhecidas_para_BaseRecalibrator-ApplyBQSR/1000G_phase1.snps.high_confidence.hg38.vcf.gz \
  --out-bam /outputdir/HJVHNDSX7-1-IDUDI0031.bam \
  --out-recal-file /outputdir/HJVHNDSX7-1-IDUDI0031.recal.table \
  --out-duplicate-metrics /outputdir/HJVHNDSX7-1-IDUDI0031.dup_metrics.txt \
  --gpusort --gpuwrite
