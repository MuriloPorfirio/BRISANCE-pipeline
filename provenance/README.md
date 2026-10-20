# Provenance

The four previously separate public repositories were copied into `source_snapshots/` without editing their contents. These are **historical source copies**, not the recommended user entry points and not a claim that every example produced the manuscript results. The original repositories and their Git history remain unchanged.

[source_repositories.json](source_repositories.json) records each original URL, fetched commit and destination. [source_manifest.json](source_manifest.json) records each copied file's SHA256 and Git blob ID. Git metadata, credentials and nested repositories are not imported into the snapshots.

[workflow_manifest.json](workflow_manifest.json) records the original local scientific workflow/configuration/modules. Those files are copied byte-for-byte into `workflow/`; new README prose is separate and is not used as historical evidence.

## Evidence classes

1. **Preserved source:** unchanged public repository files and unchanged tested Nextflow code.
2. **Recovered historical commands:** commands matched to the maintainer's HG008 notebook, headers and log excerpts; documented in the historical section. A newly path-adapted recipe is labeled as reconstructed, not as the original executed file.
3. **Observed validation:** terminal outputs supplied by the maintainer for the 20% and full Nextflow runs. The remote raw reports have not yet been downloaded to this repository.
4. **Missing release material:** original VAF/FILTER scripts, full GPU-scaling material and remaining raw evidence. These are explicitly listed, not fabricated.

The root non-commercial policy does not silently relicense preserved source copies. See [Licensing](../docs/licensing.md).
