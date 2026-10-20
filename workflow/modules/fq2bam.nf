process FQ2BAM {
    tag { "${sample}:${role}" }
    container 'nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1'
    containerOptions { "--gpus '\"device=${options.devices.join(',')}\"' --cpus ${task.cpus}" }
    publishDir { "${output_dir}/aligned/${sample}" }, mode: 'symlink', overwrite: false, failOnError: true

    input:
    tuple val(sample), val(role), val(pair_ids), path(r1_reads), path(r2_reads)
    path reference
    path reference_indices
    path known_sites
    path known_indices
    val options
    val output_dir

    output:
    tuple val(sample), val(role), path("${sample}.bam"), path("${sample}.recal.table"), path("${sample}.dup_metrics.txt"), emit: alignments
    tuple val(sample), val(role), path("${sample}.bam.bai"), optional: true, emit: indices
    tuple val(sample), val(role), path('fq2bam_versions.txt'), path('run_configuration.txt'), emit: provenance

    script:
    def r1 = r1_reads instanceof List ? r1_reads : [r1_reads]
    def r2 = r2_reads instanceof List ? r2_reads : [r2_reads]
    if (r1.size() != r2.size() || r1.size() != pair_ids.size()) {
        error "${sample}: inconsistent R1/R2/pair identifier counts."
    }
    def fastqArgs = (0..<r1.size()).collect { index ->
        "--in-fq \"${r1[index]}\" \"${r2[index]}\""
    }.join(' \\\n        ')
    def knownArgs = known_sites.collect { site -> "--knownSites \"${site}\"" }.join(' \\\n        ')
    """
    mkdir -p tmp
    pbrun fq2bam \
        --ref "${reference}" \
        ${fastqArgs} \
        ${knownArgs} \
        --out-bam "${sample}.bam" \
        --out-recal-file "${sample}.recal.table" \
        --out-duplicate-metrics "${sample}.dup_metrics.txt" \
        --tmp-dir "\$(pwd)/tmp" \
        --num-gpus ${options.devices.size()} \
        --bwa-cpu-thread-pool ${options.thread_pool} \
        --memory-limit ${options.sort_memory_gb} \
        --gpusort --gpuwrite

    pbrun fq2bam --version > fq2bam_versions.txt 2>&1
    printf '%s\\n' \
        'sample=${sample}' \
        'role=${role}' \
        'pair_ids=${pair_ids.join(',')}' \
        'gpu_devices=${options.devices.join(',')}' \
        'num_gpus=${options.devices.size()}' \
        'bwa_cpu_thread_pool=${options.thread_pool}' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        'sorting_memory_limit_gb=${options.sort_memory_gb}' \
        > run_configuration.txt
    """
}
