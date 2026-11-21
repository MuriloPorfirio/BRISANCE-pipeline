// Optional GATK models; CPU only, using the same filtering resource limits.
process CHECK_CONTAMINATION_SITES {
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/somatic_models/resource" }, mode: 'link', overwrite: false, failOnError: true,
        pattern: '*.{txt,tsv}'

    input:
    path sites, stageAs: 'population.vcf.gz'
    path sites_index, stageAs: 'population.vcf.gz.tbi'
    path reference
    path reference_indices
    val output_dir

    output:
    tuple path('population.vcf.gz'), path('population.vcf.gz.tbi'), emit: resource
    path 'resource_validation.txt', emit: provenance

    script:
    """
    test "\$(bcftools query -l population.vcf.gz | wc -l)" -eq 0
    bcftools index -s population.vcf.gz > indexed_contigs.tsv
    awk 'BEGIN { FS="\\t" } NR==FNR { lengths[\$1]=\$2; next }
         { if(!(\$1 in lengths) || lengths[\$1]!=\$2) exit 1; n++ }
         END { if(!n) exit 1 }' '${reference}.fai' indexed_contigs.tsv
    bcftools norm -c e -f "${reference}" -Ou population.vcf.gz | \\
      bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%INFO/AF\\n' | \\
      awk 'BEGIN { FS="\\t" }
        { if(NF!=5 || \$2<1 || \$3 !~ /^[ACGT]\$/ || \$4 !~ /^[ACGT]\$/ || \$3==\$4 ||
             \$5 !~ /^[0-9.eE+-]+\$/ || \$5+0<0.01 || \$5+0>0.20) exit 1;
          if(\$1==chrom && \$2<pos || \$1!=chrom && closed[\$1]) exit 1;
          if(\$1!=chrom || \$2!=pos) { delete seen; if(\$1!=chrom) closed[chrom]=1 }
          key=\$3 SUBSEP \$4; if(seen[key]++) exit 1;
          chrom=\$1; pos=\$2; count++ }
        END { if(!count) exit 1; print count > "site_count.txt" }
      '
    bcftools index -n population.vcf.gz > indexed_count.txt
    cmp site_count.txt indexed_count.txt
    bcftools --version > resource_validation.txt
    printf 'validated_common_SNPs=' >> resource_validation.txt
    cat site_count.txt >> resource_validation.txt
    """
}

process GET_PILEUP_SUMMARIES {
    tag { "${sample}:${role}" }
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/somatic_models/contamination/${sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(sample), val(role), path("${sample}.bam"), path("${sample}.bam.bai")
    tuple path(sites), path(sites_index)
    path reference
    path reference_indices
    val java_heap_gb
    val output_dir

    output:
    tuple val(sample), val(role), path("${sample}.pileups.table"), emit: pileups
    path 'pileup_versions.txt', emit: provenance

    script:
    """
    mkdir -p tmp
    gatk --java-options "-Xmx${java_heap_gb}g -Djava.io.tmpdir=\$(pwd)/tmp" GetPileupSummaries \\
      -I "${sample}.bam" -R "${reference}" -V "${sites}" -L "${sites}" \\
      --minimum-population-allele-frequency 0.01 --maximum-population-allele-frequency 0.20 \\
      -O "${sample}.pileups.table"
    test -s "${sample}.pileups.table"
    gatk --version > pileup_versions.txt 2>&1
    """
}

process CALCULATE_CONTAMINATION {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/somatic_models/contamination/${tumor_sample}_vs_${normal_sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), path(tumor_pileups), val(normal_sample), path(normal_pileups)
    val java_heap_gb
    val output_dir

    output:
    tuple path("${tumor_sample}.contamination.table"), path("${tumor_sample}.segments.table"), emit: model
    path 'contamination_versions.txt', emit: provenance

    script:
    """
    mkdir -p tmp
    gatk --java-options "-Xmx${java_heap_gb}g -Djava.io.tmpdir=\$(pwd)/tmp" CalculateContamination \\
      -I "${tumor_pileups}" --matched-normal "${normal_pileups}" \\
      --tumor-segmentation "${tumor_sample}.segments.table" -O "${tumor_sample}.contamination.table"
    test -s "${tumor_sample}.segments.table"
    test -s "${tumor_sample}.contamination.table"
    gatk --version > contamination_versions.txt 2>&1
    """
}

process LEARN_READ_ORIENTATION_MODEL {
    tag { "${tumor_sample}_vs_${normal_sample}" }
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/somatic_models/orientation/${tumor_sample}_vs_${normal_sample}" }, mode: 'link', overwrite: false, failOnError: true

    input:
    tuple val(tumor_sample), val(normal_sample), path(f1r2)
    val java_heap_gb
    val output_dir

    output:
    path "${tumor_sample}.orientation_priors.tar.gz", emit: priors
    path 'orientation_versions.txt', emit: provenance

    script:
    """
    mkdir -p tmp
    gatk --java-options "-Xmx${java_heap_gb}g -Djava.io.tmpdir=\$(pwd)/tmp" LearnReadOrientationModel \\
      -I "${f1r2}" -O "${tumor_sample}.orientation_priors.tar.gz"
    test -s "${tumor_sample}.orientation_priors.tar.gz"
    gatk --version > orientation_versions.txt 2>&1
    """
}
