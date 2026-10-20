process APPLY_BQSR {
    tag { "${sample}:${role}" }
    container 'nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1'
    containerOptions { "--gpus device=${options.device} --cpus ${task.cpus}" }
    publishDir { "${output_dir}/recalibrated/${sample}" }, mode: 'symlink', overwrite: false, failOnError: true

    input:
    tuple val(sample), val(role), path(bam), path(bam_index), path(recal_table)
    path reference
    path reference_indices
    val options
    val output_dir

    output:
    tuple val(sample), val(role), path("${sample}.bqsr.bam"), emit: recalibrated
    tuple val(sample), val(role), path("${sample}.bqsr.bam.bai"), optional: true, emit: indices
    tuple val(sample), val(role), path('applybqsr_versions.txt'), path('run_configuration.txt'), emit: provenance

    script:
    """
    mkdir -p tmp
    pbrun applybqsr \
        --ref "${reference}" \
        --in-bam "${bam}" \
        --in-recal-file "${recal_table}" \
        --out-bam "${sample}.bqsr.bam" \
        --num-gpus 1 \
        --num-threads ${options.threads} \
        --tmp-dir "\$(pwd)/tmp"

    pbrun applybqsr --version > applybqsr_versions.txt 2>&1
    printf '%s\\n' \
        'sample=${sample}' \
        'role=${role}' \
        'input_bam=${bam}' \
        'input_recal_table=${recal_table}' \
        'gpu_device=${options.device}' \
        'num_gpus=1' \
        'num_threads=${options.threads}' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        > run_configuration.txt
    """
}
