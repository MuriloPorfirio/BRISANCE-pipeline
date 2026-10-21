# Settings-file interface: HG008 small-input integration test

On 20 October 2026, the file-based interface was exercised on Turing with the existing HG008 first-read-prefix test: 10,000 synchronized input read pairs for tumor and 10,000 for normal. Four FASTQs were supplied through an editable INI file. The runner generated pair identifiers, showed the configuration/storage summary, obtained confirmation, checked dependencies/access, validated the configurable Nextflow entry point and obtained a second confirmation before analysis.

Nextflow 26.04.6 executed run `elegant_yalow`, script revision `7efcfc31ce`, under `analysis-small-test-01/reports/execution-38dfogji`. The complete sequence from trimming/FastQC to positive-TLOD selection completed **15 tasks, all with status COMPLETED and exit code 0**, without cached tasks. The final indexed VCF contained **zero variant records**, consistent with the earlier prefix test.

The time window from the first task submission to the approximate completion of the last task was **5 minutes 22 seconds**. This is inferred from the trace, not a measured total launcher runtime. It excludes prompts, environment checks, startup before the first task and work after the last task. The sum of reported task `realtime` values was approximately **5 minutes 13 seconds**; trace durations are rounded and these quantities must not be conflated.

| Phase | Tasks | Sum of reported task realtime |
| --- | ---: | ---: |
| Trim Galore / FastQC | 2 | 49.5 s |
| fq2bam | 2 | 213 s |
| ApplyBQSR | 2 | 3.2 s |
| Read-group sample-name adjustment | 2 | 0.192 s |
| MutectCaller | 1 | 42.6 s |
| Compression, filtering, PASS selection, VEP, indexing and positive-TLOD selection | 6 | 4.542 s |

The alignment configuration selected GPUs 7, 6 and 5, BWA thread-pool parameter 16 and a 64-CPU quota. Recalibration selected GPU 7 with thread parameter 16 and a 24-CPU quota. Calling selected GPUs 7 and 6 with thread parameter 24 and a 64-CPU quota. Thread parameters are not measurements of consumed CPUs. One task was scheduled at a time; GPUs were not reserved.

Environment checks passed for the installed tool versions, selected GPU visibility, read-only input/resource access, report-directory writing and regular-file publication. Downloads were disabled and all six required images were already present. The set of local Docker image IDs found in generated task wrappers matched the six IDs saved in the execution parameters. Grep counts reflected text occurrences, not numbers of container executions. The launcher also checked that published results were not symbolic links and that the final VCF/index were present.

This server execution emitted an undefined `images` parameter warning during early container discovery. It nevertheless completed, with the recorded image IDs present in the task wrappers. The subsequent local correction resolves constant image IDs during configuration parsing instead of through dynamic container closures. That change was not part of the server run documented here; its local orchestration regression tests are separate.

After transferring the corrected configuration to Turing, metadata validation was repeated with the saved parameters. Run `lethal_becquerel` on Nextflow 26.04.6 reported `CONFIGURABLE WORKFLOW CHECK OK: 2 input pairs; all stages loaded. No processing started.`, without the undefined-image warning. The main script revision remained `7efcfc31ce`; the change was in the configuration. This follow-up did not repeat scientific processing or overwrite the original execution records.

## Initial setup follow-up

On 21 October 2026, `setup_brisance.sh` was checked and then executed on Turing with `--no-download` and explicit paths to the existing Conda Java and Nextflow 26.04.6 standalone distribution. The read-only check reported a successful Nextflow SHA-256 verification. After confirmation, preparation reported `RUNTIME READY`, created the editable `analysis.local.ini` template and identified `.brisance/setup-0w8pglqf.json` as its setup record. No package download or sequencing-data processing was requested.

The existing small-input INI was then checked through `interface/run_brisance.sh ... --check`. It reported `SETTINGS CHECK OK` and confirmed that the saved configuration still matched, without writing, resuming or overwriting results. This follow-up did not recheck GPU/container availability or repeat the 15-task scientific execution. The generic template was created for user editing; this subsequent metadata check used the previously configured small-input INI, not that unedited template. The [structured record](execution_transcribed.json) distinguishes these steps.

## Scope and provenance

This test establishes integrated operation of the configuration/confirmation/checking/launch path for these small inputs and settings. It does not measure sensitivity, precision, variant-annotation correctness on nonempty data, performance at WGS scale, alternative assemblies or all user-configurable parameter combinations. No independent biological accuracy conclusion follows from an empty VCF. The [full-input HG008 evaluation](../hg008_100pct/README.md) is a separate record for the preserved scientific workflow.

The [structured record](execution_transcribed.json) was transcribed from user-provided console output, trace rows and image-ID listings. It includes individual task timings, configured resources and image IDs. Original remote reports, FASTQs, BAMs and VCFs are not bundled in this directory. Submission timestamps retain the printed server values; the pasted trace did not specify a timezone.
