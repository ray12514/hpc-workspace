# Baseline validation

Release: **0.1.0-preview1**, core, Linux amd64. Date: **2026-09-21**.

The workspace was built and exercised locally using Docker Desktop's native x86_64 Linux engine (`6.12.76-linuxkit`). No cluster was contacted, and no non-public cluster inventory, files, or credentials were used. Ruth/Jean/Blueback execution, GPU toolkits, MPI, interconnects, and live scheduler queries remain site-local validation work.

## Delivered image

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

## Passing checks

- **Host launcher:** 10 automated tests covering literal command arguments and paths containing spaces; dry-run without state writes or secret values; scheduler-specific allocation requirements; GPU-mask forwarding; isolation from inherited Apptainer injection variables; PBS/Slurm command selection; checksum-verified selection/update/rollback; detection of replaced images; compute-node session rejection; and protected bind destinations.
- **Offline Docker execution:** real core tools run with UID/GID 501:20, a read-only image, no network, all capabilities dropped, and no-new-privileges. Neovim configuration loads, both AI clients report their pinned versions, Python creates and uses a virtual environment, and GCC compiles and executes a C program from writable state. No AI authentication or API request is performed.
- **Replacement/persistence:** a second container reuses the same disposable home/project/state. Project contents, shell history, a two-window Neovim layout, installed skills, and an existing custom skill survive. The custom skill is preserved rather than replaced.
- **Tmux recovery:** the actual configured tmux server saves its windows; a new server restores them. Restored panes run shells, with process replay disabled. Snapshot paths and detach-save hooks are configured, and each workspace gets its own server/state location.
- **SIF conversion:** a standard, unencrypted, gzip SquashFS SIF is built from the Docker archive by pinned Apptainer 1.5.3. Conversion succeeds in an ordinary Docker container with no network, no privileged mode, and no Docker socket.
- **SIF execution after extraction:** the same SIF runs the real tool, Python-venv, skill, and C compilation smoke checks under both **Apptainer 1.3.6 and 1.5.3**, as UID/GID 1000:1000. The local fixture uses `--unsquash`, disposable writable binds, no network, and Docker namespace/extraction permissions.
- **Static checks:** ShellCheck for maintained shell scripts and Python compilation checks. Vendored skill/plugin files retain upstream contents.

## Exact limit of the runtime result

Direct execution from a nested SIF/FUSE mount failed under both runtimes on this Docker Desktop VM: Linux returned `EINVAL` from `execve("/bin/true", ...)`. The image had mounted and reached its final program launch. Relaxing Docker system-path restrictions alone did not change that result.

The extracted SIF passed. External extraction also showed that `/usr/bin/true` and its ELF interpreter have identical SHA256 hashes in the SIF and the working Docker image. A syscall trace ruled out Go rejecting a malformed argument/environment before execution. The failure is isolated to the local mounted-execution path; the exact kernel/FUSE mechanism is not established.

Accordingly, the release demonstrates working core image contents and Apptainer execution **through extraction**, not successful native SIF mounting on the target clusters. The host `ws` launcher keeps normal SIF execution as its default. Check that normal path locally on each cluster before adopting the release there. Nothing in this result establishes GPU-driver, MPI ABI, fabric, or scheduler integration.

`scripts/test-sif` defaults to the passing extraction fixture. `WS_SIF_TEST_MODE=mount ./scripts/test-sif` reproduces the direct-mount check on a suitable Linux Docker host. Local test permissions (`seccomp=unconfined`, `systempaths=unconfined`, and FUSE when testing mount mode) belong to these disposable Docker fixtures; they are not deployment instructions for HPCMP.

See the [focused investigation](research/nested-runtime-check.md) for primary-source references. Full local build/test logs are retained under ignored `build/`; release artifacts and checksums are under ignored `dist/`. The portable source bundle contains this result and the test scripts.
