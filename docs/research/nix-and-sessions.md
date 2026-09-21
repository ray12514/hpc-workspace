# Packaging and session persistence

Research date: 21 September 2026. These findings support a proposed design, not a claim of validation on any cluster.

## Nix's role

Nix can define a consistent package set, but a conventional installation is an additional host requirement: even the single-user installer needs a suitable `/nix` directory, normally created with elevated privileges. This does not mean rootless alternatives are impossible; it means we should not make an untested host installation a prerequisite on the three pilot systems. [Nix installation manual](https://nix.dev/manual/nix/2.34/installation/installing-binary.html)

Nix can instead be confined to the image builder. Its `dockerTools` functions produce Docker-compatible images, including package dependencies, without using Docker to perform the build. That makes it a possible later replacement for the package-install layer while keeping the same deployment interface. [Nixpkgs image builders](https://nixos.org/manual/nixpkgs/stable/#sec-pkgs-dockerTools)

**Recommendation:** begin with a version-controlled Dockerfile and pinned inputs on a Linux builder. Deploy a versioned Apptainer SIF. Introduce Nix at build time if maintaining the package set warrants its additional complexity. Neither approach removes GPU-driver or MPI compatibility requirements.

Apptainer supports building from OCI registries and saved Docker archives and produces a compressed, read-only SIF by default. An image is therefore a suitable unit for distribution, rollback, and offline staging. Building and converting on a separate Linux machine avoids depending on cluster build privileges or namespace configuration. [Apptainer build guide](https://apptainer.org/docs/user/latest/build_a_container.html)

Pinning an image digest gives a fixed runtime artifact; it does not by itself make future rebuilds identical. Rebuilds also need recorded package versions, source hashes, base image digests, plugin revisions, and stable package sources. Record both the OCI digest and the distributed SIF checksum.

## What can be resumed

tmux separates clients from a server process and preserves sessions across a detached or disconnected client. Its server and socket still belong to one host. A shared filesystem does not make the process migrate between hosts. [tmux manual](https://man.openbsd.org/tmux.1)

`tmux-resurrect` records sessions, windows, panes, layouts, working directories, and a controlled list of commands. Its restore mechanism starts programs again. It is not a checkpoint of arbitrary process memory. `tmux-continuum` adds periodic saves and optional restore when the tmux server starts. [Resurrect](https://github.com/tmux-plugins/tmux-resurrect), [command restoration](https://github.com/tmux-plugins/tmux-resurrect/blob/master/docs/restoring_programs.md), [Continuum](https://github.com/tmux-plugins/tmux-continuum)

Neovim restoration requires an editor-session mechanism as well; Resurrect documents an integration that loads an existing `Session.vim`. Preserve file contents separately: restoring a session is not a substitute for saving buffers. [Editor integration](https://github.com/tmux-plugins/tmux-resurrect/blob/master/docs/restoring_vim_and_neovim_sessions.md)

The proposed design should handle four events differently:

| Event | Expected behavior |
| --- | --- |
| Laptop disconnects; login host remains alive | Reconnect to the same host and attach to the existing tmux server. |
| Interactive compute allocation ends | Login workspace remains; compute processes stop. Preserve editor state, job records, output, and application checkpoints on persistent storage. |
| Login host restarts | Start a new server and restore layout, directories, and approved editor commands from saved state. |
| Move to another login host or cluster | Recreate the workspace from a portable project recipe; remap paths and obtain any needed allocation. Running processes do not move with the recipe. |

**Recommendation:** put the main tmux server on an approved stable login host, outside the interactive compute allocation. Use panes for the container editor, host scheduler commands, logs, and a compute shell. When host tmux is unsuitable, test a long-lived base-container tmux server with an explicit local socket path, using the same image release for its clients. Do not rely on a tmux server inside a disposable compute allocation for durable state.

Save one workspace recipe per project and separate automatic snapshot directories per cluster, host, and session to prevent concurrent writers overwriting each other's latest save. Keep sockets on host-local storage. Snapshot useful metadata onto persistent storage; do not use purgeable scratch as the only copy. Prefer explicit restoration on a different host so a remembered command cannot silently submit a duplicate job. Generic restores should not rerun `qsub`, `sbatch`, `srun`, or `mpirun`.

## Files and environment

Apptainer binds can select read/write or read-only access, and default mounts can be disabled or replaced. Binding a home directory hides files at the same container path; keep shipped editor and shell defaults under a stable image path such as `/opt/workspace`, rather than baking them into a build user's home. [Bind paths and mounts](https://apptainer.org/docs/user/latest/bind_paths_and_mounts.html)

For daily tools, use a deliberate environment with selected user overrides. Apptainer documents how inherited host variables, including those from environment modules, can affect container tools. Its `--cleanenv`, explicit environment variables, and path controls provide building blocks. MPI launch needs its own tested environment policy because scheduler and fabric settings may have to be preserved. [Environment guide](https://apptainer.org/docs/user/latest/environment_and_metadata.html)

Recommended persistent data: projects, user configuration, skills, editor history, conversation state, job IDs, and logs. Recommended disposable data: download/build caches and temporary files where the site allows them. Partition compiled caches and virtual environments by architecture, image/toolchain release, and site MPI integration as appropriate.
