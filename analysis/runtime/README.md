# Runtime analyses and timing scope

Three experiments must be kept distinct:

1. Historical fixed CPU–GPU comparison used for the manuscript's 219 h 24 min 27 s vs 9 h 38 min 27 s claim.
2. Historical GPU/thread-scaling experiments, including fq2bam, MutectCaller and DeepSomatic.
3. Later functional Nextflow executions on approximately 20% and on all original reads.

The later run used 3 alignment GPUs and 2 caller GPUs, versus 1 GPU in each stage of the fixed historical comparison. It is not an isolated measurement of Nextflow acceleration or overhead.

## Full-read Nextflow task times

From the supplied trace's `realtime` fields:

| Selected task | Time |
| --- | --- |
| fq2bam tumor | 1 h 24 min 08 s |
| fq2bam normal | 1 h 33 min 33 s |
| MutectCaller | 1 h 14 min 39 s |
| Sum of those three tasks | **4 h 12 min 20 s** |
| Separate ApplyBQSR normal | 1 h 05 min 55 s |
| Separate ApplyBQSR tumor | 0 h 55 min 12 s |
| Sum including both separate ApplyBQSR tasks | **6 h 13 min 27 s** |

Neither sum includes trimming/FastQC, read-group adjustment, filtering or annotation. The manuscript's displayed GPU total sums its two fq2bam values and its caller value; it must not be described as including a separately timed ApplyBQSR unless that accounting is corrected. These figures do not replace the historical results.

The integrated Nextflow start reported was 2026-10-16T18:20:48.037356Z; launcher end was 2026-10-20T12:06:10Z. Their difference is approximately **89 h 45 min 22 s**, including trimming/FastQC and startup/finalization. Because the endpoints refer to integrated-start and launcher-end, this is not an independently extracted exact Nextflow HTML runtime. Five trimming/FastQC `realtime` values sum to **82 h 01 min 09 s**. A normal trimming CPU quota was changed mid-run; record that intervention rather than presenting uniform settings.

Tasks can overlap: normal read-group adjustment overlapped tumor ApplyBQSR. Adding every task duration is not the pipeline's elapsed wall-clock time. Trace counters of I/O are not physical disk allocation.

## Scaling material

The original four repositories do not contain a complete set of GPU-scaling scripts, raw timing matrices and figure-generation scripts for the manuscript. These need to be imported from the study records. No matrix is invented from selected textual minima. DeepSomatic is a scaling-analysis component, **not** part of the current FASTQ-to-final-VCF Nextflow workflow.
