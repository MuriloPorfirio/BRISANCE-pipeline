process FILTER_MUTECT_CALLS {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'broadinstitute/gatk:4.6.2.0'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/filtered/${tumor_sample}_vs_${normal_sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(raw_vcf), path(raw_index), path(mutect_stats)
    path reference
    path reference_indices
    val java_heap_gb
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.filtered.vcf.gz"), path("${tumor_sample}_vs_${normal_sample}.filtered.vcf.gz.tbi"), emit: filtered
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.filtered.vcf.gz.filteringStats.tsv"), path('filtermutectcalls_versions.txt'), path('filter_configuration.txt'), emit: provenance

    script:
    """
    mkdir -p tmp
    gatk --java-options "-Xmx${java_heap_gb}g -Djava.io.tmpdir=\$(pwd)/tmp" FilterMutectCalls \
        -V "${raw_vcf}" \
        -R "${reference}" \
        --stats "${mutect_stats}" \
        -O "${tumor_sample}_vs_${normal_sample}.filtered.vcf.gz" \
        --create-output-variant-index true

    gatk --version > filtermutectcalls_versions.txt 2>&1
    printf '%s\\n' \
        'tumor_sample=${tumor_sample}' \
        'normal_sample=${normal_sample}' \
        'input_vcf=${raw_vcf}' \
        'input_index=${raw_index}' \
        'mutect_stats=${mutect_stats}' \
        'reference=${reference}' \
        'extra_filter_arguments=none' \
        'java_heap=${java_heap_gb}g' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        > filter_configuration.txt
    """
}
