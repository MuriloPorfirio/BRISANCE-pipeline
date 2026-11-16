process CHECK_PREPARED_PON {
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/pon" }, mode: 'link', overwrite: false, failOnError: true
    input:
    path pon
    path tbi
    path pon_index
    path reference
    path reference_indices
    val output_dir
    output:
    path 'prepared_pon_check.txt', emit: receipt
    script:
    """
    bcftools view -h "${pon}" > prepared_pon_check.txt
    bcftools index -n "${pon}" >> prepared_pon_check.txt
    bcftools norm --check-ref e --fasta-ref "${reference}" -Ou -o /dev/null "${pon}"
    test -s "${pon_index}"
    """
}

process PREPARE_PON_VCF {
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/pon" }, mode: 'link', overwrite: false, failOnError: true
    input:
    path pon
    path tbi
    path reference
    path reference_indices
    val output_dir
    output:
    tuple path('panel.hg38.vcf.gz'), path('panel.hg38.vcf.gz.tbi'), emit: panel
    path 'pon_records.sha256', emit: provenance
    script:
    def fai = reference_indices.find { it.name.endsWith('.fai') }
    """
    bcftools norm --check-ref e --fasta-ref "${reference}" -Ou -o /dev/null "${pon}"
    bcftools reheader --fai "${fai}" -o panel.hg38.vcf.gz "${pon}"
    bcftools index -t panel.hg38.vcf.gz
    bcftools view -H "${pon}" | sha256sum | cut -d' ' -f1 > original_records.sha256
    bcftools view -H panel.hg38.vcf.gz | sha256sum | cut -d' ' -f1 > pon_records.sha256
    cmp original_records.sha256 pon_records.sha256
    """
}

process PREPON {
    containerOptions { "--gpus '\"device=${device}\"' --cpus ${task.cpus}" }
    publishDir { "${output_dir}/pon" }, mode: 'link', overwrite: false, failOnError: true,
        pattern: '*.pon'
    input:
    tuple path(pon, stageAs: 'source.vcf.gz'), path(tbi, stageAs: 'source.vcf.gz.tbi')
    val device
    val output_dir
    output:
    tuple path('panel.hg38.vcf.gz'), path('panel.hg38.vcf.gz.tbi'), path('panel.hg38.vcf.gz.pon'), emit: panel
    script:
    """
    cp --reflink=auto source.vcf.gz panel.hg38.vcf.gz
    cp source.vcf.gz.tbi panel.hg38.vcf.gz.tbi
    pbrun prepon --in-pon-file "\$(pwd)/panel.hg38.vcf.gz" --num-gpus 1
    test -s panel.hg38.vcf.gz.pon
    """
}

process POSTPON {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    containerOptions { "--gpus '\"device=${device}\"' --cpus ${task.cpus}" }
    publishDir { "${output_dir}/variants/${tumor_sample}_vs_${normal_sample}" }, mode: 'link', overwrite: false, failOnError: true,
        pattern: '{*.pon.vcf,postpon_versions.txt}'
    input:
    tuple val(tumor_sample), val(normal_sample), path(raw_vcf), path(stats)
    tuple path(pon), path(tbi), path(pon_index)
    val device
    val output_dir
    output:
    tuple val(tumor_sample), val(normal_sample), path("${tumor_sample}_vs_${normal_sample}.pon.vcf"), path(stats), emit: calls
    path 'postpon_versions.txt', emit: provenance
    script:
    """
    pbrun postpon --in-vcf "${raw_vcf}" --in-pon-file "${pon}" \
        --out-vcf "${tumor_sample}_vs_${normal_sample}.pon.vcf" --num-gpus 1
    test -s "${tumor_sample}_vs_${normal_sample}.pon.vcf"
    pbrun postpon --version > postpon_versions.txt 2>&1
    """
}
