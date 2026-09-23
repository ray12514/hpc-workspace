# Tmux startup and bat errors

Updated 2026-09-23 for 0.4.0-preview1. The reported symptoms are an approximate tmux “Shell …” message followed by an inactive-looking session, and an unspecified bat SSL/library error. Neither exact failure has been reproduced locally. No runtime fix or cluster compatibility is claimed here.

Run these checks on the affected machine using its normal approved workflow. Keep command output and all site details there. If sharing is permitted, only the generic error wording and whether it happened in the native shell or `ws enter` are useful here; do not send profiles, environment dumps, paths, hostnames, or job data.

## What the local replay established

A disposable Linux Docker fixture used the released 0.4 image, real host-launcher code, tmux 3.4, Bash, Neovim, and bat. It had no network, a read-only image/source mount, and disposable state. An explicit Apptainer stand-in dispatched to the real image entrypoint, so this checked session construction and application behavior, **not** the real Apptainer boundary or target cluster.

- `ws session --detach` created the editor, host, and workspace windows.
- Commands sent through tmux wrote readiness markers from both Bash windows and Neovim.
- Bat rendered a changed file in a synthetic Git repository and exited successfully.
- A deliberate `exit 23` left the workspace pane visible with `pane_dead=1` and `pane_dead_status=23`.

The last result follows the shipped `remain-on-exit on` setting in `image/config/tmux/tmux.conf`. An exited pane remains visible so its error can be read. This is verified behavior, not evidence that it caused the reported incident. Reconnecting to the same workspace session reuses its existing panes.

The image's `/usr/bin/batcat` dynamically depends on `libgit2.so.1.7`, `libssl.so.3`, and `libcrypto.so.3`; all resolved within the image in the clean local check. That does not establish which executable or libraries were selected during the reported failure.

## Inspect a workspace pane without replacing the session

In the affected pane, press **Ctrl-b**, then **:** to open tmux's command prompt. Enter:

```text
display-message "dead=#{pane_dead} exit=#{pane_dead_status} command=#{pane_current_command}"
```

`dead=1` means the pane's command exited. Read its retained error locally. `dead=0` means a process still exists; it does not prove that the application is responsive. If the tmux command prompt responds, the server is processing input even if the pane's application is not.

**Ctrl-b n** selects the next window; the workspace recipe includes a native `host` window. **Ctrl-b d** detaches while leaving the session intact. Avoid killing all tmux servers or deleting state as a diagnostic step.

For a separate baseline check, return to an ordinary native shell on the approved login host, outside an allocation and outside tmux. Run:

```bash
tmux -V
tmux -L "ws-startup-check-$$" -f /dev/null new-session -s check '/bin/bash --noprofile --norc'
```

This uses a separate socket and no workspace configuration. Type `exit` in that test shell when finished. Compare whether the same generic error occurs; this comparison alone is not a diagnosis. The workspace configuration has been tested with tmux 3.4; older or differently built host versions have not been validated by this replay.

## Exercise bat outside tmux

From the ordinary native shell, use the same image/site/project selection as the failing launch. With a previously saved image selection:

```bash
ws enter -- bat --version
printf 'workspace bat check\n' | ws enter -- bat --paging=never --color=never
```

If selection is not saved, add your usual `--image`, `--site`, and `--project` options before `--`. These commands need no network or private file input. Record locally whether failure occurs on startup, while reading input, or only with a particular project/file. A successful stdin check does not exercise every Git integration path.

In the shell where the original command failed, `command -V bat` identifies whether `bat` resolves to an alias, function, or executable. Inspect that result locally; a native `bat` and the image's `bat` need not be the same program.

A message such as `libssl.so... cannot open shared object file`, `version ... not found`, or `undefined symbol` concerns loading libraries or symbols. A certificate-verification message concerns a different operation. The exact generic wording is needed to distinguish them. Do not copy arbitrary host SSL libraries into the image, disable certificate verification, or globally change library paths based only on the word “SSL”.

## Next diagnostic boundary

The missing evidence is the exact generic error and launch context. Once those are available, create a matching local failing case before changing runtime behavior. If site policy prevents sharing even that information, use this guide for local diagnosis and keep the results on the system. The [native tools proposal](research/native-tool-layer.md) is a separate architectural change and does not establish a fix for either report.
