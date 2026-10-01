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

## PROMPT_COMMAND is read-only or the workspace label is missing

Some sites initialize Bash modules with a read-only `PROMPT_COMMAND`. In 0.7.3-preview1, the workspace's attempt to add its prompt hook then printed `PROMPT_COMMAND: readonly variable` and left the `ws:SITE CONTEXT@NODE` label empty. **0.7.3-preview2** checks that attribute and uses a prompt fallback that retains the site hook, workspace label, color, and changing directory. The fallback omits the workspace Git branch and exit-status decorations.

Check a new shell's state without printing the hook's contents or any keys:

```bash
printf 'release=%s workspace=%s layout=%s\n' "${WS_RELEASE:-unset}" "${WS_CONTAINER:-unset}" "${WS_LAYOUT:-unset}"
if readonly -p | grep -Eq '^declare -[[:alpha:]]*r[[:alpha:]]* PROMPT_COMMAND(=|$)'; then echo prompt_command=readonly; else echo prompt_command=writable; fi
[[ ${PROMPT_COMMAND[*]:-} == *'_ws_prompt'* ]] && echo hook=present || echo hook=missing
type -t module
```

Run this inside `ws enter` on the affected and working systems. If the affected shell reports a writable hook, or the new image still lacks its label, save the exact startup error and the check's output locally for comparison. The command above does not print a key or the hook's value. Start a new workspace after updating; attaching an existing server returns to its original image.

## Configuration form text is too dark to read

The 0.7.0 form used Gum's fixed gray headings, placeholders, and help text. Those can have poor contrast on a black background. **0.7.1-preview1** uses your terminal's normal foreground/background colors for the interactive form, including its choices and help; it does not depend on detecting a dark theme through SSH or tmux.

Until you update and enter a fresh workspace, use basic prompts:

```bash
ws configure codex --plain
# Or:
ws configure pi --plain
```

Choose the existing gateway and **Edit connection** to review its endpoint and model. **Rotate key** changes only the credential. Keys remain hidden intentionally; ordinary fields and their questions should be readable. No PuTTY update is required to use the basic prompts. See the [profile guide](agent-profiles.md) for editing and key rotation.

## Tmux says the pane is dead or looks frozen after exit

If a native `top`/`ps` shows a tmux process in **D**, start with the
[host-only diagnostic](session-locations.md#diagnose-a-stalled-attachment-from-the-host).
D is an uninterruptible kernel wait, often I/O; it does not mean detached. An idle
tmux server in S can be normal while a separate attaching client is blocked.
Do not stop the server or its filesystem daemon merely to recover a viewer.

Releases before 0.6.1 retained an exited pane with `remain-on-exit on`. There was no shell left to read normal input. A fresh 0.6.1 server defaults to `off`: Ctrl-D at an empty prompt or `exit` closes the pane; closing the final pane/window returns to the parent shell. Ctrl-C interrupts a command without normally closing Bash.

Ctrl-B then d detaches even from a retained dead pane. Ctrl-B then `:` opens tmux's command prompt; inspect locally with:

```text
display-message "dead=#{pane_dead} exit=#{pane_dead_status} command=#{pane_current_command}"
```

`dead=1` means the pane's process exited. Ctrl-B then x and its confirmation closes that pane; use it on a finished pane, not on work you want to keep. In an older server, `set -g remain-on-exit off` at the tmux command prompt changes future pane-exit behavior. A personal `tmux.conf` can still override the default. See [current tmux behavior](editor-and-agents.md#tmux).

Use managed `ws session` from the native login shell when you want the session to outlive an entering shell. Plain tmux inside `ws enter` uses the shared settings but has no separate keeper. Neither method extends an allocation's lifetime.

## Tmux commands report the wrong server or layout saving is missing

The wrapper through 0.7.1 adds a release-default socket even inside a managed project session. Bare `tmux` commands and layout helpers can therefore contact another server or report a missing socket. **0.7.2** preserves the current session's socket unless you explicitly select another one.

Update and start a fresh `ws session` to get the corrected wrapper and helper initialization. Keep existing job sessions alive until their work is finished. For a command in an older session, use **Ctrl-B :** to address that server directly, or specify its socket explicitly from its pane: `tmux -S "${TMUX%%,*}" COMMAND`. The [release notes](releases/0.7.2-preview1.md) describe the fix and remaining limits.

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
