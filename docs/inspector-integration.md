# Use existing Cluster Inspector output

Current workflow: **0.7 thin workspace**, installed with [the repo's `./setup`](thin-start.md). Inspector is optional configuration input. The workspace does not run Inspector or probe a cluster on entry. Without a profile, `ws enter`, packaged tools, automatic filesystem integration, and ordinary native scheduler commands still work.

## Import once

From the native shell after installation and the site's normal Apptainer setup:

```bash
ws init --profile /path/to/profile.yaml --dry-run
ws init --profile /path/to/profile.yaml
cd /path/to/project
ws enter
```

Use an actual existing profile on that system. The installed image supplies the YAML reader, so there is no separate image-selection/checksum step or host PyYAML installation. `ws init` reports saved setting names; the source YAML remains unchanged. `ws session` is the alternative daily entry command for managed tmux, without `--host-jobs`.

For first-entry import, `ws enter --profile /path/to/profile.yaml` works as well. A site setup can supply `WS_INSPECTOR_PROFILE`; first entry imports it when there is no saved import. Later entries reuse the saved facts. They do not automatically reread a changed profile or run new discovery.

## Refresh when needed

After updating the YAML through your existing Inspector workflow:

```bash
ws refresh --dry-run
ws refresh
```

`ws refresh --profile /path/to/replacement.yaml` changes the source explicitly. A failed validation leaves the saved settings intact. Refresh preserves personal overrides and saved state; it does not rebuild the image, alter an existing session, or change a running job. `ws doctor` displays imported source/hash/time metadata and current local checks. Keep its output on the system.

## What is used

| Facts in the profile | Current workspace use |
| --- | --- |
| System name/family | Saved label and configuration/state scope |
| PBS/Slurm entries | Saved scheduler facts/default where applicable |
| MPI providers, modules, versions, prefixes | Stored facts for diagnostics and later integration |
| Fabric/libfabric details | Stored facts for later compatibility work |
| OS/glibc, CPU/GPU targets, compiler/toolkit providers | Stored capability information |

Missing optional fields remain absent. Importing paths does not load modules, install software, mount an MPI stack, or establish compatibility. Native `sbatch`/`qsub` use the system's own clients, scripts, authentication, and resource options. Inspector import does not choose queues/accounts or change that behavior.

## Where it is saved

Configuration lives at `${XDG_CONFIG_HOME:-$HOME/.config}/hpc-workspace/config.json`. `WS_CONFIG_DIR` can select a separate local configuration directory, for example when multiple systems share a home. Personal dotfiles still live at `~/.config/hpc-workspace`; changing `WS_CONFIG_DIR` does not move them.

Imported facts and personal `overrides` are separate. Explicit overrides survive refresh. `ws init --scheduler pbs` or `--scheduler slurm` can store a scheduler default without a profile; this is optional and is not required to call a native client. An explicit `--site` selects a saved/built-in label for one invocation; daily use does not require typing Ruth, Jean, or Blueback.

Most mounts come from automatic integration. If an extra ordinary bind is needed, merge a `binds` list into the existing configuration's `overrides`, using actual local paths:

```json
{
  "binds": [
    {"source": "/path/to/shared-data", "destination": "/path/to/shared-data", "mode": "rw"}
  ]
}
```

This is an **overrides fragment**, not a replacement `config.json`. Use `ro` for read-only access. Inspect the result with `ws enter --dry-run` before starting a new shell. Protected image/system integration paths cannot be replaced by this override.

The older `profiles/SITE.local.json` format is still recognized, with precedence over saved overrides, but editing release-owned source is not needed for the current workflow. `scheduler_env` is retained for the older limited submit/jobs bridge; ordinary native commands do not use that bridge's environment allowlist. The [0.4 workflow](legacy/core-workflow.md) records that historical behavior.

## Import implementation and state

The host launcher snapshots the chosen YAML locally and passes it read-only to the selected image's bundled PyYAML reader. It receives normalized JSON, validates the consumed fields, and saves private configuration atomically. Unsupported schemas, malformed/unsafe YAML, duplicate keys, and excessive/recursive aliases are rejected. Profile strings are data, not executable setup commands. Normal startup needs only the host Python standard library.

Existing state is preserved through the saved `state_site` choice; `--state-dir` is an explicit invocation override. The profile's recorded path/hash/import time explains which file was consumed, not whether the system has since been rescanned. The [contract research](research/cluster-inspector-contract.md) and [validation record](validation.md) document the public source review and synthetic tests.
