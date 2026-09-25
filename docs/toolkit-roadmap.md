# Workspace toolkit roadmap

Updated 2026-09-24. The [0.5 thin preview](thin-start.md) implements a pinned Nix tool set, common appearance, automated host integration, packaged tmux and release installation/update/rollback. The [implementation plan](thin-container-plan.md) describes the full direction; the [validation record](validation.md) separates tested fixtures from pending site acceptance. The 0.6 preview implements the common CLI expansion, Codex and Claude Code, and the first editor plugin/parser bundle. See [current behavior and shortcuts](editor-and-agents.md). Personal HPC helpers and a deeper editor-agent adapter remain future work. The [shell research](research/shell-usability-tools.md) and [Neovim research](research/neovim-agent-workflow.md) record those proposals.

Use the site's existing compilers through its normal module environment. Additional compiler installations are outside the default toolkit; include one only for a concrete workflow that requires a specific version unavailable from the site. Editor language servers and agent runtimes remain separate packaging decisions and must preserve access to the selected site compiler.

## Intended daily experience

Use the same Bash shell, shortcuts, editor, and project commands on Ruth, Jean, and Blueback. Start in a project, find a file or previous command, edit with language assistance, ask a coding agent for a change, review the diff, run the project's checks, and submit the existing native job script. PuTTY and VS Code terminals receive the same useful behavior with ordinary fonts and a compatible color palette.

The [daily tutorial](daily-workflow.md), [command reference](command-reference.md), and `ws tools` now provide the walkthrough, shortcuts/examples, and installed versions. File pickers and searches start in the project. Large scans, tests, and benchmarks are deliberate operations; compute-heavy work runs in an allocation.

Keep the container as the consistent shell and tools environment, with shared dotfiles for appearance and shortcuts and Nix-packaged tools inside the image. Build the tool set centrally and automate deployment, updates, and local integration. Preserve ordinary use of site filesystems, schedulers, modules, and supported software from that same shell. Host integration is implementation work; requiring a second shell or manually maintained setup on each cluster does not meet the target.

## Common toolkit

The common additions below are packaged in the 0.6 preview. Host compilers/build tools remain native; C/C++ editor assistance uses a site-provided clangd/clang-format. The current guide and validation record describe what was exercised.

| Workflow | Existing foundation | Packaged additions and their role |
| --- | --- | --- |
| Shell navigation | Bash, fzf with shortcuts, fd, ripgrep, bat, enhanced Tab completion | zoxide and eza with icons disabled; editor pickers start in the project |
| Documentation | Built-in help | Tealdeer with an offline command-example cache and a workspace shortcut guide |
| Git review | Git | Delta and lazygit; optional Difftastic for structural comparisons |
| Project tasks | Make, CMake, Ninja | Just for named project recipes; watchexec for explicitly started, narrowly scoped watches |
| Python projects | Python, pip, venv | uv for project environments/lockfiles and Ruff for checking/formatting |
| Configuration and tabular data | jq | Mike Farah's yq for YAML and Miller for CSV/TSV reports |
| Logs and storage | less, htop, rsync | lnav for logs and ncdu for deliberate disk-usage inspection |
| Visual file operations | Neovim's file browser | Optional Superfile configured without Nerd Fonts |
| Per-project setup | Explicit shell/project settings | Optional direnv, enabled only for a project whose environment file the user has approved |
| Measurement | Existing compiler/build tools | Optional hyperfine for controlled command comparisons; retain site tools for scientific profiling |
| Sessions and editing | tmux, Neovim, saved editor layouts | Consistent editor/agent/shell windows, richer navigation, completion, diagnostics, and formatting |

These are complementary roles. Htop remains the initial process monitor; btop is an optional alternative. Delta is the everyday diff display; Difftastic is an explicit additional comparison. Superfile is optional alongside the editor's small file browser. The research note explains each choice and its operating limits.

## Neovim and coding agents

The editor has the shared theme, persistent undo, session save/restore, file/text/symbol picking, shortcut hints, Git change markers, completion, diagnostics, and explicit formatting. The 0.6 bundle provides Fortran, Python, and Bash language servers, host clangd integration for C/C++, and syntax parsers including YAML/CMake/Lua. Language assistance for site-specific headers and MPI still needs a correct compilation database or matching include paths; editor plugins do not supply the scientific runtime.

Keep one main editor configuration and a small, pinned plugin set. Package the plugins, language servers, and selected syntax parsers during release preparation for the selected execution context. Opening the editor should not trigger downloads or tool installation. Use plain labels/signs by default and test narrow PuTTY-sized windows, colors, and keyboard behavior as well as VS Code.

Run Neovim and Codex or Claude Code in neighboring tmux panes/windows, with a clearly identified execution context for tests and host operations. Validate editor/agent subprocesses across the chosen container/host integration. Agent edits to an unmodified buffer can be reloaded; unsaved editor changes must be preserved and conflicts made visible. Give simultaneous editing agents separate Git worktrees. Review changes with the same editor/Git tools used for manual work.

The workspace sets `VISUAL=nvim` and `EDITOR=nvim`. The current integration is adjacent editor/agent windows, external-file checks, and a shared Git review workflow. Additional agent-specific editor adapters remain optional future work. Agent skill files are bundled, but their automatic activation in the thin runtime is still outstanding; see [skills](skills.md).

## Current versions with reproducible releases

For independently packaged productivity tools, select the newest stable upstream release available when preparing a release. Resolve concrete versions, verify artifacts, test the combination, and freeze it in the release manifest. The same selected release should expose the same tools next month. Updates produce a new tested image and matching launcher/defaults, with automated application and rollback. The image owns updates to its private libraries; host library updates affect programs that actually load those compatible shared libraries.

Track the base OS on a supported stable release with a dated package snapshot. Record any older compatibility pin and its reason. Keep compiler, GPU, MPI, and language-server compatibility explicit instead of independently upgrading every component of a coupled stack. A newest-version preference does not remove the need to verify the entire combination.

Lock editor plugins and parsers along with the editor. Include Bash completions and fzf integration files as runtime assets, even if upstream packaging calls them examples or documentation. Validate actual shortcuts, completion, offline startup, editor behavior, and persistence in addition to checking that executables exist.

Project dependencies remain project-owned: for example, Python dependencies belong in a project's virtual environment and lockfile. They should not silently replace the workspace's own Python tools.

## Your HPC toolbox

Your public [Lib Locator repository](https://github.com/ray12514/lib-locator/blob/main/README.md) supplies the **`libsweep`** command. It inventories shared-library variants and executable versions across nodes, supports PBS and Slurm inventory, and writes reports. It is a strong first candidate for reuse. This research inspected its README and source; it did not run a node sweep or validate an installation in the workspace.

Define a small integration convention before adding custom tools:

- Keep each tool in its own repository/package with an explicit version or commit and its own tests.
- Record its command name, purpose, dependencies, and where it runs: container, native host, or compute allocation.
- Offer useful `--help`, stable exit codes, and machine-readable output where appropriate, alongside readable terminal output. Reuse existing formats before adding new ones.
- Store writable configuration, caches, and reports outside the immutable image. Keep system reports on their originating system; do not automatically attach them to agent prompts or public release artifacts.
- Reuse saved Inspector-derived settings for relevant defaults, with explicit overrides and refresh. Do not rerun Inspector on every shell start or replace its existing workflow.

Portable helpers can be included in the image. Host-dependent helpers need a tested host execution path or compatible container integration, with pinned packages and coherent tool-specific dependencies. During local development, explicitly select a checked-out tool; use pinned packages in releases. A larger dependency-heavy suite can later become a versioned toolbox image or software payload using the [runtime-layer design](design-direction.md). Small Python/shell helpers do not each need a separate container.

`libsweep` needs particular care about execution context: its scheduler inventory and SSH orchestration depend on site tools, connectivity, and authentication. The thin shell provides general host integration, but `libsweep` is not packaged or validated by this release. The older core submit/jobs bridge is not its execution path. Library-name/version agreement is diagnostic evidence, not a complete application/MPI ABI compatibility test.

Two established HPC projects are worth evaluating before writing equivalent helpers: **hwloc** for inspecting CPU/NUMA/device topology, including its terminal-oriented `lstopo-no-graphics`, and **ReFrame** for repeatable system tests and benchmarks. Hwloc's output describes the resources visible in the execution environment; ReFrame needs deliberate site and test configuration and can submit jobs. Both belong to a later, explicitly invoked diagnostic/testing workflow. [hwloc documentation](https://www.open-mpi.org/projects/hwloc/), [ReFrame documentation](https://reframe-hpc.readthedocs.io/en/stable/)

Existing discovery commands and possible extensions:

| Interface | Purpose |
| --- | --- |
| `ws tools` | Already lists installed versions, with `--json` output; examples and shortcuts are in the command reference |
| Extend `ws doctor` | Explain the selected image, relevant saved settings, mounts, and explicitly requested runtime checks; the existing command runs on the host |
| `ws env diff` | Compare selected local environment/profile snapshots before and after a module or configuration change; exclude credentials |
| `ws binary-info` | Summarize ELF architecture, needed libraries, and embedded search paths using metadata inspection; distinguish container and host views |
| `ws logs` | Find and open a job's output through native scheduler information, without translating or rewriting its submission script |

`ws tools` and the current `ws doctor` exist. The new `ws env diff`, `ws binary-info`, and `ws logs` interfaces are proposals. Implement them only when a repeated task justifies them, and compose existing tools wherever possible.

## Delivery sequence

1. Delivered: pinned Nix tools, automated host integration, managed tmux, expanded agents/editor/CLI bundle, and the one-command download/install/update path. See [validation](validation.md) for the terminal, locale, library, and installation checks; site-specific acceptance remains local work.
2. Use the [practice project](../examples/workflow/) and daily guide to refine the workflow. Add real project recipes using each project's existing build/tests and native scheduler scripts.
3. Add [remembered Apptainer runtime setup](runtime-setup.md): use a recorded executable directly when sufficient, and automatically load a required site module only for workspace launch. Verify fresh-login and compute-node cases locally.
4. Add optional [guided configuration](guided-configuration.md): package Gum for terminal prompts, reuse the existing configuration backend, then add versioned Codex, Claude Code, and project-file forms. Keep initial runtime setup usable before the image can run.
5. Complete automatic skill activation for the thin runtime and validate it without replacing independently managed skills.
6. Integrate `libsweep` as the first personal HPC tool, then add further helpers and scientific runtime layers as concrete workflows require them.

This roadmap uses public sources and local development code only. The implemented foundation is documented separately; the remaining proposals do not change any cluster configuration.
