# Workspace command reference

For a guided example, use the [daily workflow](daily-workflow.md). Examples below run **inside the workspace from a project directory**, except the lifecycle commands in the first table. Paths such as `src`, `logs`, and `job.slurm` refer to your project. Many examples also work in the bundled [practice project](../examples/workflow/).

## Workspace lifecycle

| Where | Command | Result |
| --- | --- | --- |
| Repo checkout, native shell | `git pull --ff-only && ./setup` | Download, verify, and install the recommended release |
| Repo checkout on transfer machine | `./setup --download-only` | Prepare the same files for offline transfer |
| Native login shell, project directory | `ws enter` | Enter the integrated Bash shell |
| Native login shell, project directory | `ws session` | Start/reconnect to the managed tmux workspace |
| Native login shell | `ws sessions` / `ws sessions --json` | List recorded session nodes/projects/images (0.7.2+) |
| Native shell | `ws enter --dry-run` | Inspect the local mount plan |
| Inside workspace | `ws tools` / `ws tools --json` | Inspect packaged tool versions |
| Native shell | `ws runtime setup` / `ws runtime status` | Check and remember Apptainer / display its saved invocation |
| Inside workspace | `ws configure` | Choose a workspace or agent configuration form |
| Inside workspace | `ws configure codex team-a` | Create/edit a named gateway, rotate its key, or choose a default |
| Inside workspace | `ws agent codex team-a` | Launch the selected gateway profile; `claude` works the same way |
| Inside workspace | `ws agent codex --list` / `ws agent codex --native` | List profiles / use ordinary agent settings for this launch |
| Native shell | `ws rollback` | Select the previously installed release for new sessions |

`ws session` already enters the workspace. If you used `ws enter` first, ordinary `tmux` works there, but has no independent container keeper. Return to the native shell to start a managed `ws session`.

Use `ws sessions` from the native shell after a round-robin login to find [recorded session locations](session-locations.md). If still on 0.7.1, the updated repository's `./bin/ws sessions` can inspect its older records.

The [gateway configuration guide](agent-profiles.md) covers multiple connections, private credentials, and rotation. Add `--plain` to a configuration command for basic prompts; native agent arguments follow `--`, as in `ws agent codex team-a -- --model MODEL`.

## Keyboard essentials

Keys separated by spaces are pressed in sequence. In tmux, press and release **Ctrl-B** before the next key. Neovim's Space shortcuts are used in **Normal mode**; press Esc first.

| Context | Keys | Action |
| --- | --- | --- |
| Bash | Ctrl-R | Search history; Enter selects into the command line; another Enter executes |
| Bash | Ctrl-T | Insert a selected path; try after typing `nvim ` |
| Bash | Alt-C, or Esc then c | Select a directory to enter |
| Bash | Ctrl-A / Ctrl-E | Start / end of command line |
| Bash | Ctrl-U / Ctrl-K | Remove text before / after the cursor |
| Bash | Ctrl-W / Ctrl-Y | Remove previous word / reinsert removed text |
| Bash | Tab | Complete commands and paths |
| fzf picker | Up / Down, Enter, Esc | Choose, accept, cancel |
| tmux | Ctrl-B 1 / 2 / 3 | Workspace / editor / agents window |
| tmux | Ctrl-B `\|` / `-` | Split side by side / above and below |
| tmux | Ctrl-B h/j/k/l | Move left/down/up/right between panes |
| tmux | Ctrl-B z / d | Toggle pane zoom / detach |
| tmux | Ctrl-B [, then v / y | Enter copy mode, begin selection / copy to tmux buffer |
| tmux | Ctrl-B ] | Paste tmux's buffer; this is separate from the Windows clipboard |
| Neovim | Space f f / f g / f b | Files / project text / open buffers |
| Neovim | Space f s / c d | Document symbols / diagnostics |
| Neovim | g d / g r r | Definition / references, with an attached language server |
| Neovim | Space c a / c r / c f | Code action / rename / explicit formatting |
| Neovim | Space g p / g s | Preview / stage the current Git hunk |
| Neovim | Space w h/j/k/l | Move through editor splits and neighboring tmux panes |
| Neovim | Space w s / w r | Save / restore editor layout |
| Neovim | Space e / Space ? | File browser / shortcut help |
| Neovim completion | Ctrl-N/P, Ctrl-Y, Ctrl-E | Select next/previous, accept, dismiss |

## Commands by task

| Task | Try | What it gives you |
| --- | --- | --- |
| List | `ll` | eza long listing, hidden entries, ordinary fonts |
| Small tree | `eza --tree --level=2 --icons=never .` | Two levels of project structure |
| Revisit a directory | `z project` / `zi project` | zoxide jump / interactive choice among learned directories |
| Find names | `fd --type f --extension py . src` | Python filenames under `src` |
| Find by host metadata | `find logs -type f -name '*.log' -mtime -2 -print` | Recently modified log files |
| Search contents | `rg -n --smart-case 'tolerance' src config` | Matching lines with locations |
| Search literal text | `rg -n -F 'MPI_Init(' src` | Fixed string, not a regular expression |
| Choose | `rg --files src \| fzf` | Interactive choice of a filename; selection prints it |
| Read | `bat --style=numbers --paging=never -- src/solver.py` | Numbered source preview |
| Page | `less logs/run.log` | Search with `/`, next with n, quit with q |
| Review changes | `git diff` / `git diff --staged` | Delta pager when no personal Git pager overrides it |
| Visual Git | `lazygit` | Git status, diffs, staging, and commits; `?` for help |
| Structural comparison | `difft old.py new.py` | Syntax-aware comparison of two files |
| Browse files | `spf .` | Superfile; `?` for help and q to quit |
| Named project tasks | `just --list` / `just check` | Recipes from the project's Justfile, not globally defined tasks |
| Shell quality | `shellcheck jobs/check.sh` / `shfmt -d jobs/check.sh` | Diagnostics / proposed formatting without rewriting |
| Python quality | `ruff check src` / `ruff format --check src` | Diagnostics / formatting check without rewriting |
| Project Python | `uv venv --python python3 .venv` | Virtual environment using available host Python |
| Project environment | `direnv exec . COMMAND` | Run with a previously allowed `.envrc`; shell hook is opt-in |
| Watch a small source tree | `watchexec -w src -e py -- ruff check src` | Check now and again after relevant file changes; Ctrl-C stops it |
| Time a repeatable command | `hyperfine --warmup 1 --runs 5 'python3 src/solver.py'` | Repeated timings; real workloads belong in an allocation |
| JSON | `jq '.run' reports/run.json` | Select structured data |
| YAML | `yq '.solver.tolerance' config/run.yaml` | Query with Mike Farah's yq |
| CSV | `mlr --csv sort -n seconds reports/timings.csv` | Numerically sort a table |
| Logs | `lnav logs/run.log` | Interactive log reader; `?` for help |
| File space used | `ncdu -rr -x .` | Read-only directory scan within one filesystem; still traverses files |
| Filesystem capacity | `df -h .` | Capacity and free space for this path's filesystem |
| Mount identity | `findmnt -T "$PWD"` | Host-provided utility, viewed from this container |
| Processes | `htop` / `btop` | Processes/resources visible on the current node; not a cluster queue |
| Examples offline | `tldr tar` / `tldr rg` | Bundled command examples; update with the workspace release |
| Agents | `codex` / `claude` | Start deliberately in the project after local authentication |

Git, find, findmnt, df, du, tail, SSH, Python, compiler/build programs, and scheduler clients come from the host. The workspace packages the productivity tools listed by `ws tools`, their private dependencies, and editor support tools (`basedpyright`, `bash-language-server`, `fortls`). `tput`/`infocmp` supply terminal capability support. C/C++ language assistance uses host `clangd` and `clang-format` when available.

The [toolkit roadmap](toolkit-roadmap.md) tracks additional HPC helpers. `libsweep`, ReFrame, and new `ws logs`/`ws env diff` commands are not bundled features of this release.
