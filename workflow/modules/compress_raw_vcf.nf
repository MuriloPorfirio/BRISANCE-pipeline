process COMPRESS_RAW_VCF {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'staphb/bcftools:1.21'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/filtered/${tumor_sample}_vs_${normal_sample}" }, mode: 'symlink', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(raw_vcf)
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.raw.bgz.vcf.gz"), path("${tumor_sample}_vs_${normal_sample}.raw.bgz.vcf.gz.tbi"), emit: compressed
    tuple val(tumor_sample), val(normal_sample), path('raw_vcf_versions.txt'), emit: provenance

    script:
    """
    bcftools view --no-version -Oz \
        -o "${tumor_sample}_vs_${normal_sample}.raw.bgz.vcf.gz" \
        "${raw_vcf}"
    bcftools index -t "${tumor_sample}_vs_${normal_sample}.raw.bgz.vcf.gz"
    bcftools --version > raw_vcf_versions.txt 2>&1
    """
}
