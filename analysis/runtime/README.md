# Runtime analyses and timing scope

Three experiments must be kept distinct:

1. Historical fixed CPU–GPU comparison: 219 h 24 min 27 s versus 9 h 38 min 27 s.
2. Historical GPU/thread-scaling experiments, including fq2bam, MutectCaller and DeepSomatic.
3. The functional Nextflow execution using all original HG008 reads, without subsampling.

The Nextflow run used 3 alignment GPUs and 2 caller GPUs, versus 1 GPU in each stage of the fixed historical comparison. Runtime differences therefore include changes in resource allocation.

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

Neither sum includes trimming/FastQC, read-group adjustment, filtering or annotation. The historical 9 h 38 min 27 s total sums the two fq2bam values and the caller value; the documented separate ApplyBQSR runs are outside that sum.

The integrated Nextflow start was 2026-10-16T18:20:48.037356Z; launcher end was 2026-10-20T12:06:10Z. Their difference is approximately **89 h 45 min 22 s**, including trimming/FastQC and startup/finalization. This interval uses launcher timestamps rather than the HTML report's elapsed-time field. Five trimming/FastQC `realtime` values sum to **82 h 01 min 09 s**. The normal trimming container's CPU quota changed from 2 to 8 during this run, as recorded in [Validation](../../validation/hg008_100pct/README.md).

Tasks can overlap: normal read-group adjustment overlapped tumor ApplyBQSR. Adding every task duration is not the pipeline's elapsed wall-clock time. Trace counters of I/O are not physical disk allocation.

## Scaling material

The complete GPU-scaling scripts, raw timing matrices and figure-generation scripts are not included in this repository. DeepSomatic was evaluated in the scaling experiments and is separate from the FASTQ-to-VCF Nextflow workflow.
