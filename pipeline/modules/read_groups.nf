process ADJUST_READ_GROUPS {
    tag { "${sample}:${role}" }
    container 'staphb/samtools:1.19'
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/read_groups/${sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(sample), val(role), path(bam)
    val index_threads
    val output_dir

    output:
    tuple val(sample), val(role), path("${sample}.reheader.bam"), path("${sample}.reheader.bam.bai"), emit: alignments
    tuple val(sample), val(role), path('samtools_versions.txt'), path('read_groups.before.sam'), path('read_groups.after.sam'), path('run_configuration.txt'), emit: provenance

    script:
    """
    samtools quickcheck -v "${bam}"
    samtools view -H "${bam}" > header.before.sam
    grep '^@RG' header.before.sam > read_groups.before.sam

    # Require existing SM and ID fields. Do not replace read-group IDs,
    # library/platform fields, or alignment-level RG tags.
    awk 'BEGIN { FS="\\t" }
         { sm=0; id=0; rgid="";
           for (i=2; i<=NF; i++) {
             if (\$i ~ /^SM:/) { sm++; if (length(\$i)==3) exit 1 }
             if (\$i ~ /^ID:/) { id++; rgid=substr(\$i,4) }
           }
           if (sm!=1 || id!=1 || rgid=="" || seen[rgid]++) exit 1
         }' read_groups.before.sam

    samtools reheader \
        -c 'sed -E "/^@RG/ s/SM:[^[:space:]]+/SM:${sample}/g"' \
        "${bam}" > "${sample}.reheader.bam"

    samtools quickcheck -v "${sample}.reheader.bam"
    samtools index -@ ${index_threads} "${sample}.reheader.bam"
    samtools view -H "${sample}.reheader.bam" > header.after.sam
    grep '^@RG' header.after.sam > read_groups.after.sam

    sed -E "/^@RG/ s/SM:[^[:space:]]+/SM:${sample}/g" \
        read_groups.before.sam > read_groups.expected.sam
    cmp read_groups.expected.sam read_groups.after.sam

    # Non-PG header lines must change only in SM. samtools may add @PG.
    sed -E "/^@RG/ s/SM:[^[:space:]]+/SM:${sample}/g" header.before.sam |
        sed '/^@PG/d' > header.expected.non_pg.sam
    sed '/^@PG/d' header.after.sam > header.actual.non_pg.sam
    cmp header.expected.non_pg.sam header.actual.non_pg.sam

    samtools --version > samtools_versions.txt
    printf '%s\\n' \
        'sample=${sample}' \
        'role=${role}' \
        'input_bam=${bam}' \
        'method=samtools reheader -c; SM-only replacement' \
        'index_threads=${index_threads}' \
        'cpu_quota=${task.cpus}' \
        'container_memory=${task.memory}' \
        > run_configuration.txt
    """
}
