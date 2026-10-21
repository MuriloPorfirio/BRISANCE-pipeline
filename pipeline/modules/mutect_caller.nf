process MUTECT_CALLER {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    container 'nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1'
    containerOptions { "--gpus '\"device=${options.devices.join(',')}\"' --cpus ${task.cpus}" }
    publishDir { "${output_dir}/variants/${tumor_sample}_vs_${normal_sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), path(tumor_bam), path(tumor_index), val(normal_sample), path(normal_bam), path(normal_index)
    path reference
    path reference_indices
    val options
    val output_dir

    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.vcf"), path("${tumor_sample}_vs_${normal_sample}.vcf.stats"), emit: calls
    tuple val(tumor_sample), val(normal_sample), path('mutectcaller_versions.txt'), path('run_configuration.txt'), emit: provenance

    script:
    """
    mkdir -p tmp
    pbrun mutectcaller \
        --num-htvc-threads ${options.htvc_threads} \
        --ref "${reference}" \
        --in-tumor-bam "${tumor_bam}" \
        --in-normal-bam "${normal_bam}" \
        --out-vcf "${tumor_sample}_vs_${normal_sample}.vcf" \
        --tumor-name "${tumor_sample}" \
        --normal-name "${normal_sample}" \
        --tmp-dir "\$(pwd)/tmp" \
        --num-gpus ${options.devices.size()}

    pbrun mutectcaller --version > mutectcaller_versions.txt 2>&1
    printf '%s\\n' \
        'tumor_sample=${tumor_sample}' \
        'normal_sample=${normal_sample}' \
        'tumor_bam=${tumor_bam}' \
        'tumor_index=${tumor_index}' \
        'normal_bam=${normal_bam}' \
        'normal_index=${normal_index}' \
        'gpu_devices=${options.devices.join(',')}' \
        'num_gpus=${options.devices.size()}' \
        'num_htvc_threads=${options.htvc_threads}' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        > run_configuration.txt
    """
}
