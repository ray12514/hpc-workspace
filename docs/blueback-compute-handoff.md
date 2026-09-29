# Blueback: move the existing CCE build to compute

Use **option B: Codex and the build inside the compute allocation**. The
operator reported successful workspace entry and Codex API access there.
The normal login-node workspace can hold the allocation's terminal connection.
This keeps the build and agent tools on compute while preserving a detachable
terminal on login.

This procedure deliberately stops your old processes on the login node.
Packages already installed and saved files remain; an interrupted package may
repeat work. Codex can resume the conversation history that was saved, but
that is not a running-process snapshot or a guarantee of package checkpoints.
The old conversation must have no active writer before the compute client
resumes it.

## 1. Stop your old processes from a fresh native SSH connection

**No reattachment, container entry or working tmux server is required.** Open a
fresh native PuTTY/Bash connection to the **old login node**. Run this outside
any workspace, tmux session or compute allocation, as your ordinary account.
Check `hostname` first so the cleanup runs on the intended node.

This is the broad cleanup requested by the operator: it stops processes owned
by your UID on that node, including old shells, agents, builds, containers and
other sessions. It preserves this command and the ancestors of this fresh SSH
connection. Other PuTTY windows may close. Stopping an interactive scheduler
client can also end its allocation; perform this before starting the replacement
build allocation. Other users' processes are outside its scope. Never use sudo.

Copy this whole block into that fresh native shell:

```bash
ws_stop_source=$(mktemp -d /tmp/cse-native-stop.XXXXXX) &&
GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false \
git -c credential.helper= clone --depth 1 --single-branch \
  --branch codex/session-reconnect \
  https://github.com/ray12514/hpc-workspace.git "$ws_stop_source" &&
python3 "$ws_stop_source/scripts/stop-own-node-processes" --stop
```

The standalone helper uses native Python 3.6+ and `/proc`. It sends TERM, allows
ten seconds for exit, then sends KILL to remaining matching processes and checks
again. It rechecks process ownership/start time before signalling and does not
read credentials, enter Apptainer, contact tmux or remove any lock files.
It refuses root, an active workspace/tmux environment or a scheduler allocation.
If inspection is incomplete before the first signal, it stops without signalling.
To preview only, omit `--stop`.

Continue after **`CLEANUP_OK`**. You can then log out and make a fresh login, or
continue from the preserved native shell. A `Z` process has already exited;
its parent still needs to reap it.

**`CLEANUP INCOMPLETE`** lists remaining PIDs/states. A task in `D` can remain
until its kernel wait clears even after KILL was sent; new PIDs can also be
restarted user services. Keep that output for site support and verify the old
writers are gone before resuming. Successful signal delivery alone is not proof
of process exit. See Linux's [signal semantics](https://man7.org/linux/man-pages/man2/kill.2.html)
and [process states](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html).

## 2. Open a fresh login workspace to hold the allocation

After step 1 succeeds, set the original workspace path in the native login
shell you are using now. This also works after logging out and back in:

```bash
CSE_OLD_WORKSPACE='/EDIT/original/CSE/workspace/path'
(
  case "$CSE_OLD_WORKSPACE" in
    ''|*EDIT*) printf 'Fill in the original workspace path first.\n' >&2; exit 2 ;;
  esac
  cd "$CSE_OLD_WORKSPACE" && ./cse-agent-workspace
)
```

This starts a new managed login tmux session. Its shell will hold the Slurm
client; run the agent itself on compute in step 4. Detach later with **Ctrl-B d**
and return to this same login node/session. Closing the pane containing the
Slurm client can end the allocation.

In that new workspace shell, complete
[step 1 of the compute guide](blueback-compute-agent-test.md#1-fill-in-these-values-on-the-login-node):
export the tested account, **constraint**, QOS and original workspace path,
then supply the working API-key variable and CA bundle using its hidden-input
block. Keep the same native Codex configuration and any existing `CODEX_HOME`.
The exports must happen in this shell before the following allocation command.

## 3. Request the full build allocation

For the operator's selected 192-core node, request one task with 192 CPUs and
exclusive node access. Set a walltime allowed by your tested QOS; the ten-minute
smoke-test walltime is not suitable for the remaining build. This does not force
the build to use 192 workers; keep the current build parallelism for the first
compute continuation so the placement change can be evaluated separately.

```bash
CSE_BUILD_WALLTIME='EDIT_HH:MM:SS'
(
  set -eu
  for cse_build_name in CSE_PROBE_ACCOUNT CSE_PROBE_CONSTRAINT CSE_PROBE_QOS CSE_PROBE_WORKSPACE CSE_BUILD_WALLTIME; do
    cse_build_value=${!cse_build_name:-}
    case "$cse_build_value" in
      ''|*EDIT*) printf 'Fill in %s first.\n' "$cse_build_name" >&2; exit 2 ;;
    esac
  done
  test -z "${SLURM_JOB_ID:-}${PBS_JOBID:-}" || {
    printf 'Start this request from the login workspace.\n' >&2; exit 2;
  }
  cd "$CSE_PROBE_WORKSPACE"
  ws job-env -- salloc \
    --account="$CSE_PROBE_ACCOUNT" \
    --constraint="$CSE_PROBE_CONSTRAINT" --qos="$CSE_PROBE_QOS" \
    --nodes=1 --ntasks=1 --cpus-per-task=192 --exclusive \
    --time="$CSE_BUILD_WALLTIME" --job-name=cse-cce-build \
    srun --nodes=1 --ntasks=1 --cpus-per-task=192 --pty /bin/bash -l
)
```

Wait for this allocation's shell, then run the
[placement check](blueback-compute-agent-test.md#3-verify-placement-in-the-new-compute-shell).
The Slurm request and resulting affinity must cover the intended CPUs; merely
seeing 192 cores in a hardware listing is not an allocation check. The command
uses the same tested constraint/default-partition approach. Slurm's resource
and step options are documented in [salloc](https://slurm.schedmd.com/salloc.html)
and [srun](https://slurm.schedmd.com/srun.html).

## 4. Enter with the normal prompt and resume the original Codex conversation

From the allocated native compute shell:

```bash
cd "$CSE_PROBE_WORKSPACE" &&
./cse-agent-workspace -- /workspace-tools/thin-shell
```

The prompt includes `compute@HOST job:ID`. Run the compute-workspace check in
[step 4](blueback-compute-agent-test.md#4-enter-the-compute-workspace-with-the-cse-group)
to confirm the group and entry. The exported key and CA settings are inherited.
`--noprofile --norc` was responsible for the plain test prompt; it did not mean
that the earlier successful test was outside the workspace.

From this compute workspace, open the conversation picker:

```bash
ws agent codex --native -- resume
```

Choose the **original CCE build conversation**, not the short API-test chat.
Alternatively, with its exact ID:

```bash
ws agent codex --native -- resume 'ORIGINAL_BUILD_CONVERSATION_ID'
```

Use your existing named gateway instead of `--native` if that is how the
original agent was configured. The picker/ID preserves the selected history;
`--last` can now select the newer smoke-test chat. See
[Codex resume](https://learn.chatgpt.com/docs/developer-commands).

If Codex still reports an active writer after the old process has exited, keep
the error and investigate its session ownership. Do not erase its history,
database, or lock files to bypass the error.

Give the resumed agent this instruction:

> Continue the existing platform/CCE build in this allocated compute workspace.
> Read BUILD-CONTEXT.yaml, BUILD-PROGRESS.md and BUILD-AGENT.md. This run uses
> the compute context in place of the handoff's login context. First inspect
> the current recovery records and selected environment; then use cse-build
> compute resume with its existing lock. Preserve the package-overlay impact
> workflow and completed shared/GCC locks. Keep one finite workspace operation
> active at a time. Record the allocation and next recovery action in the
> progress notes. Do not automatically reconcretize just because the build was
> interrupted.

The manual continuation, after selecting the exact environment from the
workspace's `BUILD-CONTEXT.yaml`, is:

```bash
./cse-build compute resume --environment 'COMPILER/LANE'
```

Current `resume` uses the generated Spack `build_jobs` setting and has no jobs
flag. A changed `BUILD_JOBS` export is not a reliable override. The existing
installed hashes are reused; unfinished package work can restart. CSE's
maintenance lock must be free before a new finite operation proceeds.

## If using a login agent later

Route A remains an alternative to test using the guide's persistent PTY and
`ws job-env`. API access from both node types does not itself test remote shell
control. Prefer a Slurm step in the selected allocation for that route. Direct
SSH does not automatically export the key/CA/module environment or prove the
new process belongs to the allocated job; the site's SSH adoption policy
determines that placement. See [Slurm SSH job adoption](https://slurm.schedmd.com/pam_slurm_adopt.html).
