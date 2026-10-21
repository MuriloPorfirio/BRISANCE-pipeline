process SELECT_POSITIVE_TLOD {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'staphb/bcftools:1.21'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/final/${tumor_sample}_vs_${normal_sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(annotated_vcf), path(annotated_index)
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.PASS_TLOD.vcf.gz"), path("${tumor_sample}_vs_${normal_sample}.PASS_TLOD.vcf.gz.tbi"), emit: final_calls
    tuple val(tumor_sample), val(normal_sample), path('tlod_bcftools_versions.txt'), path('tlod_configuration.txt'), path('tlod_counts.tsv'), emit: provenance

    script:
    """
    bcftools view -i 'INFO/TLOD>0 && INFO/TLOD!="."' -Oz \
        -o "${tumor_sample}_vs_${normal_sample}.PASS_TLOD.vcf.gz" \
        "${annotated_vcf}"
    bcftools index -t "${tumor_sample}_vs_${normal_sample}.PASS_TLOD.vcf.gz"
    bcftools --version > tlod_bcftools_versions.txt 2>&1
    printf '%s\\n' \
        'tumor_sample=${tumor_sample}' \
        'normal_sample=${normal_sample}' \
        'input_vcf=${annotated_vcf}' \
        'input_index=${annotated_index}' \
        'selection=INFO/TLOD>0 && INFO/TLOD!="."' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        > tlod_configuration.txt
    {
        printf 'set\\tvariant_records\\n'
        printf 'annotated_PASS\\t'
        bcftools view -H "${annotated_vcf}" | wc -l
        printf 'PASS_TLOD\\t'
        bcftools view -H "${tumor_sample}_vs_${normal_sample}.PASS_TLOD.vcf.gz" | wc -l
    } > tlod_counts.tsv
    """
}
