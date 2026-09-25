# Workspace troubleshooting

Current workflow: **0.7 thin image plus the repo's `./setup` command**. The [validation record](validation.md) identifies the local checks performed; the [0.4 diagnostic replay](legacy/core-troubleshooting.md) remains historical. Keep cluster-specific paths, profiles, environment dumps, and results on the cluster. For a saved Apptainer path/module that is no longer available, use [runtime setup](runtime-setup.md) from the native shell.

## Missing ws or only a skills directory

From the repo checkout in the native login shell:

```bash
git pull --ff-only && ./setup
```

The setup command needs no old `ws`. It downloads and verifies the complete release and creates the runtime, launcher, and Bash PATH hook. Open a new Bash session afterward. A `~/.local/share/hpc-workspace/skills` directory is separate and does not establish that the runtime was installed.

For a first clone, custom startup path, nondefault prefix, or offline machine, use [setup and startup](thin-start.md). If installation reported an error, resolve that error locally before expecting activation to work.

## Download stopped or update appears unchanged

Rerun `./setup`; verified downloads are reused and partial files can resume. A checksum mismatch prevents installation. A TLS/proxy error needs the site's approved network/certificate configuration; do not turn off certificate verification.

The repo's recommendation selects the version, so use `git pull --ff-only` before setup. A running shell or tmux server retains its original image. Inside it, `printf '%s\n' "$WS_RELEASE"` and `ws tools` show that session's version. Return to the native shell and start a new `ws enter` or `ws session` to use the selected release.

## Tmux says the pane is dead or looks frozen after exit

Releases before 0.6.1 retained an exited pane with `remain-on-exit on`. There was no shell left to read normal input. A fresh 0.6.1 server defaults to `off`: Ctrl-D at an empty prompt or `exit` closes the pane; closing the final pane/window returns to the parent shell. Ctrl-C interrupts a command without normally closing Bash.

Ctrl-B then d detaches even from a retained dead pane. Ctrl-B then `:` opens tmux's command prompt; inspect locally with:

```text
display-message "dead=#{pane_dead} exit=#{pane_dead_status} command=#{pane_current_command}"
```

`dead=1` means the pane's process exited. Ctrl-B then x and its confirmation closes that pane; use it on a finished pane, not on work you want to keep. In an older server, `set -g remain-on-exit off` at the tmux command prompt changes future pane-exit behavior. A personal `tmux.conf` can still override the default. See [current tmux behavior](editor-and-agents.md#tmux).

Use managed `ws session` from the native login shell when you want the session to outlive an entering shell. Plain tmux inside `ws enter` uses the shared settings but has no separate keeper. Neither method extends an allocation's lifetime.

## bat reports an SSL or library error

In the failing shell, `command -V bat` identifies whether it is the packaged executable, a host program, or a personal alias. From a native shell with the release installed, try a small synthetic input:

```bash
ws enter -- bat --version
printf 'workspace bat check\n' | ws enter -- bat --paging=never --color=never
```

The thin release supplies private dependencies for its tools. Local tests include a deliberately incompatible host `libssl.so.3` and pass for packaged bat; they do not identify every possible site error. A missing library or undefined symbol is different from a TLS certificate-validation error. Keep the exact error and executable resolution locally. Avoid copying arbitrary host libraries into the image or globally replacing `LD_LIBRARY_PATH` based only on the word SSL.

## Locale warnings

The 0.6 image supplies a matching locale archive for its packaged tools, preserves available host locales, and falls back for unsupported values. Start a fresh release session first; an old tmux server retains its old environment. A personal startup file can also set an invalid locale after workspace initialization. The [locale notes](editor-and-agents.md#locale-warning) explain the tested case without changing host locale policy.

## Missing shortcut, icons, or editor assistance

- Try Ctrl-R at a **workspace Bash prompt**. In Neovim, Ctrl-R is redo. In a picker, Esc cancels. Personal `inputrc` settings can replace bindings; Alt-C can be sent as Esc then c.
- Press Esc before Neovim's Space shortcuts. Use Space ? to inspect them. File/text picking works independently of language-server setup.
- A symbol/definition lookup needs a suitable attached language server. C/C++ uses host clangd and the project's headers/compilation database. Activate your project Python environment before opening the editor.
- Use the [PuTTY/VS Code appearance guide](daily-workflow.md#putty-and-vs-code-appearance). Ordinary fonts are supported; TERM should describe the real terminal. Changing colors in an already-running server does not restart its applications.

## A host command or filesystem is unavailable

Check the same command/path in the native shell first. Enter after loading the site's normal modules. `ws enter --dry-run` displays the local integration plan; `findmnt -T /path/to/project` identifies a path's mount from the current context. Mounts introduced after startup may need a fresh entry. Having paths bound does not prove every site authentication helper, MPI stack, or nested container engine works; use the site's normal local checks.
