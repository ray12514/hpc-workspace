# Workspace validation

## Explicit dotfiles: 0.4.0-preview1

Date: **2026-09-22**. Built locally for Linux amd64. Core tool versions and package pins are unchanged. No cluster access, private configuration, AI authentication, or live scheduler submission was used.

- **Automated checks:** all **42 tests pass in Linux** with a read-only root, no network, and no capabilities. The macOS host passes 38 and skips four Linux peer-credential tests. The added checks cover preservation of edited files and dangling symlinks, private file permissions, and complete-file publication during simultaneous first entries.
- **Real applications:** non-root Docker runs use a read-only image and replace the container between phases. Personal Bash, Readline, Neovim, bat, and Git preferences survive, application configuration is writable, normal host Bash/Neovim files are not sourced, and Git still reads the user's normal identity configuration. Real tmux loads the personal override and preserves its existing layout save/restore behavior.
- **Interactive shell:** an actual non-root Bash PTY opens fzf with Ctrl-R, selects a synthetic history command without executing it, and completes `git chec` to `git checkout` with Tab. Existing prompt/color fallbacks and Neovim theme checks pass. Ctrl-T and Alt-C are provided by the same packaged binding script; their full picker interactions are not separately automated.
- **Source consistency:** all 27 shipped configuration, launcher, helper, and generic profile files match this checkout byte-for-byte. Maintained shell scripts pass ShellCheck. All seven host Python files parse with Python 3.6 syntax rules; an actual Python 3.6 interpreter was not tested.
- **Delivered SIF:** real Apptainer **1.3.6 and 1.5.3** runs pass as UID 1000 in `--unsquash` mode. Both verify writable application configuration and a retained personal Neovim preference after re-entry. The full launcher flow also checks an alternate host home: container `HOME` matches the explicit bind, and dotfiles are created there. Existing tool checks, synthetic PBS/Slurm host connections, and Inspector import/save/refresh checks pass under both versions.

The SIF is **628,187,136 bytes** (about **599.1 MiB**), unencrypted, with gzip SquashFS. These are local extracted-SIF checks. Normal SIF mounting and actual site scheduler, GPU, and MPI behavior remain local validation work; the Docker Desktop nested-mount limitation recorded below still applies.

## Optional Inspector configuration: 0.3.0-preview1

Date: **2026-09-22**. Built locally for Linux amd64. The image adds Ubuntu snapshot package `python3-yaml` **6.0.1-2build2** for the import helper; the existing core tools retain their pins. No cluster connection, real cluster profile, AI authentication, or live scheduler submission was used.

- **Automated checks:** all **40 tests pass in Linux** with a read-only root, no network, and no capabilities. The macOS host passes 36 tests and skips four Linux peer-credential tests. The 16 new checks cover initial import, optional/missing facts, PBS/Slurm defaults, explicit overrides, first-entry image/state preservation, cached startup without the source YAML or Inspector, concurrent edits, explicit refresh, and invalid/renamed-profile rejection.
- **YAML handling:** actual YAML parsing checks typed provider paths, modules, and node facts. Unsafe tags, duplicate keys, recursive aliases, malformed input, and unsupported versions are rejected. Imports snapshot the source, use the image's parser, and write private configuration atomically. Host launcher syntax was also checked against Python 3.6.
- **Delivered SIF:** real nested Apptainer **1.3.6 and 1.5.3** runs pass in `--unsquash` mode. Each tests initial import and preview through the SIF's reader, image selection, entry after deleting the original YAML, saved PBS/Slurm defaults, successful refresh, and preservation after a failed refresh. Existing SIF tool checks and actual container-to-host connections to synthetic PBS/Slurm clients also pass.
- **Existing daily environment:** the Docker checks pass tool/C/Python smoke tests, preservation of files/history/editor state/custom skills after replacing the container, tmux save/restore, Bash PTY colors/literal names, and Neovim theme modes. Submission export behavior is unchanged.
- **Source consistency:** the seven delivered launcher/library/entry files match the source byte-for-byte. Maintained shell scripts pass ShellCheck. The public documentation cites the public profile schema; the private implementation review and all build logs remain outside the release.

The SIF is **628,166,656 bytes** (about **599.1 MiB**), unencrypted, with gzip SquashFS. These are local extracted-SIF checks, not a claim that direct SIF mounting, scheduler authentication, GPU toolkits, or MPI communication have been validated on the target clusters. The previously recorded Docker Desktop nested-mount limitation still applies. Site checks remain local to those machines.

## Daily workflow: 0.2.0-preview1

Date: **2026-09-22**. Built locally for Linux amd64. Core tool versions and package pins are unchanged from the baseline table below. No cluster connection, private cluster files, AI authentication, or live job submission was used.

- **Launcher/scheduler:** all 24 tests pass in the Linux image as an ordinary user with a read-only root, no network, and no capabilities. The macOS host passes the 20 applicable tests; four Linux peer-credential tests are skipped there. Native-client fixtures cover PBS and Slurm, literal paths and arguments, working directory, selected host environment, explicit job variables, native job IDs/errors, dry-run behavior, and container fallback rejection.
- **Local submission connection:** Linux tests exercise actual Unix sockets and peer credentials, private directory/socket permissions, the container CLI, wrong-site/operation rejection, symlink escape rejection, malformed requests, four-request capacity, immediate busy errors, and cleanup. These tests use synthetic scheduler executables, not PBS/Slurm servers.
- **Terminal appearance:** real Bash PTYs pass 256-color, true-color, `NO_COLOR`, `WS_COLOR=never`, and `TERM=dumb` cases, including site/node/job labels and nonzero exit status. Path and branch names containing shell syntax render literally without executing it. Headless Neovim verifies the theme's 256-color highlights, true-color setting, and opt-out.
- **Existing behavior:** offline tool/C/Python smoke checks, replacement of the container with persistent files/history/editor state, preservation of independent skills, and real tmux save/restore all pass. Tmux restores shells; process replay remains disabled.
- **Build consistency:** the 12 delivered launcher, profile, theme, and entry files have the same SHA256 hashes as their source files. Maintained shell scripts pass ShellCheck. Host Python modules parse with Python 3.6 syntax rules; an actual Python 3.6 interpreter was not tested.
- **SIF:** the new gzip SquashFS SIF passes real tool smoke checks under **Apptainer 1.3.6 and 1.5.3**, using `--unsquash` as UID 1000. Under each version, inner-container `ws submit` and `ws jobs` reach synthetic PBS and Slurm clients on the outer host through the bound Unix socket. Tests verify script paths containing spaces and shell syntax, working directory, host environment selection, explicit input values, native failure status/stderr, and socket cleanup. The native scheduler clients are absent from the image PATH. There is no network access in these fixtures.

The fixtures establish the portable implementation, not a site's scheduler authentication, account/queue settings, client plugin dependencies, or production filesystem policy. The optional connection requires a permitted bind-mounted Unix socket and Linux peer credentials on the login host. Site-only client settings can be added to a local profile. Keep all actual cluster validation results local.

The first image was reported by the user to start on a target system. No detailed site report was requested or transmitted, and that report does not validate this update. The Docker Desktop direct nested SIF-mount limitation described below remains applicable; extraction tests do not establish native SIF mounting on each target. GPU stacks, MPI, interconnects, and distributed runtime validation remain outside this phase.

## Baseline: 0.1.0-preview1

Release: **0.1.0-preview1**, core, Linux amd64. Date: **2026-09-21**.

The workspace was built and exercised locally using Docker Desktop's native x86_64 Linux engine (`6.12.76-linuxkit`). No cluster was contacted, and no non-public cluster inventory, files, or credentials were used. Ruth/Jean/Blueback execution, GPU toolkits, MPI, interconnects, and live scheduler queries remain site-local validation work.

### Delivered image

| Component | Observed version |
| --- | --- |
| Ubuntu userspace | 24.04.5 LTS |
| glibc | 2.39 |
| Neovim | 0.12.5 |
| tmux | 3.4 |
| Node | 24.21.0 |
| Python | 3.12.3 |
| GCC | 13.3.0 |
| Codex | 0.155.1 |
| Claude Code | 2.1.278 |

Base-image digests, npm lock entries, and checked upstream assets are in `image/`. The installed Debian-package list, npm dependency tree, Node version, and asset lock are also stored inside the image under `/opt/workspace/manifests` and exported with the release.

### Passing checks

- **Host launcher:** 10 automated tests covering literal command arguments and paths containing spaces; dry-run without state writes or secret values; scheduler-specific allocation requirements; GPU-mask forwarding; isolation from inherited Apptainer injection variables; PBS/Slurm command selection; checksum-verified selection/update/rollback; detection of replaced images; compute-node session rejection; and protected bind destinations.
- **Offline Docker execution:** real core tools run with UID/GID 501:20, a read-only image, no network, all capabilities dropped, and no-new-privileges. Neovim configuration loads, both AI clients report their pinned versions, Python creates and uses a virtual environment, and GCC compiles and executes a C program from writable state. No AI authentication or API request is performed.
- **Replacement/persistence:** a second container reuses the same disposable home/project/state. Project contents, shell history, a two-window Neovim layout, installed skills, and an existing custom skill survive. The custom skill is preserved rather than replaced.
- **Tmux recovery:** the actual configured tmux server saves its windows; a new server restores them. Restored panes run shells, with process replay disabled. Snapshot paths and detach-save hooks are configured, and each workspace gets its own server/state location.
- **SIF conversion:** a standard, unencrypted, gzip SquashFS SIF is built from the Docker archive by pinned Apptainer 1.5.3. Conversion succeeds in an ordinary Docker container with no network, no privileged mode, and no Docker socket.
- **SIF execution after extraction:** the same SIF runs the real tool, Python-venv, skill, and C compilation smoke checks under both **Apptainer 1.3.6 and 1.5.3**, as UID/GID 1000:1000. The local fixture uses `--unsquash`, disposable writable binds, no network, and Docker namespace/extraction permissions.
- **Static checks:** ShellCheck for maintained shell scripts and Python compilation checks. Vendored skill/plugin files retain upstream contents.

### Exact limit of the runtime result

Direct execution from a nested SIF/FUSE mount failed under both runtimes on this Docker Desktop VM: Linux returned `EINVAL` from `execve("/bin/true", ...)`. The image had mounted and reached its final program launch. Relaxing Docker system-path restrictions alone did not change that result.

The extracted SIF passed. External extraction also showed that `/usr/bin/true` and its ELF interpreter have identical SHA256 hashes in the SIF and the working Docker image. A syscall trace ruled out Go rejecting a malformed argument/environment before execution. The failure is isolated to the local mounted-execution path; the exact kernel/FUSE mechanism is not established.

Accordingly, the release demonstrates working core image contents and Apptainer execution **through extraction**, not successful native SIF mounting on the target clusters. The host `ws` launcher keeps normal SIF execution as its default. Check that normal path locally on each cluster before adopting the release there. Nothing in this result establishes GPU-driver, MPI ABI, fabric, or scheduler integration.

`scripts/test-sif` defaults to the passing extraction fixture. `WS_SIF_TEST_MODE=mount ./scripts/test-sif` reproduces the direct-mount check on a suitable Linux Docker host. Local test permissions (`seccomp=unconfined`, `systempaths=unconfined`, and FUSE when testing mount mode) belong to these disposable Docker fixtures; they are not deployment instructions for HPCMP.

See the [focused investigation](research/nested-runtime-check.md) for primary-source references. Full local build/test logs are retained under ignored `build/`; release artifacts and checksums are under ignored `dist/`. The portable source bundle contains this result and the test scripts.
