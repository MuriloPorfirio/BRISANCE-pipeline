# HG008 full-read Nextflow execution

## Source and identity

This is a structured transcription of terminal output provided by the maintainer on 20 October 2026, not a copy of the original server report archive. Source archive still to retrieve: `reports/hg008-100pct/execution-VlBLXe` on Turing. The scientific implementation is preserved unchanged in `workflow/`.

- Actual integrated run: **sharp_lavoisier**.
- `angry_gilbert` was the preceding validation/preflight run, not the scientific run.
- Main script revision displayed by Nextflow: **0cd76ca9c7**.
- Nextflow: **26.04.6**, build 12646; Java **21.0.10**.
- Original inputs: 5 paired inputs / 10 FASTQs, **500,242,287,130 bytes**, with no subsampling.
- All **18 tasks COMPLETED**, exit 0; no CACHED tasks in the supplied trace.
- Nextflow exit 0 and launcher exit 0.

The [input file table](input_files.csv) and [transcribed trace values](tasks_transcribed.csv) are metadata only, not sequencing payloads.

## Final VCF checks

The final file was `stage8/final/somatico_vs_germinativo/somatico_vs_germinativo.PASS_TLOD.vcf.gz` under the full-run result directory. Read-only BCFtools 1.21 inspection reported:

- Samples: `germinativo`, `somatico`.
- Total VCF records: **17,455**.
- Records with nonempty `INFO/CSQ`: **17,455**.
- Records outside `INFO/TLOD>0 && INFO/TLOD!="."`: **0**.
- Workflow count file: annotated_PASS **17,455**, PASS_TLOD **17,455**.

The maintainer compared this file with the historical `HG008-IDUDI0031_somatico_vs_germinativo.PASS_TLOD.vcf.gz` using `bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\n'`, `LC_ALL=C sort` and `comm`:

| Comparison | VCF records |
| --- | --- |
| Shared | 17,455 |
| Historical only | 0 |
| Nextflow only | 0 |

This is 100% agreement of the compared record identity lists, **not** a hash/byte comparison, equality of FORMAT/genotypes/VAF/annotations, a normalized/haplotype-aware allele comparison, or 100% biological accuracy. The manuscript's SNV+indel and RTG units are different. No other equivalence tests are implied.

## Resources and intervention

fq2bam used GPUs **7,6,5**, BWA thread-pool parameter **16** per GPU and a 64-logical-CPU quota. MutectCaller used GPUs **7,6**, thread parameter **24** and a 64-logical-CPU quota. ApplyBQSR used GPU **7**, worker parameter **16** and a 24-logical-CPU quota. Both alignments ran sequentially, not as two concurrent 3-GPU jobs.

At **2026-10-19T12:33:12Z**, while the normal Trim Galore container was running, the maintainer changed its Docker CPU quota from **2 to 8** using `docker update --cpus 8` on that exact container. The workflow was not restarted and its scientific code was not edited. Immediately reported CPU utilization was approximately 226–227%, not 800%. This was a manual resource intervention; the full run must not be presented as uniformly using either 2 or 8 trimming CPUs. It is not proof of an eight-thread Cutadapt implementation.

## Timing and storage

- Integrated start UTC reported: **2026-10-16T18:20:48.037356Z**.
- Launcher end UTC reported: **2026-10-20T12:06:10Z**.
- Difference: approximately **89 h 45 min 22 s**; endpoints are not an independently extracted same-scope HTML runtime.
- Five trimming/FastQC realtimes sum to **82 h 01 min 09 s**.
- fq2bam normal + fq2bam tumor + caller realtimes sum to **4 h 12 min 20 s**.
- Including both separate ApplyBQSR realtimes gives **6 h 13 min 27 s**.

Full wall-clock time is not a sum of all task durations: normal header adjustment overlapped tumor ApplyBQSR. Earlier fixed/scaling resource settings differ, so the shorter selected-stage sum is not attributed to Nextflow alone.

End-of-launcher `df` reported 60% occupancy on `/raid` (total 30,601,613,336,576; used 17,236,840,017,920; available 11,828,508,397,568 bytes). This is a filesystem snapshot, not a measured workflow disk peak or isolated BRISANCE footprint.

## Remaining evidence work

Retrieve raw trace/configuration/version files, verify original reports, and inspect any additional checks before making broader claims. Index presence or successful traversal alone does not establish full index consistency. No full-input GPU rerun was performed from this newly reorganized repository.
