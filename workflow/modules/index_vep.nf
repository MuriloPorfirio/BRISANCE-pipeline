process INDEX_VEP {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'staphb/bcftools:1.21'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/annotated/${tumor_sample}_vs_${normal_sample}" }, mode: 'symlink', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(annotated_vcf), path(pass_vcf)
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${annotated_vcf}.tbi"), emit: indices
    tuple val(tumor_sample), val(normal_sample), path('annotation_bcftools_versions.txt'), path('annotation_counts.tsv'), emit: provenance

    script:
    """
    bcftools view -h "${annotated_vcf}" |
        awk '/^##INFO=<ID=CSQ,/ {found=1} END {if (!found) {print "Missing VEP CSQ header" > "/dev/stderr"; exit 1}}'
    bcftools index -t "${annotated_vcf}"
    bcftools --version > annotation_bcftools_versions.txt 2>&1
    {
        printf 'set\\tvariant_records\\n'
        printf 'PASS_input\\t'
        bcftools view -H "${pass_vcf}" | wc -l
        printf 'VEP_output\\t'
        bcftools view -H "${annotated_vcf}" | wc -l
    } > annotation_counts.tsv
    """
}
