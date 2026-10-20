# Source provenance

`source_snapshots/` contains unchanged copies of the four original project repositories. These include historical execution examples as well as study-specific scripts. The HG008 manual procedure is documented separately in [Historical workflows](../historical_workflows/README.md).

| File | Contents |
| --- | --- |
| [source_repositories.json](source_repositories.json) | Original repository URLs, commit identifiers and snapshot locations |
| [source_manifest.json](source_manifest.json) | SHA256 checksums and Git blob identifiers for the preserved files |
| [workflow_manifest.json](workflow_manifest.json) | Checksums of the Nextflow configuration and scientific modules used for the HG008 run |

The original repositories remain unchanged. Adapted manual command recipes and the corrected indel-comparison script are identified in their respective sections. HG008 execution summaries are based on the recorded terminal outputs; the raw remote report archive is not included.

Original license terms are retained with the corresponding sources. See [Licensing](../docs/licensing.md).
