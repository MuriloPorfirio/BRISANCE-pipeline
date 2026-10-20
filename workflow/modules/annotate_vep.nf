process ANNOTATE_VEP {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'ensemblorg/ensembl-vep:release_113.0'
    containerOptions { "--mount 'type=bind,source=${options.cache_dir},target=/cache,readonly' --cpus ${task.cpus}" }
    publishDir { "${output_dir}/annotated/${tumor_sample}_vs_${normal_sample}" }, mode: 'symlink', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(pass_vcf), path(pass_index)
    path cache_info
    val options
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.PASS_annotado.vep.vcf.gz"), emit: annotated
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.PASS_annotado.vep.stats.html"), path('vep_versions.txt'), path('vep_cache_info.txt'), path('annotation_configuration.txt'), emit: provenance
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.PASS_annotado.vep.vcf.gz_warnings.txt"), optional: true, emit: warnings

    script:
    """
    vep \
        --assembly GRCh38 \
        --cache --cache_version 113 \
        --compress_output bgzip \
        --dir_cache /cache \
        --dir_plugins /cache/plugins \
        --everything --force_overwrite --fork 8 \
        --format vcf \
        --input_file "${pass_vcf}" \
        --offline \
        --output_file "${tumor_sample}_vs_${normal_sample}.PASS_annotado.vep.vcf.gz" \
        --vcf \
        --stats_file "${tumor_sample}_vs_${normal_sample}.PASS_annotado.vep.stats.html"

    vep --help > vep_versions.txt 2>&1
    cp "${cache_info}" vep_cache_info.txt
    printf '%s\\n' \
        'tumor_sample=${tumor_sample}' \
        'normal_sample=${normal_sample}' \
        'input_vcf=${pass_vcf}' \
        'input_index=${pass_index}' \
        'cache_host=${options.cache_dir}' \
        'cache_container=/cache' \
        'cache_version=113' \
        'assembly=GRCh38' \
        'cache_read_only=true' \
        'fork=8' \
        'plugins_requested=none' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        > annotation_configuration.txt
    """
}
