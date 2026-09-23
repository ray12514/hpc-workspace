# Install the integrated development environment

The **0.5.0-preview1** thin release implements the first working foundation: one development shell, centrally built Nix tools and dotfiles, automated host filesystem/environment integration, and an offline install/update path. Site-local facts and results stay on the system. The larger tool catalog is still being expanded.

## Transfer and install

Download these four assets from the [preview release](https://github.com/ray12514/hpc-workspace/releases/tag/v0.5.0-preview1), together with their checksum files, and transfer them through the usual approved route:

- `hpc-workspace-thin-0.5.0-preview1-linux-amd64.sif`
- `hpc-workspace-source-0.5.0-preview1.tar.gz`
- `install-workspace-0.5.0-preview1.py`
- `release-0.5.0-preview1.json`

Keep the four files in the same directory. After verifying the downloaded checksums, run the same command on each system:

```bash
python3 install-workspace-0.5.0-preview1.py release-0.5.0-preview1.json
```

The installer verifies the SIF and source checksums, installs a versioned copy under `~/.local/share/hpc-workspace/runtime`, and selects it atomically. It adds a managed PATH block to `.bashrc`, preserving the rest of that file. Repeating installation is safe. `--prefix DIRECTORY` selects another persistent location; `--no-shell-hook` leaves shell startup files alone.

Open a new Bash session, or activate the newly installed launcher immediately:

```bash
source "$HOME/.local/share/hpc-workspace/runtime/activate.sh"
ws enter
```

Use a host with Python 3.6+ and the site's Apptainer 1.3.6 or newer available through its normal setup. Nix is already in the image as prepared store contents; there is no host Nix installation, package compilation, or startup download.

## Everyday use

Start in a project directory and run `ws enter`, or `ws session` for the packaged tmux session. The session contains workspace and editor windows that both use the integrated environment. A small background keeper holds the container open until the tmux server ends, so detaching does not remove its tool files. Plain `tmux` inside the workspace uses the same defaults; use `ws session` when the session must outlive the entering shell. No host tmux package is needed for the thin workflow.

Use the site's ordinary commands from that shell:

```bash
module list
sbatch job.slurm     # on a Slurm system
qsub job.pbs         # on a PBS system
```

The site clients and script arguments are used directly. This workflow does not require `--host-jobs` or the older limited submission bridge. Existing native jobs remain native. After obtaining an interactive allocation through the site's normal procedure, use `ws enter` there to bring the same tools into that allocation.

The image supplies Bash, Neovim, tmux, bat, fzf, fd, ripgrep, jq, eza, zoxide, less and terminal support. Bash includes the shared prompt, fzf history/path bindings and completion. Neovim loads the shared defaults and existing `~/.config/hpc-workspace/nvim.lua` overrides. This first thin preview does not yet package the full 0.4 compiler/agent inventory; programs already available on the host remain accessible.

Optional saved Inspector configuration continues to work. An available `WS_INSPECTOR_PROFILE` is imported once, or `ws init --profile FILE` imports an existing local YAML file explicitly. Daily entry does not require choosing Ruth/Jean/Blueback or running Inspector. Without a saved name the prompt uses `local` alongside the actual hostname; ordinary site commands still come from that system.

## Updates and rollback

Transfer the next release's files together, then run:

```bash
ws update /path/to/release-VERSION.json
```

The same command updates the image, launcher and shared defaults together. It handles the local setup automatically and preserves personal configuration and state. `ws rollback` selects the previous installed release after checking its image checksum. Neither operation replaces the image underneath an existing shell or kills sessions; new shells use the selected version. Managed tmux sessions use a separate server per release, so an update cannot quietly attach a new image to old processes.

## What the integration does

The launcher discovers accessible top-level host directories and mounts them at their normal paths. OS/program trees are read-only; data and runtime trees retain the caller's normal filesystem permissions. It keeps the image's `/nix` and `/workspace-tools` visible and leaves kernel interfaces to Apptainer. It preserves the calling environment, including module settings, literal values and agent credentials, through a private temporary JSON snapshot. The snapshot file is unlinked after the environment is read; the saved integration record contains path metadata only.

Loaded exported module functions are inherited. Where needed, Bash initializes the module function from standard `MODULESHOME`, `LMOD_CMD`, or site profile locations. It does not replay the entire login sequence. Packaged ELF tools use private dependency search paths; the shell and editor's native subprocesses still receive the module environment. Personal overrides load after common shell defaults.

This is a development environment with broad access to the caller's system, not a sandbox for untrusted code. A pre-existing nonempty host `/nix` or another reserved workspace path currently produces a local conflict diagnostic. Special preload libraries, site authentication helpers and container-engine nesting still need site-local validation. Having their files visible is not proof that every such program works.

## Validation and local checks

The [validation record](validation.md) distinguishes local fixtures from cluster acceptance. No cluster was accessed. The known Docker Desktop limitation requires extracted-SIF execution in the local Apptainer tests; normal SIF mounting and site-specific scheduler/MPI/GPU/runtime behavior remain checks to perform locally. Keep their output there.

For the first local check, enter the workspace, use `module list` and the site's normal queue query, read/write a project file, try Ctrl-R, and open `ws session`. Run any small submission using your normal site script. The reported earlier tmux/bat errors were not reproduced on the clusters, so the new fixture results are not a diagnosis of those incidents.
