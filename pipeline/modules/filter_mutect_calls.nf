process FILTER_MUTECT_CALLS {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'broadinstitute/gatk:4.6.2.0'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/filtered/${tumor_sample}_vs_${normal_sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(raw_vcf), path(raw_index), path(mutect_stats)
    path reference
    path reference_indices
    path priors_files, stageAs: 'orientation/*'
    path contamination_files, stageAs: 'contamination/*'
    path segmentation_files, stageAs: 'segmentation/*'
    val java_heap_gb
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.filtered.vcf.gz"), path("${tumor_sample}_vs_${normal_sample}.filtered.vcf.gz.tbi"), emit: filtered
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.filtered.vcf.gz.filteringStats.tsv"), path('filtermutectcalls_versions.txt'), path('filter_configuration.txt'), emit: provenance

    script:
    def priors = priors_files instanceof List ? (priors_files ? priors_files[0] : null) : priors_files
    def contamination = contamination_files instanceof List ? (contamination_files ? contamination_files[0] : null) : contamination_files
    def segmentation = segmentation_files instanceof List ? (segmentation_files ? segmentation_files[0] : null) : segmentation_files
    def priorsArgs = priors ? "--orientation-bias-artifact-priors \"${priors}\"" : ''
    def contaminationArgs = contamination ? "--contamination-table \"${contamination}\"" : ''
    def segmentationArgs = segmentation ? "--tumor-segmentation \"${segmentation}\"" : ''
    """
    mkdir -p tmp
    gatk --java-options "-Xmx${java_heap_gb}g -Djava.io.tmpdir=\$(pwd)/tmp" FilterMutectCalls \
        -V "${raw_vcf}" \
        -R "${reference}" \
        --stats "${mutect_stats}" \
        ${priorsArgs} \
        ${contaminationArgs} \
        ${segmentationArgs} \
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
        'orientation_priors=${priors ?: 'off'}' \
        'contamination_table=${contamination ?: 'off'}' \
        'tumor_segmentation=${segmentation ?: 'off'}' \
        'java_heap=${java_heap_gb}g' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        > filter_configuration.txt
    """
}
