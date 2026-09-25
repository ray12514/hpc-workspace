# Current workspace design and future scientific stacks

Updated 2026-09-24 for the **0.6.1 thin release** and repo-based **`./setup`** workflow. This is the architecture overview; [daily use](daily-workflow.md) and [installation](thin-start.md) are documented separately.

## One integrated development shell

Build the productivity tools, private dependencies, editor plugins, and shared defaults centrally using a pinned Nix package set. Deliver them in one SIF with a matching host launcher and installer. The cluster does not need a host Nix installation or a local rebuild of the toolbox.

`./setup` downloads and verifies the recommended image/source/installer/manifest together, or reuses a verified transferred bundle. It selects a versioned installation and makes `ws` available through the user's Bash startup. `ws enter` starts the integrated shell; `ws session` starts that environment in managed tmux. Updates preserve personal files and state, and existing sessions keep their original image.

The image retains `/nix` and `/workspace-tools`. The launcher exposes accessible host filesystem trees at their ordinary paths, including a coherent host userspace and the project/home paths. It preserves the calling module and application environment while adding selected workspace tools to PATH. Image programs use their own dependencies; ordinary scheduler clients, compilers, Python, Git, SSH, and filesystem utilities come from the host. The [startup guide](thin-start.md#what-the-integration-does) describes discovery and its limits.

Use native `sbatch`, `qsub`, queue commands, and site scripts from that same shell. The older `--host-jobs` bridge is not the current submission workflow. When exporting an environment to a process outside the image, `ws job-env -- COMMAND ...` removes workspace-only settings while retaining native/module changes and the original command arguments.

## Build compatibility is separate from submission

The current image supplies development conveniences, not a replacement scientific compiler stack. Load and use the site's intended compiler/MPI modules and build/run procedure. For a project requiring a different scientific userspace, build and run it with a compatible application container or a future validated software stack.

Binding a compiler, driver, or MPI library path is not proof that a particular workload works. CPU instruction targets, GPU/toolkit versions, MPI ABI, process management, and fabric integration still need site-local checks. The [validation record](validation.md) records what the public local fixtures establish; real cluster results stay on their systems.

## Implemented and remaining work

| Area | Implemented now | Additional work |
| --- | --- | --- |
| Delivery | Repo `./setup`, complete verified bundle, offline transfer, update/rollback, remembered Bash startup choice | Broader distribution/registry options if needed |
| Daily tools | CLI/AI toolkit, Neovim plugins/parsers, Bash integration, shared and personal settings | Refine from daily use; integrate personal HPC helpers |
| Host access | Automatic filesystem/environment integration and native client invocation | Site-specific authentication and unusual mount/runtime cases |
| Jobs | Native scripts and clients; optional environment cleanup prefix | Live site validation; no scheduler policy translation planned |
| Sessions | Managed login-node tmux with a container keeper; saved layouts and editor state | No live process migration or walltime extension |
| Inspector | Import existing local YAML once, save facts, explicit refresh | Use facts for later validated scientific-stack integration |
| Configuration | Saved local defaults, personal dotfiles, command-line setup | [Remember the runtime](runtime-setup.md) and add optional [terminal forms](guided-configuration.md) |
| GPU/MPI | Runtime GPU passthrough flags and host access; imported facts | No bundled scientific toolkit or validated distributed MPI/GPU profile |
| Software payloads | Normal filesystem binds | No SquashFS stack selection/mount/activation interface yet |
| Agent skills | Versioned skill copies in the image | Thin-runtime automatic activation is not wired up; see [skills](skills.md) |

## Future immutable software stacks

The CSCS uenv/Stackinator work studied earlier provides a useful pattern: build a coherent software stack once, publish an immutable image, mount it at an agreed prefix, and activate a defined view. Those tools are not installed or integrated by this workspace. The [runtime-layer research](research/runtime-layers-gpu-mpi.md) records the public sources and compatibility questions.

A future payload should have its own version, checksum, mount prefix, toolchain/CPU/GPU targets, and a stated compatibility relationship to the workspace/application runtime. Prefer a coherent stack over independently mixing compiler, MPI, GPU, and language-runtime fragments. A SquashFS data-image mount is different from binding the image file as an ordinary file or merging a writable overlay into the OS. The current bind schema only describes ordinary source/destination/mode binds; it does not implement data-image activation.

GPU devices and kernel drivers remain host responsibilities. A user-space toolkit does not grant resources or upgrade a driver. MPI also depends on the native launcher, process manager, and interconnect. Establish a small serial/GPU/MPI pilot on an allocated system before describing a combination as supported.

Images provide repeatable package contents; they are not a sandbox against programs running with the user's permissions. Shared data remains live, and immutable images still need maintained releases. Scientific payloads require their own integrity and compatibility checks. Measure any filesystem-metadata or startup benefit locally rather than promising a universal speedup.

The next useful steps are site-local acceptance of the daily workflow, remembered runtime setup, guided configuration, thin-runtime skill activation, project recipes, and selected personal HPC tools such as `libsweep`. The [toolkit roadmap](toolkit-roadmap.md) distinguishes those proposals from commands already available.
