# Apptainer provided by a site module

Status: **design for the next runtime setup improvement; not implemented in 0.6.1 or the current `./setup`.** No site module was accessed for this design. Runtime paths, module contents, and validation results belong only in local configuration on that system.

## Current behavior

`./setup` can download and install the release without Apptainer. When starting the workspace, the launcher currently resolves `apptainer` from PATH. On a system where the runtime is module-provided, load the site's normal Apptainer module before `ws enter`, `ws session`, or an Inspector import needing the image reader. Use the module name actually supplied by the site.

The workspace does not yet remember that executable path or automatically load its module. A working session does not establish that the same command will be available after the next login.

## Desired behavior

During initial installation/runtime setup and explicit updates, discover Apptainer's absolute command path and record it privately with the relevant local system/runtime configuration. Preserve an administrator-maintained command symlink when appropriate, rather than unnecessarily fixing the path to its current target. If installation happens before the runtime is available, perform this once when the runtime is first configured.

Do module inspection and a real workspace-image execution check at those setup/update points. Daily launch reuses the saved configuration with only a cheap path-exists/executable guard on the current node. It should not rerun discovery, version probes, or a separate container self-test on every login or entry. Applying required module settings at launch is separate from discovering and validating them.

There are two cases:

| Module behavior | What to retain | Later workspace launch |
| --- | --- | --- |
| Only adds a usable executable directory | Absolute executable path and validation metadata | Invoke that path directly without a module load |
| Supplies required environment, helpers, or configuration | Executable plus the approved module name/initialization method | Load the module automatically for the runtime invocation only |

Prefer evaluating the site's module when it is needed over freezing a copy of its full environment. Module changes can include library/helper paths and runtime settings, and administrators can update them. The workspace should not copy Apptainer's libraries, save unrelated compiler/MPI state, or retain credentials just to remember how to start a container.

No module evaluation is needed at ordinary login. Any required loading belongs to the workspace launch, scoped to its runtime process rather than permanently changing the user's parent shell. A caller's explicitly selected available runtime should have a clear precedence over an old cached discovery. Missing/changed installations should trigger rediscovery or an actionable local message; never silently keep using a vanished version.

## Verification before calling it supported

Inspect the actual module locally and test a fresh shell without the module already loaded. A successful `apptainer version` check is useful but insufficient: test execution of the selected workspace image too, because helpers, configuration, mounts, and privilege modes can matter only at exec time.

Cover normal PATH installs, a module that only changes PATH, a module requiring extra setup, a changed/removed version, fresh login, and compute-node startup. A shared home does not imply identical runtimes across different clusters; local configuration must stay scoped to the appropriate system and executable availability must be checked on the current node.

This belongs in automated runtime initialization alongside [setup](thin-start.md), not in a repeated manual step in the [daily workflow](daily-workflow.md). Until implemented and verified, current instructions continue to use the site's normal module setup.

An optional [configuration form](guided-configuration.md) can expose the saved choices later. Initial setup must still work through ordinary host prompts or command-line options before Apptainer can launch the image; a form tool packaged only inside the SIF cannot bootstrap its own runtime.
