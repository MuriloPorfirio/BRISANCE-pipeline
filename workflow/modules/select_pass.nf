process SELECT_PASS {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'staphb/bcftools:1.21'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/filtered/${tumor_sample}_vs_${normal_sample}" }, mode: 'symlink', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(filtered_vcf), path(filtered_index)
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.PASS.vcf.gz"), path("${tumor_sample}_vs_${normal_sample}.PASS.vcf.gz.tbi"), emit: pass_calls
    tuple val(tumor_sample), val(normal_sample), path('pass_vcf_versions.txt'), path('pass_counts.tsv'), emit: provenance

    script:
    """
    bcftools view -f PASS -Oz \
        -o "${tumor_sample}_vs_${normal_sample}.PASS.vcf.gz" \
        "${filtered_vcf}"
    bcftools index -t "${tumor_sample}_vs_${normal_sample}.PASS.vcf.gz"
    bcftools --version > pass_vcf_versions.txt 2>&1
    {
        printf 'set\\tvariant_records\\n'
        printf 'all_filtered\\t'
        bcftools view -H "${filtered_vcf}" | wc -l
        printf 'PASS\\t'
        bcftools view -H "${tumor_sample}_vs_${normal_sample}.PASS.vcf.gz" | wc -l
    } > pass_counts.tsv
    """
}
