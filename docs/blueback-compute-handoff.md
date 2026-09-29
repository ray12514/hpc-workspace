# Blueback: move the existing CCE build to compute

Use **option B: Codex and the build inside the compute allocation**. The
operator reported successful workspace entry and Codex API access there.
The normal login-node workspace can hold the allocation's terminal connection.
This keeps the build and agent tools on compute while preserving a detachable
terminal on login.

This procedure deliberately stops the old build session. Packages already
installed and saved files remain; an interrupted package may repeat work.
Codex conversation recovery is separate from resuming a Spack build. The old
conversation must have no active writer before the compute client resumes it.

## 1. Stop the old workspace on its original login node

Open a native PuTTY/Bash connection to the recorded login node. This block gets
the source controls from GitHub without updating the installed image or merging
an existing checkout. It lists sessions; it does not stop anything yet.

```bash
ws_reconnect_source=$(mktemp -d "$HOME/hpc-workspace-reconnect.XXXXXX") &&
GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false \
git -c credential.helper= clone --depth 1 --single-branch \
  --branch codex/session-reconnect \
  https://github.com/ray12514/hpc-workspace.git "$ws_reconnect_source" &&
ws_reconnect_prefix=$(python3 - "$ws_reconnect_source/lib" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from bootstrap import install_prefix
print(install_prefix())
PY
) &&
export WS_INSTALL_ROOT="$ws_reconnect_prefix" &&
export PATH="$ws_reconnect_source/bin:$PATH" &&
hash -r &&
ws sessions
```

Select the exact old CSE workspace name and original project path from that
output. Use the same `--site` or `--state-dir` override if the original session
used one. Inspect your process IDs before stopping, so leftovers are identifiable:

```bash
ps -u "$(id -u)" -o pid,ppid,stat,comm
```

Fill in both values, then run:

```bash
CSE_OLD_WS_SESSION='EDIT_FULL_ws_SESSION_NAME'
CSE_OLD_WORKSPACE='/EDIT/original/CSE/workspace/path'
(
  case "$CSE_OLD_WS_SESSION:$CSE_OLD_WORKSPACE" in
    *EDIT*) printf 'Fill in the old session name and workspace path first.\n' >&2; exit 2 ;;
  esac
  ws stop --session "$CSE_OLD_WS_SESSION" --project "$CSE_OLD_WORKSPACE" --timeout 30 &&
  ws sessions &&
  ps -u "$(id -u)" -o pid,ppid,stat,comm
)
```

This closes only that managed tmux server and its panes, including its Codex
and local build commands. It also interrupts any interactive allocation client
held in those panes, so do this **before** starting the replacement allocation.

Continue when the selected workspace has stopped and its old Codex/build
processes have exited. A stopped keeper alone is not proof that every child
exited. If the command times out, or old build/Codex PIDs remain (particularly
in `D`), retain that output and stop the handoff here. A kernel-blocked process
may require site support; repeatedly entering containers or deleting lock files
does not release it. Do not replace this selection with a user-wide kill.

## 2. Open a fresh login workspace to hold the allocation

After step 1 succeeds, from that native login shell:

```bash
cd "$CSE_OLD_WORKSPACE" && ./cse-agent-workspace
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
