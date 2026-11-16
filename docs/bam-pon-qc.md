# Existing BAMs, optional PoN and BAM QC

Version 1.1.0 adds three opt-in features to the configurable runner. Existing FASTQ INIs without these options retain their earlier processing and scientific parameters. The preserved `workflow/` HG008 workflow and its published evaluation are unchanged.

## Reuse an existing tumor–normal BAM pair

Copy [brisance.bam.example.ini](../interface/brisance.bam.example.ini) and supply the sample names, BAMs, reference and VEP cache. BAMs must already have undergone the read processing you intend to use for calling, be coordinate-sorted, and have matching sample names in every read group.

```ini
[analysis]
folder = /analyses/patient_01_pon
input_mode = bam

[tumor]
sample = P01_TUMOR
bam = /data/P01_TUMOR.bam

[normal]
sample = P01_NORMAL
bam = /data/P01_NORMAL.bam
```

An index is required for each BAM. By default its path is `BAM_PATH.bai`; set `bam_index` within the corresponding sample section for another BAI path. BAM mode does not read FASTQs, require BWA indexes or known-sites files, or repeat trimming, alignment, BQSR or read-group rewriting. It checks BAM quickcheck, coordinate-order declaration, read-group IDs/SM, sequence names/lengths against the FASTA index, and one indexed region before calling. These checks do not establish biological identity or full BAM integrity.

BAMs remain read-only inputs and are not copied into the results. Use a new analysis folder. Never point the new run at an old analysis folder containing results.

## Add your panel of normals

The PoN is a resource VCF derived from multiple normal samples. It is separate from the **matched-normal BAM**, which remains required. Use a bgzip-compressed `.vcf.gz` with its adjacent `.tbi`, matching your reference sequences and contig names.

```ini
[somatic]
pon = /references/my_panel.vcf.gz
```

A nonempty `pon` enables the panel. Omit the section or leave `pon` empty to disable it. BRISANCE does not choose or download a panel for you. Prefer a panel appropriate to the assay and technical processing; a public panel is not universally optimal. The [GATK PoN guide](https://gatk.broadinstitute.org/hc/en-us/articles/360035890631-Panel-of-Normals-PON) describes its purpose and public resources.

With the pinned Parabricks 4.5.1-1 image the sequence is:

1. Check REF alleles against the supplied FASTA, generate a derived contig header and TBI, and verify that the variant records are unchanged.
2. Run `prepon` to generate the additional `.pon` index.
3. Supply the panel VCF to `mutectcaller --pon`.
4. Run `postpon` with the same VCF/TBI to annotate panel membership in the caller VCF.
5. Use that annotated VCF and the original caller statistics in GATK FilterMutectCalls, followed by the existing PASS, VEP and positive-TLOD stages.

`postpon` changes variant annotations; its output uses the caller statistics from the same call, not the statistics from an older analysis. Both the pre- and post-PoN VCFs are retained. Shared inputs and original panels are never rewritten. See NVIDIA's [prepon guide for 4.5.1](https://docs.nvidia.com/clara/parabricks/4.5.1/documentation/tooldocs/man_prepon.html) and [postpon documentation](https://docs.nvidia.com/clara/parabricks/tool-reference/tools/postpon).

For an already prepared panel, an advanced option avoids generating its `.pon` again:

```ini
[somatic]
pon = /references/prepared_panel.vcf.gz
pon_prepared = true
```

This requires both adjacent `.tbi` and `.pon` files. The owner must establish that the `.pon` was produced from this exact panel with the selected Parabricks version. BRISANCE checks file presence, indexed VCF access and REF compatibility, but cannot prove the provenance of an arbitrary binary `.pon`. Preserve panel, image and preparation hashes together. Without this explicit option, the runner prepares its own index in managed work.

## Collect QC metrics

```ini
[qc]
enabled = true
```

QC is disabled by default. When enabled, `pbrun collectmultiplemetrics --gen-all-metrics --out-qc-metrics-dir ...` runs separately on each supplied BAM, or on each recalibrated BAM after read-group adjustment in FASTQ mode. Reports cover alignment, insert-size, quality, cycle, GC-bias and sequencing-artifact metrics supported by the pinned tool. See [NVIDIA collectmultiplemetrics](https://docs.nvidia.com/clara/parabricks/4.5.0/documentation/tooldocs/man_collectmultiplemetrics.html) for the command family; BRISANCE uses image **4.5.1-1**.

`--out-qc-metrics-dir` names an output directory; it is not a quality cutoff. This release uses the standalone command so existing BAMs can receive QC without realignment. It does not add that option to fq2bam itself. Its reports describe the recalibrated/supplied BAM stage and must not be represented as measurements taken during the original alignment. QC reports do not remove reads or variants. Calling waits for both requested QC collections to succeed.

Metrics are published under `results/qc/SAMPLE/qc_metrics/`. QC and PoN preprocessing use the `read_groups` CPU/memory limits and the first GPU in `[calling] gpus`. One task runs at a time.

## Check, run and audit

```bash
bash interface/run_brisance.sh patient_01_pon.ini --check
bash interface/run_brisance.sh patient_01_pon.ini --run --no-download
```

For an explicitly authorized unattended run, including a persistent terminal session:

```bash
bash interface/run_brisance.sh patient_01_pon.ini --run --yes --no-download
```

`--yes` requires `--run`, records the explicit choice, and disables image downloads. It bypasses the two human confirmations, not dependency, GPU, input, storage or workflow checks. It does not reserve resources, enable automatic resume or permit overwriting results. Use one settings file and analysis folder per patient and execute them sequentially for a cohort.

BAM-mode storage planning uses a **64 GiB free-space allowance per analysis**, not a measurement of peak disk use. Existing BAM sizes are reported separately. Monitor real usage and allow for all retained cohort outputs, panel preparation, QC, quotas and other users. The earlier FASTQ-based estimate is unchanged.

## Interpreting a PoN comparison

PoN targets recurrent technical/background signals, not missense annotations specifically. Its effect on total, PASS and exonic non-synonymous calls must be measured. A reduction in the number of missense variants is not by itself evidence of better sensitivity or specificity.

For a controlled comparison, retain the exact same BAMs, reference, calling/filtering arguments, VEP/cache and downstream selection, and change only the requested PoN/QC options. QC does not filter. Adding PoN does not harmonize germline resources, F1R2/orientation models, contamination estimates, alignment or transcript selection with a historical hg19 analysis. Reuse the established common-coordinate, harmonized-annotation comparison for the resulting callsets.

The new branches have software tests with synthetic metadata and real Nextflow orchestration using simulated scientific tools. These tests do not constitute a biological benchmark or prove successful execution of the new patient cohort.
