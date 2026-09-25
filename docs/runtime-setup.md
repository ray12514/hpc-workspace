# Remembered Apptainer setup

Implemented in **0.7.0-preview1**. The native installer discovers and checks an available Apptainer during installation/update, then saves the working invocation locally. Daily launch checks the saved paths and applies any required module setup; it does not run version probes or a separate container self-test.

On a module-based system, load its normal Apptainer module once before installation. Setup tests whether the absolute executable path can run the workspace image from a fresh environment. If so, later launches use that path directly. An administrator-maintained executable symlink is retained rather than replaced by its resolved version path.

If the executable needs more setup, discovery uses an unambiguous loaded Apptainer/Singularity module name and an available initialization file. It loads that module in a child Bash process and checks real image execution. Only the module name, initialization path, executable path, image path, and validation time are saved. It does not copy libraries or retain the whole module environment.

If automatic discovery needs help, run this from the **native host shell**:

```bash
ws runtime setup
ws runtime status
```

Explicit local choices are available:

```bash
ws runtime setup --apptainer /path/to/apptainer --module apptainer/site-version --module-init /path/to/modules/init/bash
```

Use actual site paths and module names. `--image FILE.sif` selects another image for validation. This command does not install a runtime or cluster module.

An installation can finish before Apptainer is available. It reports that runtime setup remains necessary; load the module and run `ws runtime setup` once. An update started inside the workspace defers host validation to that command in the native shell. A failed check preserves prior runtime settings and reports the next step.

Launches prefer an explicit `WS_APPTAINER` executable, then a different Apptainer currently selected on PATH, then the saved invocation. When PATH names the recorded executable, its saved module recipe still applies. Module loading is scoped to the child runtime and does not change the parent login shell. Missing executable or initialization paths produce an actionable error.

Runtime records live in `runtime.json` under the normal workspace configuration directory. Inspector system labels scope records; the initial `local` record can be reused after the first import. If different clusters share a home but need distinct settings, use their existing local `WS_CONFIG_DIR` setup. A shared home does not establish identical runtimes on every node.

Public tests use synthetic modules and local Apptainer fixtures. Unusual module initialization, node differences, privilege modes, and normal SIF mounting still need site-local verification. Runtime paths and metadata belong on their originating system.
