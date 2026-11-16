process COLLECT_BAM_QC {
    tag { "${sample}:${role}" }
    containerOptions { "--gpus '\"device=${options.device}\"' --cpus ${task.cpus}" }
    publishDir { "${output_dir}/${sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(sample), val(role), path(bam), path(bai)
    path reference
    path reference_indices
    val options
    val output_dir

    output:
    tuple val(sample), val(role), path('qc_metrics'), emit: metrics
    tuple val(sample), val(role), path('qc_versions.txt'), path('qc_configuration.txt'), emit: provenance

    script:
    """
    mkdir -p tmp
    pbrun collectmultiplemetrics --ref "${reference}" --bam "${bam}" \
        --out-qc-metrics-dir "\$(pwd)/qc_metrics" --gen-all-metrics \
        --tmp-dir "\$(pwd)/tmp" --num-gpus 1
    test -n "\$(find qc_metrics -type f -size +0c -print -quit)"
    pbrun collectmultiplemetrics --version > qc_versions.txt 2>&1
    printf '%s\\n' 'sample=${sample}' 'role=${role}' 'input_bam=${bam}' \
        'method=collectmultiplemetrics; supplied/recalibrated BAM; no variant filtering' > qc_configuration.txt
    """
}
