# Daily appearance and job submission

[View the running Bash, tmux, and Neovim configuration](previews/README.md).

Release **0.4.0-preview1** makes [dotfiles an explicit part of the workspace](dotfiles.md). Shared defaults ship with the image; missing personal settings are created under `~/.config/hpc-workspace/` and existing preferences are preserved. It also enables fzf's Ctrl-R history selection, Ctrl-T path selection, Alt-C directory selection, and enhanced Tab completion.

Release **0.3.0-preview1** adds [optional Inspector profile import](inspector-integration.md). After `ws init`, omit `--site` from the examples below to use the saved settings. An Inspector profile is optional; `ws init --site ruth` (or `jean` / `blueback`) also saves the system default. Submission behavior and the optional host connection are unchanged by this release.

Release **0.2.0-preview1** adds a shared Bash/tmux/Neovim appearance and native PBS/Slurm submission. Transfer both the new SIF and its matching source bundle using the [transfer guide](transfer.md). A running shell keeps its old image; exit and re-enter after selecting the update. Existing tmux sessions keep their original configuration and image until recreated. Keep the previous release for rollback.

Reconnecting also retains the session's original `--host-jobs` choice. For an immediate fresh shell, use `ws enter --host-jobs` from the host window. To replace the full tmux session, save your files/layouts and finish interactive work, then use `Ctrl-b :` followed by `kill-session`. This closes that session's panes; re-run `ws session` to create it with the new image and options.

## Start your day on a login host

Load the site's Apptainer, scheduler-client, and (for sessions) tmux modules in the host shell. Select your verified SIF with `ws use`, then start from your project:

```bash
ws session --site ruth --project "$HOME/my-project" --host-jobs
```

Use `jean` or `blueback` on those systems. This opens editor, native host, and workspace-shell windows in host tmux. `Ctrl-b n` moves to the next window; `Ctrl-b d` detaches. Re-run the same command on the same login host to reconnect. The host window remains the place to request interactive allocations and use arbitrary native scheduler commands.

For a single container shell without tmux:

```bash
ws enter --site ruth --project "$HOME/my-project" --host-jobs
```

`--host-jobs` enables `ws submit` and `ws jobs` inside that login-host container. Without it, use those commands in the host window. The option cannot be started inside an allocation and does not connect a compute node back to the login host.

The prompt uses ordinary text and requires no icon font:

```text
ws:ruth login@login-host  ~/my-project [main]
$

ws:jean compute@compute-node job:12345  ~/my-project [main]
exit:1 $
```

The second example shows a previous command returning 1. A selected GPU passthrough mode appears as `gpu:cuda` or `gpu:rocm`; it does not claim that a toolkit has been installed or validated. Git branch lookup is cached for five seconds or until the directory changes and does not scan the working tree. The prompt never polls the scheduler. Set `WS_GIT_PROMPT=0` before entry to disable branch lookups.

## Submit an existing native batch script

Inside a shell started with `--host-jobs`:

```bash
ws submit --dry-run ./job.pbs
ws submit ./job.pbs
ws jobs
```

On Jean/Blueback, use your Slurm script. From the native host window, add the site explicitly:

```bash
ws submit --site jean ./job.slurm
ws jobs --site jean
```

No development container is added to the job. The script controls the job runtime. Keep account, queue/partition, resource, output, and dependency options in the native script. PBS and Slurm requests are not translated into one another. The generic [PBS](../examples/jobs/hello.pbs) and [Slurm](../examples/jobs/hello.slurm) examples print the job ID, hostname, and working directory; add your site's required directives locally before submitting them.

The current directory is the submission directory. `--cwd /absolute/project/run` chooses another one, while the script argument is resolved relative to the caller's original directory. PBS jobs should explicitly `cd "$PBS_O_WORKDIR"`; the example Slurm script likewise uses `$SLURM_SUBMIT_DIR`. Output file handling remains the scheduler's responsibility. Script and working-directory paths passed from a container must resolve under its selected project or `--work` directory, at the same absolute paths on the host. Other mounts are not automatically submission roots.

`--dry-run` validates paths and prints arguments plus environment **names**, without calling a scheduler or printing variable values. Actual submissions relay native stdout, stderr, and exit status, including the native job ID. Output is limited to 512 Ki characters per stream. There is no automatic retry. If a timeout or lost connection leaves the outcome uncertain, check the host queue before submitting again.

Interactive/blocking submission modes, custom PBS directive prefixes, Slurm `--get-user-env`, and wrapper/alternate-export modes belong in the native host window. `ws` accepts batch scripts, not an arbitrary scheduler option tail. Cancellation and detailed scheduler administration also use the native host commands.

## Deliberate environment handling

The host starts its own `qsub` or `sbatch` with a selected host environment: identity/home/shell, host `PATH` and `LD_LIBRARY_PATH`, locale/time zone, known scheduler configuration pointers, `KRB5CCNAME`, and certificate paths. The exact list is `HOST_ENV` in [scheduler.py](../lib/scheduler.py). The PBS command uses `-V`; Slurm uses `--export=ALL`. Those switches export this selected environment. Slurm's command-line setting overrides a conflicting `#SBATCH --export` directive. The wrapper does not use `--export=NONE`, which can request implicit user-environment reconstruction. [Slurm sbatch](https://slurm.schedmd.com/sbatch.html), [OpenPBS qsub](https://github.com/openpbs/openpbs/blob/master/doc/man1/qsub.1B)

Container tool paths, allocation device masks, and AI keys are not automatically copied into submissions. To deliberately pass a job input, export it and name it:

```bash
export RUN_CASE=case-17
ws submit --env RUN_CASE ./job.slurm
```

Repeat `--env NAME` as needed. Reserved path, runtime, and scheduler controls cannot be overridden this way. Explicitly selecting a non-reserved credential variable would export it, so choose only variables the job needs. A script's own exports, login-shell startup, and site hooks retain their usual behavior; this feature does not sanitize arbitrary job code.

Initialize the site's module system and load the required compiler/MPI in each job using that site's supported recipe. Do not assume every variable from your interactive module environment was captured. Programs compiled against the core's Ubuntu/glibc may require the container runtime; native scientific jobs should use compatible site builds. See [build/runtime compatibility](design-direction.md#build-compatibility-is-separate-from-submission).

For an additional native client setting, add its **name**, not its value, to the local profile in the source bundle on that cluster:

```json
{
  "scheduler_env": ["SITE_SCHEDULER_SETTING"]
}
```

Combine this with the existing `binds` field if needed. Values are read from the host environment before entry. Load/change modules or settings before starting a fresh container; existing connections retain their captured environment.

## How the optional host connection works

The parent `ws enter` process creates a private, node-local Unix socket in a mode-700 temporary directory and binds it at `/workspace-host`. It checks Linux peer credentials for the same UID, accepts only `submit` and `jobs`, validates the site and allowed paths, and removes the socket when the parent exits. It listens on no TCP port. At most four requests run concurrently; excess requests receive an error without being queued for later submission. This is convenience under your existing account permissions, not a security boundary against your own programs.

The host must support local Unix sockets and Linux `SO_PEERCRED`, and the site's Apptainer settings must permit the bind. If unavailable, native-host `ws submit --site SITE` still works without the connection. Scheduler clients, their dependencies, configuration, and authentication stay on the host. No cluster information is uploaded by this mechanism.

## PuTTY and VS Code appearance

The image controls prompts and application colors. Set the client font and background on your Windows workstation. For a PuTTY saved session:

1. In **Window > Appearance**, choose an installed monospace font such as Consolas, around 12–13 points.
2. In **Window > Translation**, choose UTF-8.
3. In **Window > Colours**, keep ANSI and 256-color support enabled. On versions offering it, keep 24-bit color support enabled.
4. Set Default Background to **40, 44, 52** (`#282C34`), Default Foreground to **171, 178, 191** (`#ABB2BF`), and Cursor Colour to **97, 175, 239** (`#61AFEF`). Disable “Use system colours” if it overrides these choices.
5. In **Connection > Data**, use `xterm-256color` only where the remote host has that terminfo entry (`infocmp xterm-256color` succeeds). Save the session. Keep the site's existing terminal setting if that entry is unavailable.

These settings follow the [PuTTY manual](https://the.earth.li/~sgtatham/putty/0.85/htmldoc/Chapter4.html#config-colours). The shell does not overwrite `TERM`. Host tmux chooses an installed `tmux-256color`, `screen-256color`, or `screen` entry for its panes.

For VS Code, merge the optional [terminal settings snippet](../examples/vscode-terminal.json) into your existing user settings; merge the `workbench.colorCustomizations` object rather than replacing other customizations. It supplies the same palette without changing your shell or requiring extensions. [VS Code terminal appearance](https://code.visualstudio.com/docs/terminal/appearance)

Color controls apply before starting the workspace/session:

| Setting | Behavior |
| --- | --- |
| `WS_COLOR=auto` (default) | True color when `COLORTERM` advertises it; otherwise use terminal capabilities |
| `WS_COLOR=256` | Use the 256-color Bash/editor palette |
| `WS_COLOR=truecolor` | Opt into true color, including tmux passthrough, after confirming client support |
| `WS_COLOR=never` or `NO_COLOR=1` | Plain Bash prompt and tmux styles; leave Neovim's default theme instead of the custom palette |
| `TERM=dumb` or redirected shell output | Plain Bash prompt |

The workspace flags configure the shipped Bash/tmux/Neovim settings; they are not a universal switch for every third-party program. Personal Bash, Neovim, and tmux overrides are loaded last from `~/.config/hpc-workspace/bashrc`, `nvim.lua`, and `tmux.conf`. Readline key choices live in `inputrc`; application settings use the writable `xdg/` subdirectory. The [dotfile guide](dotfiles.md) explains loading order and updates. Change tmux color settings before creating a fresh session or explicitly reload your personal file; reconnecting does not replace an existing server's configuration.

## First local check after transferring this update

Enter with the new image and launcher, verify the prompt, and edit a project file. On a login host, inspect `ws submit --dry-run` for a small site-approved script, then submit it once and check `ws jobs`. Compare its job ID and output using the native scheduler. Confirm the same workflow on each target locally; the automated fixtures use synthetic clients and cannot validate a site's scheduler configuration or authentication. Keep those local results on the clusters.

For interactive compute work, request the allocation in the host window, then use `ws enter --site SITE --compute --project /path/to/project`. Login-host editor/session state survives the allocation ending. Saving tmux/editor layouts does not migrate live processes or allocations. GPU stacks, software-image payloads, and MPI integration are subsequent phases.
