# Workspace toolkit roadmap

Updated 2026-09-23. The [dotfile foundation](dotfiles.md), fzf shortcuts, and enhanced Tab completion are implemented in **0.4.0-preview1** in the SIF workflow. The [thin-container implementation plan](thin-container-plan.md) recommends Nix tools inside the image and a tested site integration recipe as the next milestone. Those changes, additional tools, and editor plugins remain proposed. The [native tools research](research/native-tool-layer.md) is an alternative analysis, not a selected migration. The [shell tool research](research/shell-usability-tools.md) records the earlier image audit and upstream sources; the [Neovim research](research/neovim-agent-workflow.md) records the editor proposal.

## Intended daily experience

Use the same Bash shell, shortcuts, editor, and project commands on Ruth, Jean, and Blueback. Start in a project, find a file or previous command, edit with language assistance, ask a coding agent for a change, review the diff, run the project's checks, and submit the existing native job script. PuTTY and VS Code terminals receive the same useful behavior with ordinary fonts and a compatible color palette.

The defaults should be discoverable. Add a short shortcut guide and a tool catalog showing what is installed, its version, and one useful example. File pickers and searches start in the project. Large scans, tests, and benchmarks are deliberate operations; compute-heavy work runs in an allocation.

Keep the container as the consistent shell and tools environment, with shared dotfiles for appearance and shortcuts. Evaluate Nix inside the image to manage the selected binaries and their dependencies. Preserve useful access to site filesystems, schedulers, modules, and scientific tools through explicitly tested integration. File visibility and host command execution are separate requirements; packaging tools with Nix does not by itself establish host integration. No switch to a native-only installation has been selected.

## Common toolkit

The exact package list is a proposal until its versions and integrations pass tests in the intended native or container execution context.

| Workflow | Existing foundation | Proposed additions or improvements |
| --- | --- | --- |
| Shell navigation | Bash, fzf with shortcuts, fd, ripgrep, bat, enhanced Tab completion | Add zoxide and eza with icons disabled; integrate project-scoped path candidates/previews |
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

The existing editor already has the shared theme, persistent undo, session save/restore, and clangd setup. Extend it with file/text/symbol picking, shortcut hints, Git change markers, completion, diagnostics, and explicit formatting. Start with C/C++, Fortran, Python, and Bash support; add YAML/CMake/Lua where the projects need them. Language assistance for site-specific headers and MPI still needs a correct compilation database or matching include paths; editor plugins do not supply the scientific runtime.

Keep one main editor configuration and a small, pinned plugin set. Package the plugins, language servers, and selected syntax parsers during release preparation for the selected execution context. Opening the editor should not trigger downloads or tool installation. Use plain labels/signs by default and test narrow PuTTY-sized windows, colors, and keyboard behavior as well as VS Code.

Run Neovim and Codex or Claude Code in neighboring tmux panes/windows, with a clearly identified execution context for tests and host operations. Validate editor/agent subprocesses across the chosen container/host integration. Agent edits to an unmodified buffer can be reloaded; unsaved editor changes must be preserved and conflicts made visible. Give simultaneous editing agents separate Git worktrees. Review changes with the same editor/Git tools used for manual work.

The workspace already sets `VISUAL=nvim` and `EDITOR=nvim`. Codex documents **Ctrl-G** for composing a longer prompt in that editor and returning it to the CLI before sending. That is a useful initial integration, followed by an optional editor adapter if it adds value. The shortcut itself was not exercised during this research. [Official Codex CLI customization](https://learn.chatgpt.com/docs/cli-customization)

## Current versions with reproducible releases

For independently packaged productivity tools, select the newest stable upstream release available when preparing a release. Resolve concrete versions, verify artifacts, test the combination, and freeze it in the release manifest. The same selected release should expose the same tools next month. Updates produce a new tested native tool bundle, package-manager generation, or image, with a changelog and rollback path. Each delivery format owns updates to its private libraries; host library updates only help programs that actually load those compatible shared libraries.

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

`libsweep` needs particular care about execution context: its scheduler inventory and SSH orchestration depend on host tools, connectivity, and authentication. Merely adding its executable to the SIF does not establish that integration. Begin with native-host execution; add a narrow adapter only if useful. The current workspace host connection supports **submit/jobs only** and cannot already run `libsweep`. Library-name/version agreement is diagnostic evidence, not a complete application/MPI ABI compatibility test.

Two established HPC projects are worth evaluating before writing equivalent helpers: **hwloc** for inspecting CPU/NUMA/device topology, including its terminal-oriented `lstopo-no-graphics`, and **ReFrame** for repeatable system tests and benchmarks. Hwloc's output describes the resources visible in the execution environment; ReFrame needs deliberate site and test configuration and can submit jobs. Both belong to a later, explicitly invoked diagnostic/testing workflow. [hwloc documentation](https://www.open-mpi.org/projects/hwloc/), [ReFrame documentation](https://reframe-hpc.readthedocs.io/en/stable/)

Useful future custom commands, all proposed except the existing doctor command:

| Interface | Purpose |
| --- | --- |
| `ws tools` | Discover installed tools, versions, execution context, examples, and shortcuts |
| Extend `ws doctor` | Explain the selected image, relevant saved settings, mounts, and explicitly requested runtime checks; the existing command runs on the host |
| `ws env diff` | Compare selected local environment/profile snapshots before and after a module or configuration change; exclude credentials |
| `ws binary-info` | Summarize ELF architecture, needed libraries, and embedded search paths using metadata inspection; distinguish container and host views |
| `ws logs` | Find and open a job's output through native scheduler information, without translating or rewriting its submission script |

These names are design examples, not commands the current release provides. Implement only when a repeated task justifies them, and compose existing tools wherever possible.

## Delivery sequence

1. Diagnose the reported tmux/bat errors using the [local guide](troubleshooting-startup.md). Keep the container workflow and personal overrides; clarify which site operations must work from within it.
2. Build the small Nix tool pilot and explicit host-integration recipe described in the [implementation plan](thin-container-plan.md). Validate real invocation, terminal input, paths, modules, editor subprocesses and native scheduler behavior, then perform site-local acceptance before extending the toolkit.
3. Build the compact Neovim configuration and validate the editor/agent/review workflow in the intended execution contexts.
4. Add reusable project recipes for linting, formatting, builds, and tests, using native scheduler scripts where required.
5. Integrate `libsweep` as the first personal HPC tool and use that experience to settle the small packaging convention.
6. Add further custom helpers and scientific runtime layers as concrete workflows require them.

This roadmap uses public sources and local development code only. The implemented foundation is documented separately; the remaining proposals do not change any cluster configuration.
