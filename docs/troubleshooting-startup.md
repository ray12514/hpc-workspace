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

For a missing `ws:` label or `scp` reporting bad ownership on an SSH config file, run this **once from a native shell in the repo checkout**. It enters and exits its own fresh interactive workspace, so you do not need to run a second block inside `ws enter`:

```bash
git pull --ff-only && python3 scripts/diagnose-workspace-entry.py
```

Paste its complete short report. It reports whether the actual interactive prompt displayed the workspace label, release/layout, prompt hook/template flags, and native versus workspace SSH executable and config-file ownership. It does not print the prompt text, site banner, SSH config contents, hook contents, or keys; it does not contact another machine. If `ssh_config_path=not_found`, rerun it with `--ssh-config /exact/path/from/the/scp/error`. It leaves existing tmux sessions alone. The error path might use either `/etc/ssh/config.d` or `/etc/ssh/ssh_config.d`.

The thin layout bind-mounts the host `/etc` read-only. On the reported rootless RHEL system, a root-owned host SSH config appeared as UID `65534` inside the workspace; OpenSSH refused that owner before connecting. **0.7.3-preview4** binds private, temporary, user-owned copies of the system SSH client config and its `Include` files into each fresh entry. It does not change the host files. If the transfer still fails, this report shows whether the owner mapping was corrected and whether both shells resolve the same client. Until resolved, run `scp` from the native shell where it succeeds.

Some sites initialize Bash modules with a read-only `PROMPT_COMMAND`. In 0.7.3-preview1, the workspace's attempt to add its prompt hook then printed `PROMPT_COMMAND: readonly variable` and left the `ws:SITE CONTEXT@NODE` label empty. **0.7.3-preview2** checks that attribute and uses a prompt fallback that retains the site hook, workspace label, color, and changing directory in a local reproduction. The fallback omits the workspace Git branch and exit-status decorations. The error still occurs on a reported RHEL system, so that release is not a confirmed fix for that site.

**0.7.3-preview3** addresses the reproduced cause: zoxide's Bash initialization also writes `PROMPT_COMMAND`. Normal `ws enter` and managed windows now prepare the site's module functions and prompt hook in a short-lived Bash, then start the final workspace Bash with the site hook retained and writable. The workspace restores its prompt after the site hook runs. The packaged image passes a synthetic site hook that both makes `PROMPT_COMMAND` read-only and replaces `PS1`; the affected RHEL system still needs a fresh-session check. From the native shell, update with `git pull --ff-only && ./setup`, then start a **new** `ws enter`. An existing tmux server keeps its original image.

The affected system confirmed the read-only error was gone in preview3, but the label still disappeared. Its prompt hook remained read-only and the workspace hook was missing. **0.7.3-preview4** rechecks after personal startup and restores the workspace label after a single read-only site function runs. The packaged PTY regression reproduces and fixes that late-hook case. Test in a new entry; an old tmux server keeps its old prompt behavior.

To isolate where startup is happening on the affected system, run these three commands **one at a time from a native shell**, outside `ws enter` or `ws session`, after updating this checkout with `git pull --ff-only`. Each starts a fresh Bash, prints a distinct marker, and exits. They do not print the API key or the value of `PROMPT_COMMAND`; a site startup file might print other local details, so redact those before sharing output.

```bash
command bash --noprofile --norc -ic 'printf "NATIVE_CLEAN_OK\n"'
ws enter -- /workspace-tools/bin/bash --noprofile --norc -ic 'printf "WS_CLEAN_OK release=%s\n" "${WS_RELEASE:-unset}"'
ws enter -- /workspace-tools/bin/bash --noprofile --rcfile /workspace-tools/config/bashrc -ic 'printf "WS_RC_OK\n"'
```

For **each** command, record whether the site login header appeared, whether `PROMPT_COMMAND: readonly variable` appeared, and whether its `*_OK` marker printed. The first command tests the native Bash without profile or rc files. The second tests workspace entry and its packaged Bash without a Bash rc file. The third adds the workspace Bash rc file, which may source the site's module initialization. This comparison identifies the startup boundary; it does not by itself identify the exact site file or authorize changing site configuration. These checks leave existing tmux sessions alone.

If only the third command prints the read-only error, type `exit` to leave any interactive workspace, pull the latest repo, and run this from the **native shell**. The diagnostic refuses to run inside a workspace because a nested entry can inherit a different Bash/module state and give a false negative:

```bash
bash scripts/diagnose-prompt-startup
```

This first repeats the **actual `--rcfile /workspace-tools/config/bashrc` startup command**, then runs a traced rcfile that sources the same workspace config during Bash startup. Report `real_rc_readonly_error`, `traced_rc_readonly_error`, any `WS_TRACE` location, and both entry statuses. The earlier version of this diagnostic used `--norc` and sourced the config later from `-c`; that was not the failing startup path and could return a false negative. The revised check prints only file/line locations from its trace, not command text, prompt values, or credentials. It keeps private temporary files only for the duration of the check and removes them afterward. Site startup may still print its normal header to the terminal; redact site details before sharing. The source location is a lead, not proof that the indicated line itself is wrong.

Check a new shell's state without printing the hook's contents or any keys:

```bash
printf 'release=%s workspace=%s layout=%s\n' "${WS_RELEASE:-unset}" "${WS_CONTAINER:-unset}" "${WS_LAYOUT:-unset}"
if readonly -p | grep -Eq '^declare -[[:alpha:]]*r[[:alpha:]]* PROMPT_COMMAND(=|$)'; then echo prompt_command=readonly; else echo prompt_command=writable; fi
[[ ${PROMPT_COMMAND[*]:-} == *'_ws_prompt'* ]] && echo hook=present || echo hook=missing
type -t module
```

Run this inside `ws enter` on the affected and working systems. If the affected shell reports a writable hook, or the new image still lacks its label, save the exact startup error and the check's output locally for comparison. The command above does not print a key or the hook's value. Start a new workspace after updating; attaching an existing server returns to its original image.

In the 0.7.3-preview2 read-only fallback, `hook=missing` is expected because Bash will not let the workspace add a hook. Preview3 can also report a missing workspace hook if a later startup file makes the site hook read-only; preview4 handles a single site function in that state. To check why the label is absent **inside an interactive `ws enter` shell**, run:

```bash
declare -F _ws_prompt >/dev/null && echo prompt_function=present || echo prompt_function=missing
[[ -n ${_ws_label:-} ]] && echo label_value=set || echo label_value=empty
[[ ${PS1:-} == *'${_ws_label}'* ]] && echo prompt_template=workspace || echo prompt_template=other
```

These checks report only presence flags; they do not print `PS1` or its contents. The earlier `-ic` marker commands exit back to the native shell, so run this block after a separate interactive `ws enter`.

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
