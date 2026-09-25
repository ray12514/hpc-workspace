# Make the workspace part of your day

This is a practical guide to the **0.6.1 thin workspace**. Install once with [the repo's `./setup` command](thin-start.md), then use the same habits in PuTTY or a VS Code terminal. The [command reference](command-reference.md) is the shorter lookup sheet.

- [Start your workspace](#start-your-workspace)
- [Try a complete workflow](#try-a-complete-workflow)
- [Move around and reuse commands](#move-around-and-reuse-commands)
- [Find names, search contents, and choose a result](#find-names-search-contents-and-choose-a-result)
- [Edit and review in Neovim](#edit-and-review-in-neovim)
- [Check code and make project tasks repeatable](#check-code-and-make-project-tasks-repeatable)
- [Submit jobs and inspect results](#submit-jobs-and-inspect-results)
- [Save your work and return later](#save-your-work-and-return-later)
- [PuTTY and VS Code appearance](#putty-and-vs-code-appearance)

## Start your workspace

From the normal login shell, go to your project and choose one entry method:

If this site supplies Apptainer through a module, load its normal runtime module first. Remembering that setup automatically is a [planned improvement](runtime-setup.md); it is not enabled in the current release.

```bash
cd /path/to/project
ws session
```

`ws session` enters the workspace and opens three tmux windows: **1 workspace**, **2 editor**, **3 agents**. Press and release Ctrl-B, then press the window number. The agents window is an ordinary shell until you start an agent. The managed session keeps its container available when you detach.

For a single shell, use `ws enter` instead. You can run plain `tmux` inside it; that uses the packaged tools and defaults, but does not keep the container independently alive after its entering shell ends. Start managed `ws session` from the native login shell, not from inside `ws enter`. You do not need a site name, host tmux module, or `--host-jobs` for this workflow.

Inside the workspace, `ws tools` lists the installed versions. `printf '%s\n' "$WS_RELEASE"` shows this shell's release. Your module environment and native commands remain available. In particular, `find` comes from the host, while `fd` is packaged in the workspace; `command -v find fd` shows their locations.

## Try a complete workflow

The repo includes a tiny [practice project](../examples/workflow/) with Python, a shell script, YAML, JSON, CSV, and a sample log. After installation, copy it from the repo checkout into a new directory in your home and start a session:

```bash
practice_dir=$(mktemp -d "$HOME/ws-practice.XXXXXX")
cp -R examples/workflow/. "$practice_dir/"
cd "$practice_dir"
ws session
```

This keeps your edits separate from the repository. The sample contains no scheduler submission command. Its log and reports are synthetic fixtures, not output from a real job.

1. In window 1, run `ll`, then `eza --tree --level=2 --icons=never .` to see the project.
2. Run `fd --type f --extension py . src` to locate Python files. Run `rg -n 'tolerance' src config` to find the setting in file contents.
3. Type `nvim `, including the trailing space, and press **Ctrl-T**. Type `solver`, choose the path, and press Enter. The path is inserted into the shell command. Press Enter again to open it.
4. In Neovim, press Esc, then **Space f g**. Type `tolerance` and select a match to open its file at the matching line. **Space f b** switches between opened files.
5. Try changing the solver's default tolerance from `1e-6` to `1e-7`: move to it, use normal editing, then Esc and `:w`. Use `:q` to return to the shell when ready. The sample YAML is a separate search example; this toy solver does not read it.
6. Run `just --list`, `just check`, and `just run`. The first lists recipes, the second checks Python/shell style, and the third runs a tiny local calculation with host Python.
7. Read results with `rg -n -i 'error|warning' logs`, `jq '.run' reports/run.json`, and `mlr --csv sort -n seconds reports/timings.csv`.
8. Press **Ctrl-R**, type `just check`, and press Enter to put it back on the command line. Review it, then press Enter to run it. Detach with **Ctrl-B d**. Re-run `ws session` from this same directory on the same login node to return.

Once those steps feel natural, use the same sequence in a real project: **locate → search → edit → check → review → submit**. The following sections build on that routine.

## Move around and reuse commands

`ll` uses eza with icons disabled. `..` moves to the parent directory and `cd -` returns to the previous directory. Use **Alt-C** to choose a subdirectory interactively; if the client intercepts Alt, press Esc and then c.

Zoxide learns directories you visit with `cd`. After a few visits, `z project-name` jumps to a matching directory you know; `zi project-name` lets you choose among matches. This learned list differs from Alt-C, which searches directories beneath your current location. Neither is a cluster-wide filesystem index.

At the Bash prompt:

| Want to… | Use |
| --- | --- |
| Repeat or adapt a past command | Ctrl-R, type a fragment, Enter to select, edit, Enter to run |
| Supply a filename without retyping it | Type the command and a space, then Ctrl-T |
| Move across a long command | Ctrl-A to its beginning, Ctrl-E to its end |
| Remove/reinsert text | Ctrl-U before cursor, Ctrl-K after cursor, Ctrl-W previous word, Ctrl-Y reinsert |
| Stop the foreground command | Ctrl-C |
| Clear the visible terminal | Ctrl-L |

These are Control keys in the remote terminal, including on a Mac client. Command-R is not the workspace history binding. Personal Readline settings can override the defaults. History persists between workspace shells; another already-open shell does not automatically import every new entry. `history -n` reads entries appended since it last read the history file.

## Find names, search contents, and choose a result

Use **fd/find for paths**, **rg for text inside files**, **fzf to choose from candidates**, and **bat to preview**. You can pipe the output of a search into a chooser. These examples start at the project directory, keeping the search bounded.

### Find files by name

```bash
fd --type f --extension py . src       # Python paths under src
fd --type f 'solver' .                 # Names containing solver (a regex)
rg --files -g '*.sh'                   # Shell paths under this project
find logs -type f -name '*.log' -mtime -2 -print
```

The last command uses the site's `find` for a modification-time condition. Quote wildcard patterns so the search program receives them. `fd` and `rg` normally skip hidden and ignored files; `find` does not read `.gitignore`. For a deliberate wider search in this project, `fd --hidden --no-ignore --exclude .git 'solver' .` includes hidden and ignored entries. Avoid starting a recursive search at a whole archive or shared filesystem when a project subdirectory will do. [fd usage](https://github.com/sharkdp/fd#usage), [ripgrep guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md)

### Choose a filename and preview it

```bash
fd --type f --print0 . . |
    fzf --read0 --preview 'bat --color=always --style=numbers --line-range=:160 -- {}'
```

Type fragments of a filename, use Up/Down to select, Enter to print the chosen path, or Esc to cancel. The preview displays its first 160 lines. This command only selects a path; it does not open the editor. fzf's `{}` placeholder is the selected entry and is shell-escaped by fzf. The zero separators keep filenames containing spaces or newlines intact as candidates. [fzf preview behavior](https://github.com/junegunn/fzf#preview-window)

Yes, the same chooser works with `find`:

```bash
find . -path './.git' -prune -o -type f -print0 |
    fzf --read0 --preview 'bat --color=always --style=numbers --line-range=:160 -- {}'
```

This excludes `.git` but still includes other hidden/ignored directories. Use a narrower starting directory, such as `src`, when appropriate.

For a picker that **opens the selection**, this optional Bash helper carries the selected filename safely into Neovim:

```bash
fedit() {
    local selected
    if IFS= read -r -d '' selected < <(
        fd --type f --print0 . . |
            fzf --read0 --print0 \
                --preview 'bat --color=always --style=numbers --line-range=:160 -- {}'
    ); then
        nvim -- "$selected"
    fi
}
```

Paste the function into a workspace Bash shell, then run `fedit`. Canceling leaves the shell alone. To keep it, add it to your personal [workspace Bash configuration](dotfiles.md#small-personal-changes). **`fedit` is an example, not a preinstalled command.** The `--print0`, `read -d ''`, and quoted argument avoid splitting one filename into multiple editor arguments.

### Search contents, then decide what to open

```bash
rg -n --smart-case 'tolerance' src config
rg -n -F 'MPI_Init(' src                  # literal text in your actual C project
rg -n -i 'error|warning' logs
rg -l 'tolerance' src config             # filenames only
```

`-n` adds line numbers, `-F` means literal text, `-i` ignores case, and `-l` lists files with a match. Smart-case ignores case for a lowercase query and respects case when the query contains uppercase letters. A no-match exit status from `rg` is normal.

To choose among files containing a setting:

```bash
rg -l -0 'tolerance' src config |
    fzf --read0 --preview 'bat --color=always --style=numbers --line-range=:160 -- {}'
```

To jump directly to a matching line, open Neovim and use **Space f g** instead of parsing `file:line:text` yourself. Use **Space f f** when you know the filename. Neither requires a language server.

## Edit and review in Neovim

Start Neovim from the project root so its pickers search the intended tree. Press Esc before the Space shortcuts. **Space ?** shows the configured key guide.

For basic editing, `i` enters Insert mode, Esc returns to Normal mode, `:w` saves, and `:q` closes the current window. Use `/text` to search within a buffer, n/N for next/previous match, u to undo, and Ctrl-R to redo. Neovim's Ctrl-R is redo; Bash's Ctrl-R is history search.

The daily editing loop is:

1. **Space f f** to choose a file, or **Space f g** to find text across the project.
2. **Space f b** to switch among open buffers. `:vsplit` and `:split` create editor splits; **Space w h/j/k/l** moves between them and adjacent tmux panes.
3. With language assistance available, use **g d** for a definition, **g r r** for references, **Space f s** for document symbols, and **Space c d** for diagnostics.
4. Use Ctrl-N/P to choose a completion and Ctrl-Y to accept. **Space c a** offers code actions; **Space c r** renames a symbol through the language server.
5. Use **Space c f** for explicit formatting, then `:w` to save. Ordinary saves do not automatically format files.

Treesitter supplies syntax highlighting for the bundled languages. It does not itself provide completion or understand your MPI headers. Python, Bash, and Fortran assistance is packaged; C/C++ assistance uses host `clangd` and your project's compilation database. Activate the intended project Python environment **before** opening Neovim. The [editor guide](editor-and-agents.md#neovim-defaults) describes the exact providers and large-file limits.

In a real Git project, use **Space g p** to preview a changed hunk and **Space g s** to stage that hunk. Staging is a change to Git's index; it is not a commit. Then review from a shell:

```bash
git status --short
git diff
git diff --staged
```

Delta supplies the pager unless your Git configuration already chooses one. `lazygit` provides a visual alternative. `difft old.py new.py` compares two explicit versions structurally. The practice copy is not automatically a Git repository; Git review applies to your own repository unless you explicitly initialize the copy.

For agent work, keep the editor in window 2 and run your configured `codex` or `claude` in window 3 from the same project. Save your editor changes before asking for edits. Unmodified buffers reload external changes on checks/focus; an unsaved buffer produces a conflict instead of silently losing your work. Review the resulting diff and run the same checks you use for manual changes. Running agents against the same shared worktree simultaneously can still create conflicting edits.

## Check code and make project tasks repeatable

Start with checks that report changes without applying them:

```bash
shellcheck jobs/check.sh
shfmt -d jobs/check.sh
ruff check src
ruff format --check src
```

`shfmt -w` and `ruff format` rewrite files; choose them when you want to apply formatting. The practice [Justfile](../examples/workflow/Justfile) groups the checks behind `just check`. `just` runs project-defined recipes; it does not know how to build or submit an arbitrary project by itself. Put your existing build/test commands in a project recipe when you want one repeatable entry point, using the site's compilers and job scripts.

For a Python project, after loading its intended site Python:

```bash
uv venv --python python3 .venv
source .venv/bin/activate
python --version
```

Install dependencies using that project's documented lockfile/mirror/offline procedure. The workspace's uv wrapper defaults to not downloading Python. The virtual environment is project-owned; it does not change the packaged tools.

Optional tools are installed but need deliberate use:

- `watchexec -w src -e py -- ruff check src` runs once immediately and again on relevant changes. Ctrl-C stops it. Keep watches narrow on shared storage.
- `direnv` has no automatic Bash hook enabled by default. For a project whose `.envrc` you have reviewed, `direnv allow .` authorizes it and `direnv exec . COMMAND` uses that environment for one command. Add `eval "$(direnv hook bash)"` to your personal workspace Bash file only if you want automatic loading on directory changes.
- `hyperfine --warmup 1 --runs 5 'python3 src/solver.py'` deliberately repeats this tiny calculation. Use allocated resources for real benchmarks and commands that make sense to run repeatedly.

## Submit jobs and inspect results

Use your existing native batch scripts and site procedure. The workspace does not invent resource flags or add its container to your batch jobs:

```bash
sbatch job.slurm       # Slurm: your real site script
qsub job.pbs          # PBS: your real site script; choose the applicable command
```

The practice project has no submit-ready PBS/Slurm script. For jobs that export the submitting environment but will run outside this image, use `ws job-env --` before your usual client when needed to strip workspace-only paths. For example, `ws job-env -- sbatch job.slurm` retains the native command and arguments. Keep your normal module/setup commands in the job script.

You can start an interactive job from a tmux pane. The client connection stays in that login-node pane; the scheduler starts a new shell on the compute node. There, run `ws enter` to use the workspace tools. Your login-node container does not move to the compute node. Follow the [interactive-job guide](editor-and-agents.md#interactive-jobs-and-tmux) for the environment prefix, site-specific resource options, and shared-file requirements.

For output, choose the smallest useful view:

```bash
tail -n 80 logs/run.log
rg -n -i 'error|warning' logs
lnav logs/run.log
jq '.run | {case, ranks, seconds}' reports/run.json
yq '.solver.tolerance' config/run.yaml
mlr --csv sort -n seconds reports/timings.csv
```

Use `tail -f /path/to/live.log` to follow a running log, then Ctrl-C to stop following. Use `htop` or `btop` for processes visible on the current node; use native `squeue`/`qstat` for the job queue. `df -h .` reports filesystem capacity; `du -sh ./results` or `ncdu -rr -x ./results` measures that directory by scanning it. `spf .` is the visual file browser; its help is `?`, and its plain-font defaults are already configured.

## Save your work and return later

Before leaving an editor, `:wall` writes all writable modified buffers. **Space w s** saves the editor layout; **Space w r** restores it. A normal Neovim exit saves the layout, and opening `nvim` with no file arguments interactively in the same directory restores it. A layout snapshot does not contain the text of unsaved buffers.

Persistent undo helps with previously saved edits. Swap files can help recover unsaved edits after a crash: reopen the original file and follow Neovim's recovery prompt, or use `nvim -r path/to/file`. Recovery is limited to what reached the swap file. The [state paths and recovery notes](dotfiles.md#persistent-state) explain where those files live. Save before allocation expiry; neither swap nor tmux extends walltime.

In tmux, **Ctrl-B d** detaches; `ws session` on the same node/project/release reconnects. **Ctrl-B Ctrl-S** saves a layout snapshot; **Ctrl-B Ctrl-R** restores one into an appropriate new session. Snapshots also save periodically and on detach, but automatic restore is disabled. The defaults restore layout/directories and shells, not running jobs or agent/editor processes, and do not capture pane contents. Live sessions, layout snapshots, and saved files are three different things.

Close a shell pane with `exit` or Ctrl-D at an empty prompt. Closing the last pane/window ends the session and its keeper. When a compute allocation ends, its processes end; files on persistent shared storage remain, while node-local temporary data follows the site's cleanup policy.

For an update, return to your repository checkout in the native shell and run `git pull --ff-only && ./setup`. Start a new `ws enter` or `ws session` afterward. Existing sessions keep their original image; updates preserve your personal preferences and saved state.

## PuTTY and VS Code appearance

The default prompt, editor, and terminal apps use ordinary fonts. You do not need Nerd Fonts. For a PuTTY saved session, choose a monospace font, UTF-8 translation, and ANSI/256-color support. A matching palette uses background **#282C34**, foreground **#ABB2BF**, and cursor **#61AFEF**. Keep a terminal type supported by the host; use `xterm-256color` only when `infocmp xterm-256color` succeeds. Font and palette settings belong to the client. [PuTTY appearance and color settings](https://the.earth.li/~sgtatham/putty/0.85/htmldoc/Chapter4.html#config-colours)

For VS Code, the optional [terminal settings example](../examples/vscode-terminal.json) uses the same palette. Inspect and merge the keys you want into your existing settings; do not replace unrelated preferences.

Use `WS_COLOR=256 ws session` or `WS_COLOR=truecolor ws session` from the native shell when choosing a mode for a new session. `WS_COLOR=never ws enter` disables the shared color styling. These settings affect workspace defaults, not every application universally. Leave TERM alone inside tmux, where it describes tmux's terminal. The [dotfile guide](dotfiles.md) covers persistent preferences.
