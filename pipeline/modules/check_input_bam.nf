process CHECK_INPUT_BAM {
    tag { "${sample}:${role}" }
    containerOptions { "--cpus ${task.cpus}" }
    publishDir { "${output_dir}/input_checks/${sample}" }, mode: 'link', overwrite: false, failOnError: true,
        pattern: '*.{txt,sam}'

    input:
    tuple val(sample), val(role), path("${sample}.bam"), path("${sample}.bam.bai")
    path fai
    val output_dir

    output:
    tuple val(sample), val(role), path("${sample}.bam"), path("${sample}.bam.bai"), emit: alignments
    tuple val(sample), val(role), path('validation.txt'), path('header.sam'), emit: provenance

    script:
    """
    samtools quickcheck -v "${sample}.bam"
    samtools view -H "${sample}.bam" > header.sam
    awk -v expected='${sample}' 'BEGIN { FS="\\t" }
      NR==FNR { lengths[\$1]=\$2; next }
      \$1=="@HD" { for(i=2;i<=NF;i++) if(\$i=="SO:coordinate") sorted=1 }
      \$1=="@RG" {
        sm=0; id=0; rgid="";
        for(i=2;i<=NF;i++) {
          if(\$i ~ /^SM:/) { sm++; if(substr(\$i,4)!=expected) bad=1 }
          if(\$i ~ /^ID:/) { id++; rgid=substr(\$i,4) }
        }
        if(sm!=1 || id!=1 || rgid=="" || ids[rgid]++) bad=1;
        groups++
      }
      \$1=="@SQ" {
        sn=""; len="";
        for(i=2;i<=NF;i++) { if(\$i ~ /^SN:/) sn=substr(\$i,4); if(\$i ~ /^LN:/) len=substr(\$i,4) }
        if(sn=="" || !(sn in lengths) || lengths[sn]!=len || seen[sn]++) bad=1;
        if(first=="") first=sn; seqs++
      }
      END { if(bad || !sorted || !groups || !seqs) exit 1; print first > "query_contig.txt" }
    ' '${fai}' header.sam
    contig=\$(cat query_contig.txt)
    samtools view -c "${sample}.bam" "\${contig}:1-1" > indexed_query.txt
    grep -Eq '^[0-9]+\$' indexed_query.txt
    samtools --version > validation.txt
    printf '%s\\n' 'sample=${sample}' 'role=${role}' 'SM/reference/index checks passed; BAM unchanged' >> validation.txt
    """
}
