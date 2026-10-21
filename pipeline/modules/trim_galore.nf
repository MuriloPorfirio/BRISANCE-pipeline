process TRIM_GALORE {
    tag { "${sample}:${pair_id}" }
    container 'biowardrobe2/trimgalore:v0.4.4'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/trimmed/${sample}/${pair_id}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(sample), val(role), val(pair_id), path(r1), path(r2)
    val java_heap
    val options
    val output_dir

    output:
    tuple val(sample), val(role), val(pair_id), path('*_val_1.fq.gz', arity: '1'), path('*_val_2.fq.gz', arity: '1'), emit: reads
    tuple val(sample), val(role), val(pair_id), path('*_fastqc.html', arity: '2'), path('*_fastqc.zip', arity: '2'), emit: qc
    tuple val(sample), val(role), val(pair_id), path('*_trimming_report.txt', arity: '2'), emit: reports
    tuple val(sample), val(role), val(pair_id), path('versions.txt'), emit: versions

    script:
    def adapterArgs = options.adapter_mode == 'custom'
        ? "--adapter '${options.adapter_r1}' --adapter2 '${options.adapter_r2}'" : ''
    """
    export _JAVA_OPTIONS="-Xmx${java_heap}"

    trim_galore --paired \
        --quality ${options.quality} \
        --length ${options.min_read_length} \
        ${adapterArgs} \
        --fastqc \
        -o . \
        "${r1}" "${r2}"

    {
        trim_galore --version
        cutadapt --version
        fastqc --version
    } > versions.txt 2>&1
    """
}
