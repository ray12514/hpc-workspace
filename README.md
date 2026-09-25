# HPC workspace

One centrally maintained development environment for Linux HPC systems. Build the tools and dotfiles once, transfer a release, and use the same development shell on each system while retaining its normal files, modules and commands.

**0.7.0-preview1 adds Gum configuration forms, named API gateway profiles, private credential updates, and remembered Apptainer setup.** It retains the CLI/AI toolkit, Neovim/Treesitter, locale support, and tmux exit fix from 0.6.1. It packages the development tools in a pinned Nix store, automatically brings the host userspace into the container, and supplies a repeatable installer, update operation and rollback. The first targets remain Ruth (PBS), Jean (Slurm), and Blueback (Slurm); no cluster access or private inventory is needed to build the release.

[Install/update](docs/thin-start.md) · [Daily workflow tutorial](docs/daily-workflow.md) · [Command reference](docs/command-reference.md) · [All documentation](docs/README.md) · [Release downloads](https://github.com/ray12514/hpc-workspace/releases/tag/v0.7.0-preview1)

## Get the current release

From your normal Linux login shell, clone this repo and run **`./setup`**:

```bash
git clone https://github.com/ray12514/hpc-workspace.git
cd hpc-workspace
./setup
```

Already have the checkout? Install or update with one command from that directory:

```bash
git pull --ff-only && ./setup
```

`setup` downloads and verifies the recommended release's SIF, source bundle, manifest, and matching installer, then installs them together. **It does not need an existing `ws` command**, so this also works from 0.5 or when only the skills directory exists. No version numbers, individual download commands, or manual extraction are needed. Verified downloads are reused and interrupted downloads can resume. Python 3.6+ and either curl or wget are required; there is no build or GitHub login step.

After setup finishes, open a new Bash session and run `ws enter`. For a site-specific Bash startup file, use `./setup --shell-startup /path/to/your/startup-file`; the installer remembers that choice. To download on another machine for offline transfer, see the [startup guide](docs/thin-start.md#download-elsewhere-and-transfer).

## Daily workflow

After installing the release, work from your project directory:

```bash
ws enter          # one integrated development shell
# Or, from the native shell:
ws session        # enter the environment in managed, packaged tmux
```

Start with the [daily workflow tutorial](docs/daily-workflow.md), including a copyable practice project. It walks through navigation, Ctrl-R/Ctrl-T, `find`/`fd` + `fzf` + `bat`, ripgrep, Neovim, Git review, project checks, job scripts, and saving your work. Keep the [command reference](docs/command-reference.md) alongside it for quick lookup.

Use ordinary site commands such as `module`, `sbatch`, and `qsub` from that shell. Your existing native job scripts retain their usual role. Enter the workspace within an interactive allocation when you want its tools on the allocated node.

The shell foundation is Bash, Neovim, tmux, bat, fzf, fd, ripgrep, jq, eza, zoxide, less and terminal support. It includes the common prompt, history/path shortcuts, completion, editor defaults and personal overrides. The package set is locked in [flake.lock](image/nix/flake.lock); runtime dependencies ship in the image. No Nix installation or toolbox compilation is needed on the hosts.

This preview includes Codex and Claude Code, the expanded CLI toolkit, and a preconfigured Neovim/Treesitter bundle. See the [editor, agents, and interactive-job guide](docs/editor-and-agents.md). Use the site's existing compilers through its normal module environment; bundle a compiler only when a concrete workflow needs a specific version that the site does not provide. Existing host programs remain available. The earlier [0.4 core image](https://github.com/ray12514/hpc-workspace/releases/tag/v0.4.0-preview1) and its [instructions](docs/transfer.md) remain available.

Inside the workspace, `ws configure` opens the configuration menu. Use `ws configure codex team-a` or `ws configure claude team-a` to create a named API gateway, update its settings, rotate its key, or choose a default. Start it with `ws agent codex team-a` or `ws agent claude team-a`. See the [gateway guide](docs/agent-profiles.md) for credential storage, protocol requirements, and basic terminal prompts.

## One release across systems

Run `./setup` from the updated checkout on each system. It checks the files, installs the matching launcher, adds its PATH hook to ordinary Bash startup and the active Bash login profile, and selects the release. After setup, log in normally and run `ws enter`; manual activation is only needed to use an already-open terminal immediately after installation. Local filesystem integration is generated automatically; optional existing Inspector facts and personal settings remain local.

For later releases:

```bash
git pull --ff-only && ./setup
```

Updates preserve personal files and state. Existing sessions keep their original image; new sessions use the selected release. Use `ws rollback` to select the previous installed release. `ws update /path/to/release-VERSION.json` remains available for bundles transferred separately. The [startup guide](docs/thin-start.md) covers offline transfer and custom installation locations.

## Implementation and validation

- [Integrated-container implementation plan](docs/thin-container-plan.md)
- [Development-environment requirements](docs/workflow-options.md)
- [Toolkit roadmap](docs/toolkit-roadmap.md) and [dotfile conventions](docs/dotfiles.md)
- [Agent configuration and gateway profiles](docs/agent-profiles.md)
- [Remembered Apptainer setup](docs/runtime-setup.md)
- [Optional Inspector import](docs/inspector-integration.md)
- [Local validation record](docs/validation.md)
- [Reported startup/library errors](docs/troubleshooting-startup.md)

The thin container preserves the image-owned store and tools while mounting the host OS/program directories coherently. Its tools have private library paths, and native commands retain the host/module environment. Filesystem visibility, authentication, MPI, GPUs, and starting other container engines are distinct compatibility checks; their site-specific results stay on the originating systems.

## Build locally

Docker supplies the Linux builder on the workstation:

```bash
scripts/build-thin 0.7.0-preview1
scripts/docker-public build -f image/Apptainer.Dockerfile \
  -t hpc-workspace-apptainer:1.5.3 .
scripts/export-thin 0.7.0-preview1
# Prepare the public Linux acceptance fixture (Apptainer plus native Git).
scripts/docker-public build --target native -f tests/ThinTools.Dockerfile \
  -t hpc-workspace-test-native:1.5.3 .
scripts/test-thin dist/hpc-workspace-thin-0.7.0-preview1-linux-amd64.sif
scripts/package-thin 0.7.0-preview1
scripts/test-thin-install dist/release-0.7.0-preview1.json
```

Packaging requires a clean committed source tree and an image built from that commit. The manifest connects the source commit, Docker image identity, Nix lock, and artifact checksums. No registry is required for SIF transfer.

After publishing and validating a release, update [releases/recommended.json](releases/recommended.json) with its version and published manifest's SHA-256, then commit and push that recommendation. `./setup` uses this checked-in recommendation, including preview releases, rather than GitHub's stable-only "latest" selection. Downloaded code is verified against that manifest before execution. Updating this host-side setup command does not require rebuilding the SIF.

The default local test uses real Apptainer 1.5.3 with an extracted SIF inside a disposable Debian container. A fixture argument selects another runtime/host combination; the validation record identifies which combinations were exercised for each release. These tests do not establish normal SIF mounting or live cluster integration on Ruth, Jean, or Blueback.

For faster configuration iteration, build `tests/ThinTools.Dockerfile` as `hpc-workspace-toolkit-fixture`, then run `scripts/test-configuration`. It drives the real forms and packaged agents against a loopback-only synthetic gateway with external networking disabled.
