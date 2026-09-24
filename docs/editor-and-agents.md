# Editor, tools, agents, and interactive jobs

The 0.6 thin preview packages these defaults centrally. New shells use the selected release; personal files under `~/.config/hpc-workspace` are preserved. Run `ws tools` (or `ws tools --json`) inside the workspace for exact installed versions. The Nix lock and image manifests pin tools, plugins, parsers, and help pages together; this is a tested package snapshot, not a promise that every upstream project has the same release schedule.

## Daily toolkit

| Task | Packaged tools / example |
| --- | --- |
| History, navigation, search | Bash, fzf (Ctrl-R history, Ctrl-T paths, Alt-C directories), fd, ripgrep, zoxide (`z project`), eza (`ll`) |
| Read and review | bat, less, delta, lazygit; `difft old.c new.c` for an explicit structural comparison |
| Files, logs, processes | `spf .` (Superfile with ordinary fonts), `ncdu -rr -x .`, `lnav application.log`, htop, btop |
| Project tasks | `just --list`, direnv, watchexec, hyperfine; environment loading, watches, and benchmarks are explicit choices |
| Python and shell quality | uv, Ruff, ShellCheck, shfmt; uv defaults to using an available Python rather than downloading one |
| Data | jq, Mike Farah's `yq`, Miller (`mlr`) |
| Offline examples | `tldr tar`, using pinned English common/Linux pages inside the image |
| Editor and agents | Neovim, tmux, Codex, Claude Code; private agent/editor runtimes do not replace host Python, Node, or compilers |

Use the site's module-selected compiler and scientific stack. `df`, `findmnt`, Git, SSH, scheduler clients, and other native programs continue to come from the host. No disk scan, benchmark, directory watch, agent session, or `.envrc` execution starts merely because you enter the workspace. Delta is the shell's Git pager only when you have not already chosen a pager.

Use `df -h` for human-readable filesystem capacity and `findmnt` to inspect visible mounts. The launcher binds the host's accessible top-level filesystem trees when you enter. These commands report the container's mount view, which can differ from the host's mount table; permissions, site bind rules, and mounts created afterward still matter. A filesystem that appears only later may need a fresh `ws enter` or an explicit local bind.

Superfile, lazygit, btop, and tealdeer have personal configuration templates under `~/.config/hpc-workspace/xdg`. Their wrappers scope configuration to those programs; they do not globally redirect host application settings. Templates are seeded only when missing. The offline help cache is read-only; update it with a workspace release rather than `tldr --update`.

On Superfile's first run, press any key to dismiss its welcome screen. Then `?` opens the key guide and `q` quits. Lazygit's first-run welcome uses Enter to continue into the repository view.

## Neovim defaults to refine together

Neovim loads the shared configuration, then `~/.config/hpc-workspace/nvim.lua`. The image includes fzf-lua, which-key, gitsigns, blink.cmp, conform, nvim-treesitter, and vim-tmux-navigator. Native package loading needs no runtime plugin manager. Completion uses Blink's Lua matcher; startup does not download a binary.

Precompiled parsers and matching queries cover C, C++, Fortran, Python, Bash, JSON, YAML, Lua, Markdown, CMake, Vim, and Vim help. Syntax highlighting falls back to native syntax for unsupported languages and skips Treesitter on files over 1 MiB or 20,000 lines. Don't run `:TSUpdate` against the release: update the image's parser/plugin set together. [Treesitter setup and compatibility](https://github.com/nvim-treesitter/nvim-treesitter#quickstart)

| Keys | Action |
| --- | --- |
| Space f f / f g / f b / f s | Project files / text search / buffers / document symbols |
| Space c d / c a / c r / c f | Diagnostics / code actions / rename / manual formatting |
| Space g p / g s | Preview / stage a Git hunk |
| Space w s / w r | Save / restore the editor layout |
| Space w h / w j / w k / w l | Move left / down / up / right through editor splits and out to adjacent tmux panes |
| Space e / Space ? | File browser / shortcut guide |
| Ctrl-N / Ctrl-P / Ctrl-Y / Ctrl-E | Next completion / previous / accept / dismiss |
| g d / g r r | Definition / references |

Formatting is manual, so saving an existing PBS/Slurm script does not silently reformat it. Gitsigns uses ordinary `+`, `~`, and `-` characters. Borders, labels, and completion kinds do not require Nerd Fonts. Set `WS_COLOR=256`, `WS_COLOR=truecolor`, or `WS_COLOR=never` in personal Bash settings as appropriate; PuTTY and VS Code can use the same key vocabulary.

Python support uses basedpyright plus Ruff, with diagnostics limited to open files. Bash uses bash-language-server and ShellCheck, with remote explainshell requests disabled. Fortran uses fortls with one initialization thread and its updater disabled by default. Project configuration can refine server behavior. C/C++ uses `clangd` if provided by the host and `clang-format` if available; neither supplies your site's headers or MPI configuration. Use a correct `compile_commands.json`. Heavy project indexing still belongs in an appropriate allocation.

An unmodified buffer reloads external agent edits on focus/buffer checks. Neovim preserves unsaved edits and reports a conflict instead of overwriting them. Agents run as separate tools; merely opening a source file does not send it to a model. A deeper editor adapter can be a later configuration choice.

## tmux

`ws session` starts **workspace**, **editor**, and **agents** windows. The agents window is a shell: run `codex` or `claude` there when ready. It uses the same project directory. Use Ctrl-B then the window number to switch.

Ctrl-B followed by `|` or `-` splits at the current directory. Ctrl-B then h/j/k/l selects a pane; capital H/J/K/L resizes it. Ctrl-B then `[` enters copy mode, with `v` to select and `y` to copy into tmux's buffer. The editor's Space-w navigation can cross its outer split boundary into tmux. Ordinary shell Ctrl-H/J/K/L behavior remains available. [vim-tmux-navigator](https://github.com/christoomey/vim-tmux-navigator)

Detach with Ctrl-B then d. Reattach with `ws session` on the same node and project. Layout saving remains separate from live process persistence: it cannot preserve a finished allocation or move a running process to another node. Release updates create separate tmux servers; start a fresh session to test a new release's locale/tool configuration.

Ctrl-C interrupts a foreground command. Ctrl-D at an empty Bash prompt, or `exit`, closes that pane's shell. In 0.6.1 and later, the pane closes with it; closing the final pane/window returns the client to its parent shell. Ending an interactive job in a pane returns to the pane's login-node shell rather than closing that shell.

Earlier releases set `remain-on-exit on`, retaining a dead pane after its shell exited. This can look like a frozen terminal because there is no shell left to read ordinary input. Ctrl-B then d detaches even from that screen. Ctrl-B then x and confirmation closes the current pane; use it on the dead pane, not on work you want to retain. A fresh patch-release session uses `remain-on-exit off`. A personal `tmux.conf` override still takes precedence.

For an older image, put `set -g remain-on-exit off` in `~/.config/hpc-workspace/tmux.conf` to change future workspace tmux servers. In an existing tmux session, Ctrl-B then `:` opens the tmux command prompt; enter `set -g remain-on-exit off` to change the server's default. Close an already-dead pane separately. This setting changes pane-exit behavior; it does not add the container keeper that `ws session` supplies.

## Interactive jobs and tmux

The scheduler starts the compute-node process. A login-node container and its tmux server do not migrate with it. A pane can hold the interactive job's terminal connection while tmux itself remains on the login node.

```text
login node: ws session -> workspace pane -> native interactive job client
                                              |
compute node:                           native site shell
                                              |
                                           ws enter
                                              |
                                      nvim / codex / claude
```

Use your site's existing resource options and interactive procedure. When a command exports its environment, the optional prefix strips workspace-only settings before calling the native client:

```bash
# PBS example; replace YOUR_SITE_OPTIONS with the options you normally use.
ws job-env -- qsub -I YOUR_SITE_OPTIONS

# Slurm example when your site uses srun for the interactive step.
ws job-env -- srun YOUR_SITE_OPTIONS --pty /bin/bash -l

# After the scheduler has placed you on the compute node:
hostname
ws enter
codex --version
claude --version
# Then start the agent you want to use.
```

`ws job-env` does not translate flags, pick resources, change accounts/queues, or move the client out of the current container. It removes image paths and runtime markers and the login-node `TMUX` socket from the environment sent onward, while preserving current module changes, user credentials, and other native settings. It restores values that the workspace replaced, unless you subsequently changed them explicitly. Ordinary `sbatch job.slurm` and `qsub job.pbs` remain the same native commands. The prefix is also useful when deliberately exporting the environment of a batch job that will not start this image.

Slurm's `salloc` grants resources but may still run its command on the submitting node; follow the site's procedure for starting the actual compute-node step. Slurm commonly exports the caller's environment. A stale `WS_CONTAINER` variable alone is now insufficient to block a new `ws enter` when the image files are absent. These safeguards are tested with synthetic transitions, not a live HPCMP scheduler. [Slurm salloc](https://slurm.schedmd.com/salloc.html), [Slurm srun](https://slurm.schedmd.com/srun.html)

Install the release on a persistent filesystem available to the compute nodes. The compute node needs access to the SIF, launcher, project, home, and its own Apptainer installation. `ws enter` discovers the trees on that node. Detaching login-node tmux preserves the client connection while that node/session survives; walltime limits, cancellation, and node cleanup still end jobs. A compute-node tmux server lasts only as long as that allocation and the site's process rules permit.

## AI setup and local checks

The image contains Codex and Claude Code, without credentials. Their wrappers retain existing authentication, proxies, and certificate choices. When `SSL_CERT_FILE` is unset, the wrapper chooses an available host certificate bundle before the bundled public roots. No TLS verification is disabled. Agent automatic updates are disabled so the installed versions follow workspace releases; neither wrapper bypasses the agent's approval/sandbox controls.

Authenticate locally on the cluster using the method approved for your account. For a headless Codex login, `codex login --device-auth` is an official option when enabled for the account/workspace. Codex also supports API-key authentication and custom CA bundles. Claude's sign-in/API-provider setup is independent. Shared home directories can make saved credentials visible on compute nodes, but network and provider access must still work there. [Codex authentication](https://learn.chatgpt.com/docs/auth), [Claude Code setup](https://code.claude.com/docs/en/setup)

`codex --version` and `claude --version` verify installation, not outbound API connectivity. Test sign-in and a small approved request once on the login node and again inside a compute-node workspace. Use synthetic/non-sensitive content for the initial check. Claude's required hosts depend on the selected authentication/provider features; use the official list for any local allowlist work. Keep site diagnostics and credentials on the cluster. [Claude network configuration](https://code.claude.com/docs/en/network-config)

## Locale warning

The old image reproduced `setlocale: LC_ALL: cannot change locale (en_US.UTF-8)` because the Nix runtime lacked that locale's data. The new image bundles its matching glibc locale archive, selected with Nix's `LOCALE_ARCHIVE_2_27` setting. Ordinary host glibc continues to use its own locale installation. Valid host locale values are preserved; unavailable values such as a bare `UTF-8` are replaced with `C.UTF-8` before Bash starts. [Pinned Nix glibc patch](https://github.com/NixOS/nixpkgs/blob/8825bebf6324e0579d012936eff73379af284b6d/pkgs/development/libraries/glibc/nix-locale-archive.patch)

This reproduces and fixes the missing-data case locally. An old running tmux server or a personal startup file that sets a different invalid locale can still need local attention. The release does not alter your host startup locale configuration.
