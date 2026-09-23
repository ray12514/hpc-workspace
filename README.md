# HPC workspace

One centrally maintained development environment for Linux HPC systems. Build the tools and dotfiles once, transfer a release, and use the same development shell on each system while retaining its normal files, modules and commands.

**0.5.0-preview1 is the first integrated thin-image implementation.** It packages the development tools in a pinned Nix store, automatically brings the host userspace into the container, and supplies a repeatable installer, update operation and rollback. The first targets remain Ruth (PBS), Jean (Slurm), and Blueback (Slurm); no cluster access or private inventory is needed to build the release.

[Install and use the preview](docs/thin-start.md) · [Release downloads](https://github.com/ray12514/hpc-workspace/releases/tag/v0.5.0-preview1) · [Validation and limitations](docs/validation.md)

## Daily workflow

After installing the transferred release, work from your project directory:

```bash
ws enter          # one integrated development shell
ws session        # the same environment in packaged tmux
```

Use ordinary site commands such as `module`, `sbatch`, and `qsub` from that shell. Your existing native job scripts retain their usual role. Enter the workspace within an interactive allocation when you want its tools on the allocated node.

The first thin tool set is Bash, Neovim, tmux, bat, fzf, fd, ripgrep, jq, eza, zoxide, less and terminal support. It includes the common prompt, history/path shortcuts, completion, editor defaults and personal overrides. The package set is locked in [flake.lock](image/nix/flake.lock); runtime dependencies ship in the image. No Nix installation or toolbox compilation is needed on the hosts.

This preview establishes the integration and delivery foundation. Adding the full agent/compiler inventory and further custom tools is the next toolkit iteration. Existing host programs remain available. The earlier [0.4 core image](https://github.com/ray12514/hpc-workspace/releases/tag/v0.4.0-preview1) and its [instructions](docs/transfer.md) remain available.

## One release across systems

Transfer the SIF, matching source bundle, standalone installer, and release manifest. Run the same installer on each system. It checks the files, installs the matching launcher, adds its Bash PATH hook, and selects the release. Local filesystem integration is generated automatically; optional existing Inspector facts and personal settings remain local.

For later releases:

```bash
ws update /path/to/release-VERSION.json
ws rollback
```

Updates preserve personal files and state. Existing sessions keep their original image; new sessions use the selected release. The [startup guide](docs/thin-start.md) includes exact filenames and commands.

## Implementation and validation

- [Integrated-container implementation plan](docs/thin-container-plan.md)
- [Development-environment requirements](docs/workflow-options.md)
- [Toolkit roadmap](docs/toolkit-roadmap.md) and [dotfile conventions](docs/dotfiles.md)
- [Optional Inspector import](docs/inspector-integration.md)
- [Local validation record](docs/validation.md)
- [Reported startup/library errors](docs/troubleshooting-startup.md)

The thin container preserves the image-owned store and tools while mounting the host OS/program directories coherently. Its tools have private library paths, and native commands retain the host/module environment. Filesystem visibility, authentication, MPI, GPUs, and starting other container engines are distinct compatibility checks; their site-specific results stay on the originating systems.

## Build locally

Docker supplies the Linux builder on the workstation:

```bash
scripts/build-thin 0.5.0-preview1
scripts/export-thin 0.5.0-preview1
scripts/test-thin dist/hpc-workspace-thin-0.5.0-preview1-linux-amd64.sif
scripts/package-thin 0.5.0-preview1
scripts/test-thin-install dist/release-0.5.0-preview1.json
```

Packaging requires a clean committed source tree and an image built from that commit. The manifest connects the source commit, Docker image identity, Nix lock, and artifact checksums. No registry is required for SIF transfer.

The default local test uses real Apptainer 1.5.3 with an extracted SIF inside a disposable Debian container. The suite also runs with Apptainer 1.3.6 and a public Ubuntu fixture. Those tests do not establish normal SIF mounting or live cluster integration on Ruth, Jean, or Blueback.
