# Using Cluster Inspector output as workspace configuration

Implemented in **0.3.0-preview1**. Updated 2026-09-22. Transfer both the new SIF and matching launcher; the YAML reader is bundled in this image.

## Setup and daily commands

After verifying the transferred image, load the site's Apptainer module and import an existing local profile:

```bash
ws init --profile /path/to/profile.yaml --image /path/to/release.sif
ws use /path/to/release.sif --sha256 CHECKSUM_FROM_THE_SHA256_FILE
cd /path/to/project
ws enter
# Or: ws session --host-jobs
```

`ws init` reports the saved system key, scheduler default, configuration path, and changed setting names. Add `--dry-run` to parse the profile and preview those changes without saving. The image is used only as a YAML reader for this operation; neither Inspector nor its probes are run.

For first-entry import, use `ws enter --profile /path/to/profile.yaml --image /path/to/release.sif`. A site module may instead export `WS_INSPECTOR_PROFILE=/path/to/profile.yaml`; `ws enter` or `ws session` imports it if that system has no saved import. Once imported, later starts ignore changes to that source until explicitly refreshed. `--profile` pointing to the same source also reuses the saved import on entry.

Without Inspector, `ws init --site ruth` saves the existing Ruth default; use `jean` or `blueback` for the other original defaults. `ws init --site example --scheduler slurm` supports another system. A basic shell also works without setup using `ws enter --image /path/to/release.sif`, with a generic `local` state directory. The current directory is the default project.

When the system/profile changes:

```bash
ws refresh --dry-run
ws refresh
```

Refresh uses the saved source path and selected image. `--profile NEW_FILE.yaml` selects a replacement source; `--image FILE.sif` selects a reader image for this invocation. If the YAML is stale, regenerate it through your normal Inspector workflow first. `ws doctor` reports the saved facts, source path/hash/import time, and current runtime checks.

## Where configuration lives

The private file is `${XDG_CONFIG_HOME:-$HOME/.config}/hpc-workspace/config.json`. Set `WS_CONFIG_DIR` to use a different configuration directory. One file describes the system configured there. If several clusters share the same home/configuration path, supply a separate `WS_CONFIG_DIR` through each system's usual setup or module. No hostname-discovery service is involved.

The file stores imported facts separately from an `overrides` object. Personal `scheduler`, `binds`, and `scheduler_env` settings belong in `overrides` and survive refresh. `ws init --scheduler pbs` or `--scheduler slurm` saves a scheduler override without needing the source YAML or image. Binds and additional scheduler environment names use the same formats documented in the main README. Existing `profiles/SITE.local.json` files are still supported and take precedence over saved defaults/overrides.

The explicit `--site` option selects a system for one invocation without changing the saved default. Existing state and image-selection directories are retained. If a generic workspace was already used before its first profile import, `state_site` keeps its original state directory unless the imported system already has one. `--state-dir` remains an invocation-specific override.

## Purpose

Use an existing, locally available Cluster Inspector `profile.yaml` to populate useful workspace settings during initial setup. Save those settings as private local configuration and reuse them on later starts. Refresh the imported settings explicitly when the profile or system changes.

Cluster Inspector remains a separate tool with its existing workflow and output. This integration consumes that output; it does not change Inspector, require a new export command, or run its probes. The common development SIF continues to provide the same tools across systems.

## Initial setup and later use

1. During first entry or setup, use an Inspector profile if its location has been supplied through a workspace option or local/site configuration. If no profile is available, allow the core development environment to start with its normal defaults and explicit settings.
2. Read the YAML, validate the supported version and consumed fields, and import the useful system facts. Use the configured profile's system name for the workspace label and saved settings. Existing explicit personal settings take precedence over imported defaults.
3. Save the imported settings with the source path, content hash, and import time in local workspace configuration. The original YAML remains unchanged.
4. On subsequent starts, load the saved configuration. Inspector and the original YAML are not required for ordinary startup. Do not rerun discovery or automatically re-import a changed file on every entry.
5. When an update is wanted, refresh from the local YAML. If the system changed and the YAML is stale, regenerate it using the normal Inspector workflow first, then refresh the workspace configuration.

The configured local profile is the input for this system. No separate host-membership discovery or verification feature is needed for this setup workflow. A site module can supply the profile location; otherwise the user supplies it once. Routine commands then omit the repeated site name. Selection of a verified SIF remains a separate saved workspace setting.

## Information to reuse

| Existing profile information | Workspace use |
| --- | --- |
| System name and family | System label and configuration/state scope |
| PBS or Slurm external entry, when present | Default scheduler selection for the existing convenience commands |
| MPI providers, versions, prefixes, and module chains | Saved facts for later MPI setup and diagnostics |
| Fabric and libfabric entries, including available prefixes | Saved facts for later runtime-library integration |
| OS/glibc, node CPU/GPU targets, compiler and toolkit providers | Available capabilities for diagnostics and later compatibility checks |

Consume the facts that are present. Missing optional information does not block the core shell. If scheduler information is absent or ambiguous, preserve an explicit local scheduler setting or request just that setting when the submission convenience is needed. No account, queue, or authentication discovery is required by this import.

Personal mounts and image selection remain normal workspace configuration. Filesystem candidates in the profile can inform a later setup choice; importing them does not mount directories. Importing MPI, libfabric, or GPU paths similarly records available information without automatically loading modules, replacing libraries, or declaring an integration validated.

## Daily jobs and interactive allocations

Existing scripts and native `sbatch`/`qsub` behavior remain the basis of job submission. Script directives and site defaults already handle job resources and placement. Interactive allocations use each system's normal procedure; the user then starts the development environment within that allocation.

The Inspector importer supplies a saved scheduler default where useful. It does not translate scripts, choose job resources, configure authentication, or add the development image to batch jobs.

The current optional host connection can reuse that saved configuration when accepting a submission from the container. Existing checks of allocation variables and scheduler-provided GPU visibility remain tied to operations that need them; they are not an Inspector refresh or general discovery pass.

The released `ws submit` wrapper also filters exported environment variables and adds scheduler export options. Reviewing that behavior against the desired native submission workflow is a separate change, not a prerequisite for consuming Inspector output. The import itself must not introduce further submission-policy changes.

After this integration and initial image selection, the intended entry commands are:

```bash
cd /path/to/project
ws enter
# Or a persistent workspace session:
ws session
```

The optional `--host-jobs` connection remains available for submission convenience. Release 0.2.0-preview1 and earlier still require `--site` on the host; use a matching launcher from 0.3.0-preview1 or later to use saved configuration.

## Refresh behavior

A refresh validates a candidate and shows which imported settings would change, then atomically replaces only those settings. A failed import leaves the working configuration intact. Preserve personal overrides, binds, image selection/rollback, and saved editor/session state. Preserve the existing state directory when the imported name matches an already configured site; a changed name must not silently move or discard state.

New sessions use the refreshed configuration. Existing sessions and host submission connections retain the settings with which they started. Updating configuration does not rebuild the SIF or change a running job.

The source hash and import time explain what was imported. They are bookkeeping, not a claim that the system has been rescanned. Freshness is maintained through the user's normal local Inspector/update workflow.

## Implementation within hpc-workspace

The import module turns a supported Inspector YAML profile into workspace configuration defaults. Parsing, field mapping, validation, and refresh behavior stay behind that interface. It uses the existing YAML format directly; no Inspector or canonical schema changes are required.

The image bundles Ubuntu's snapshot-pinned `python3-yaml` package. The host takes a fixed local snapshot of the input and binds it read-only to the helper, which returns normalized JSON. Normal startup uses only the host Python standard library. This is an internal workspace conversion, not a new Inspector export or a user conversion step. The reader rejects unsupported versions, malformed/unsafe YAML, duplicate keys, and excessive or recursive aliases.

The importer validates supported schema versions and the types of fields it consumes. Absent facts remain absent; an existing named scheduler default is retained when the profile has no scheduler entry. Profile strings are data, system names map to safe state keys, and profile contents are never executed. The [contract review](research/cluster-inspector-contract.md) identifies the current field shapes and synthetic fixtures.

Configured daily entry supports system names beyond the original three, while preserving explicit settings and released state paths. The existing `ws doctor` report shows imported values and their source. The source profile, saved settings, and derived system information stay on the cluster; the public repository and image contain only code, generic defaults, and synthetic fixtures where applicable.

The synthetic tests cover initial import, startup without Inspector or the source YAML, missing optional fields, malformed/unsupported input, conflicting scheduler entries, refresh, and preservation of personal overrides/state. The nested Apptainer test exercises the delivered SIF as the YAML reader and then enters it using saved configuration. See the [validation record](validation.md) for results and local-runtime limitations.
