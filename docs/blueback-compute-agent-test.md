# Blueback: test Codex with a compute allocation

This is a small connectivity and workspace test. Keep the existing CCE build
running. The commands below leave its locks, overlays and packages alone.
Use branch **`codex/session-reconnect`** of **ray12514/hpc-workspace** for this
guide; no workspace/image update is required for `ws job-env` or direct entry.

Blueback's public documentation identifies **Slurm**, with account, partition,
QOS and time/resource options. It recommends allocated compute resources for
heavy interactive work. Project access determines the values you can use; fill
in the three scheduler placeholders below from your approved settings. Public
queue examples are not proof of your project's access. Sources checked
2026-09-29: [Blueback Slurm guide](https://centers.hpc.mil/users/docs/navy/bluebackSlurmGuide.html)
and [Blueback user guide](https://centers.hpc.mil/users/docs/navy/bluebackUserGuide.html).

| Arrangement | Where Codex runs | Where build commands run | What to test |
| --- | --- | --- | --- |
| A: login agent controls a shell | Login workspace | A shell launched by Slurm on a compute node | Keep one terminal handle and send subsequent commands to it. |
| B: agent inside the allocation | Compute workspace | Same compute workspace | Verify its certificate/key setup and an actual gateway response. |

Start with A if the gateway is reachable only from login nodes. B places the
agent's local tools in the compute allocation too. Both still need working
shared storage and container entry. A remains subject to login-node limits for
its own local work; neither route repairs an unrelated filesystem problem.

## 1. Fill in these values on the login node

Use Bash. Start in a native login shell for a manual test, or use a working
login-workspace shell for route A. `ws`, `salloc` and `srun` must already be on
PATH, and the site's absolute writable `WORKDIR` must be set. Use the original
existing CSE workspace path, on storage accessible from compute nodes.

```bash
export CSE_PROBE_ACCOUNT='EDIT_ACCOUNT'
export CSE_PROBE_PARTITION='EDIT_PARTITION'
export CSE_PROBE_QOS='EDIT_QOS'
export CSE_PROBE_WORKSPACE='/EDIT/absolute/path/to/existing/CSE/workspace'
export CSE_PROBE_LOGIN_HOST="$(hostname)"
```

For route B, supply the **same working credential variable and CA path** as your
current Codex setup before allocation/entry, through your existing private
mechanism. Keep secrets out of this block and the repository. If you currently
export them only inside the login workspace, start the allocation from that
shell. `ws job-env` retains those exports; it is not a credential scrubber.
The certificate and saved configuration must be readable on the compute node.

Exports made in another PuTTY window do not update a running agent. For route A,
include the completed exports in the same shell-tool invocation as step 2.

## 2. Request one short test allocation

This example requests one task, two CPUs and ten minutes. Adapt those resources
if your site's selected partition requires a different minimum. It is a smoke
test allocation, not a resource recommendation for Dakota.

```bash
(
  set -eu
  for cse_probe_name in CSE_PROBE_ACCOUNT CSE_PROBE_PARTITION CSE_PROBE_QOS CSE_PROBE_WORKSPACE; do
    cse_probe_value=${!cse_probe_name:-}
    case "$cse_probe_value" in
      ''|*EDIT*) printf 'Fill in %s first.\n' "$cse_probe_name" >&2; exit 2 ;;
    esac
  done
  test -n "${CSE_PROBE_LOGIN_HOST:-}" || {
    printf 'Run the exports in step 1 first.\n' >&2; exit 2;
  }
  test -z "${SLURM_JOB_ID:-}${PBS_JOBID:-}" || {
    printf 'Run this allocation request from the login node.\n' >&2; exit 2;
  }
  case "${WORKDIR:-}" in
    /*) test -d "$WORKDIR" && test -w "$WORKDIR" && test -x "$WORKDIR" || {
          printf 'WORKDIR is missing or not writable/searchable.\n' >&2; exit 2;
        } ;;
    *) printf 'The site WORKDIR must be an absolute writable directory.\n' >&2; exit 2 ;;
  esac
  cd "$CSE_PROBE_WORKSPACE"
  test -x ./cse-agent-workspace || {
    printf 'No executable cse-agent-workspace at that workspace path.\n' >&2; exit 2;
  }
  for cse_probe_command in ws salloc srun; do command -v "$cse_probe_command"; done
  ws job-env -- salloc \
    --account="$CSE_PROBE_ACCOUNT" \
    --partition="$CSE_PROBE_PARTITION" --qos="$CSE_PROBE_QOS" \
    --nodes=1 --ntasks=1 --cpus-per-task=2 --time=00:10:00 \
    --job-name=ws-agent-probe \
    srun --nodes=1 --ntasks=1 --cpus-per-task=2 --pty /bin/bash -l
)
```

Wait for **this request** to reach a compute shell. A queued job is not an entry
failure; do not submit another request just because it waits. The explicit
`srun` starts the compute step rather than assuming an allocation variable
places the current shell there. `ws job-env` restores workspace-modified
environment settings and removes the login tmux socket before export. See
[Slurm salloc](https://slurm.schedmd.com/salloc.html),
[Slurm srun](https://slurm.schedmd.com/srun.html), and
[the workspace environment boundary](editor-and-agents.md#interactive-jobs-and-tmux).

**For a Codex-controlled test (A):** launch that block with a persistent PTY
(`exec_command` with `tty: true`, when available). Retain the returned terminal
session ID. Send steps 3 and 4 through `write_stdin` on that same session. A new
shell-tool call is still on the login node. If the agent's shell tool cannot
retain a PTY, use the manual route B; do not claim A passed from a queued job.

## 3. Verify placement in the new compute shell

```bash
(
  set -eu
  cse_probe_require() {
    cse_probe_label=$1
    shift
    "$@" || { printf 'STOP: %s\n' "$cse_probe_label" >&2; exit 2; }
  }
  printf 'Current host=%s job=%s\n' "$(hostname)" "${SLURM_JOB_ID:-unset}"
  cse_probe_require 'Slurm job ID is absent.' test -n "${SLURM_JOB_ID:-}"
  cse_probe_require 'Login hostname was not exported.' test -n "${CSE_PROBE_LOGIN_HOST:-}"
  cse_probe_require 'This is still the submitting login node.' test "$(hostname)" != "$CSE_PROBE_LOGIN_HOST"
  cse_probe_require 'A login container marker leaked through.' test -z "${WS_CONTAINER:-}"
  cd "$CSE_PROBE_WORKSPACE"
  cse_probe_require 'CSE context is not readable here.' test -r BUILD-CONTEXT.yaml
  cse_probe_require 'CSE entry is not executable here.' test -x ./cse-agent-workspace
  cse_probe_require 'WORKDIR is missing here.' test -d "${WORKDIR:-}"
  cse_probe_require 'WORKDIR is not writable here.' test -w "$WORKDIR"
  cse_probe_require 'WORKDIR is not searchable here.' test -x "$WORKDIR"
  cse_probe_require 'Native ws is missing on compute PATH.' command -v ws
  printf 'Compute host=%s job=%s requested CPUs/task=%s\n' \
    "$(hostname)" "$SLURM_JOB_ID" "${SLURM_CPUS_PER_TASK:-unknown}"
  id
  awk '/^Cpus_allowed_list:/' /proc/self/status
  printf 'COMPUTE_PLACEMENT_OK\n'
)
```

Continue only after `COMPUTE_PLACEMENT_OK`. If it is absent, retain the failed
command/output and stop this test. A job ID alone is not the placement check.
The allowed CPU list shows affinity, not a CPU-time quota; the
[host diagnostic](../START-HERE-DIAGNOSTICS.md) can inspect ancestor limits when
needed. Keep any detailed report site-local.

## 4. Enter the compute workspace with the CSE group

In that same compute shell:

```bash
cd "$CSE_PROBE_WORKSPACE" &&
./cse-agent-workspace -- /bin/bash --noprofile --norc -i
```

The wrapper's **`-- COMMAND`** form calls `ws enter` and selects the recorded
CSE primary group. No-argument `cse-agent-workspace` calls `ws session`, whose
persistent server is deliberately restricted to login nodes. Use direct entry
here. The launcher, SIF, project, home and Apptainer runtime must be available
on this compute node; a login-only `/tmp` installation is insufficient.

Inside the resulting compute workspace:

```bash
(
  set -eu
  test "${WS_CONTEXT:-}" = compute && test "${WS_CONTAINER:-}" = 1 && test -n "${SLURM_JOB_ID:-}" || {
    printf 'STOP: expected a workspace inside a Slurm compute allocation.\n' >&2; exit 2;
  }
  printf 'Workspace host=%s job=%s context=%s\n' \
    "$(hostname)" "$SLURM_JOB_ID" "$WS_CONTEXT"
  id
  ws agent codex --native -- --version
  printf 'COMPUTE_WORKSPACE_OK\n'
)
```

For A, send a second command through the **same PTY**:

```bash
printf 'SECOND_COMMAND_OK host=%s job=%s context=%s\n' \
  "$(hostname)" "$SLURM_JOB_ID" "$WS_CONTEXT"
```

A passes when both commands return on the same compute host/job, the recorded
CSE group is present, and workspace context remains `compute`. Codex's file
tools still run on login, so they must use the same shared workspace path.
This test does not start another agent or build on compute.

## 5. Optional route B: test Codex itself on compute

After step 4, use your existing Codex connection selection. For the ordinary
native TOML setup:

```bash
ws agent codex --native -- 'Reply with exactly COMPUTE_API_OK. Do not run commands, read files, or change anything.'
```

If you normally use a named gateway, use that same name in place of `--native`.
A returned model response tests gateway access; `--version` alone does not.
If authentication or streaming fails here, preserve the error locally and
compare the existing credential, readable CA path and site network policy.
Current Codex supports `CODEX_CA_CERTIFICATE`, falling back to `SSL_CERT_FILE`;
retain the setup already working with your installed version. See
[Codex authentication](https://learn.chatgpt.com/docs/auth#custom-ca-bundles)
and [the workspace's native configuration guide](restricted-codex.md).

Close this **test** Codex with `/quit`, exit the compute workspace shell, then
exit the native compute shell. The foreground allocation command returns and
releases this test allocation. Record its job ID so it is distinguishable from
other jobs. From login, `squeue --me` shows your remaining jobs.

For this first test, keep the submitting terminal/agent alive. For ongoing
interactive work, keep its client in a working login-node tmux session according
to the site's procedure. Ending an allocation ends its compute processes;
moving the terminal UI does not preserve an expired job. See
[session lifetime](session-locations.md#starting-on-another-node-instead).

## Before continuing the real CCE build

Record the test's host, job ID, resource request, CSE group, entry result and
whether A/B passed. Keep errors and paths in the existing site-local build
notes. A successful smoke test qualifies the route, not Dakota performance.

After the existing writer finishes or a deliberate stop is complete, use one
appropriately sized allocation and the original workspace. Read its
`BUILD-CONTEXT.yaml` for the exact platform environment and its `BUILD-AGENT.md`
for overlay/recovery policy. That handoff currently says `login`; when the
operator selects this compute route, use the `compute` context consistently:

```bash
./cse-build compute resume --environment 'COMPILER/LANE'
```

Replace `COMPILER/LANE` with the selected existing environment. This reuses its
current lock and matching installed hashes. Current `resume` has no jobs flag;
the generated Spack configuration supplies parallelism. Verify that setting
fits the allocation before a real resume. Exporting a different `BUILD_JOBS`
is not a reliable override and does not change a running build. Preserve the
existing overlay impact checks and completed shared/GCC locks.

## Validation boundary

The local offline fixture exercises a persistent PTY through the actual
`ws job-env` launcher, a simulated scheduler boundary, compute-context entry and
packaged Codex startup. It uses no cluster credentials or API calls. Blueback
allocation admission, node placement, group/mount access and API connectivity
remain the acceptance checks above. See [the validation record](validation.md#compute-agent-shell-test).
