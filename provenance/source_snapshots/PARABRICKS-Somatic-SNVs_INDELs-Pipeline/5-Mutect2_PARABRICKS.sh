time docker run \

--gpus '"device=7"' \
# Allow the container to access only GPU 7 on the host.
# Alternatively, use --gpus all to allow all GPUs.

--user 1006:1006 \
#User ID / Group ID

--workdir /workdir \
# Set the default working directory inside the container, DO NOT CHANGE.

--rm \
# Automatically remove the container after execution finishes.

--volume /caminho/para/seus/bams:/workdir \
# Bind-mount the host directory containing your BAM input files into /workdir inside the container.

--volume /caminho/para/salvar/output:/outputdir \
# Bind-mount the host directory where you want output files (like the final VCF) to appear.

--volume /caminho/para/genome_reference:/reference \
# Bind-mount the host directory containing the genome reference FASTA and all necessary index files (.fai, .dict, etc.).

nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1 \
# Specify the Docker image containing Parabricks tools.

pbrun mutectcaller \
# Launch the MutectCaller tool.

--num-htvc-threads 10 \
#Specify the number of threads after this option. If not set, the process will run with the default of 5 threads.

--ref /reference/blablabla.fa \
# Path to the genome reference FASTA file inside the container.

--in-tumor-bam /workdir/SRR7890824-WGS_FD_T.bam \
# Path to the tumor sample BAM file.

--in-normal-bam /workdir/SRR7890827-WGS_FD_N.bam \
# Path to the normal sample BAM file.
# If you don't have a normal BAM, omit this line.

--in-tumor-recal-file /workdir/RR7890824-WGS_FD_T_BQSR_REPORT.txt \
# Path to the tumor BQSR report file.
# This file is typically generated during fq2bam step.
# If the file is in another directory, create a dedicated --volume for it.

--in-normal-recal-file /workdir/SRR7890827-WGS_FD_N_BQSR_REPORT.txt \
# Path to the normal BQSR report file.
# If you don't have a normal sample, omit this line.

--out-vcf /outputdir/SRR7890824-SRR7890827-WGS_FD.vcf \
# Full path and filename for the output VCF.
# Replace the name as needed, but keep the ".vcf" extension.

--tumor-name sm_SRR7890824 \
# Tumor sample name for the VCF header.
# Must match exactly the SM tag found in the tumor BAM's Read Group.
# Use: docker run --rm -v $(pwd):/data staphb/samtools samtools view -H /data/IDUDI0031_aligned.bam | grep '^@RG'

--normal-name sm_SRR7890827
# Normal sample name for the VCF header.
# Must match the SM tag in the normal BAM file.
# If you don't have a normal sample, omit this line.

2>&1 | tee /caminho/para/salvar/output/mutectcaller_run.log
# Generates a log with detailed processing information.
# Specify both the log file name and its output location
# (it’s recommended to use the same directory as the output files to avoid errors).






