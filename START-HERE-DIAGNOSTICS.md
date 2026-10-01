# Blueback workspace diagnostics: start here

This page contains the complete procedure for collecting diagnostics when the
existing workspace will not reattach, including intermittent tmux `D`/`R` states.
The diagnostic is in **ray12514/hpc-workspace** on the main branch. You do not
need to push anything from Blueback.

**Already collected the report?** Start with [CPU limits and filesystem
waits](#cpu-limits-and-filesystem-waits). To test Codex controlling an allocation
or running inside one, use [the complete compute-agent test](docs/blueback-compute-agent-test.md).
**The compute test passed?** Use [the complete stop-and-resume handoff](docs/blueback-compute-handoff.md)
to move the existing CCE build and resume the original Codex conversation.

## 1. Open the right terminal

Open a second PuTTY connection to the **same actual login node where your build
and tmux processes are running**. Use your normal native Bash shell, outside the
workspace/container. You can start in any directory. Leave the existing build
and workspace running; no workspace activation, update, or restart is required.

## 2. Copy and run this entire block

This downloads a separate copy of the GitHub repository under `/tmp` and
runs its diagnostic. It supplies every required file, selects the branch for
you, and saves both the printed summary and the detailed report. It does not
change an existing checkout or install a new workspace release.

Native Git, Python 3.6+, Bash, and access to the public GitHub repository are
required. No GitHub sign-in or agent API key is needed for this procedure.

```bash
ws_diag_source=$(mktemp -d /tmp/ws-diagnostics.XXXXXX) &&
GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false \
git -c credential.helper= clone --depth 1 --single-branch \
  --branch main \
  https://github.com/ray12514/hpc-workspace.git "$ws_diag_source" &&
(
  umask 077
  set -o pipefail
  if python3 "$ws_diag_source/scripts/diagnose-session" \
    --output "$ws_diag_source/report.json" 2>&1 |
    tee "$ws_diag_source/summary.txt"; then
    ws_diag_status=0
  else
    ws_diag_status=$?
  fi
  printf '\nSaved summary: %s/summary.txt\n' "$ws_diag_source"
  printf 'Detailed report: %s/report.json\n' "$ws_diag_source"
  printf 'Diagnostic exit code: %s\n' "$ws_diag_status"
  exit "$ws_diag_status"
)
```

After the download, the diagnostic normally takes about six seconds plus
metadata collection. Its sampler has a 30-second deadline. It does not enter
Apptainer, attach to tmux, stop existing processes, or restart your build.

## 3. Save the result for the next conversation

Send the printed text beginning with **Workspace host diagnostic**. Both output
paths are printed at the end. Keep the detailed `report.json` on Blueback; it
contains additional process and filesystem metadata if needed later.

To display the saved summary again in the **same PuTTY shell**, run:

```bash
cat "$ws_diag_source/summary.txt"
```

Record the full saved-summary path before closing that PuTTY window. The
`ws_diag_source` variable belongs to that shell, and `/tmp` is temporary storage
on that node. Preserve the printed summary through your usual working notes if
you need it after logging out.

If the Git download fails, save that error. If the diagnostic says **INCOMPLETE**,
save its summary, including the last-probe line. If it reports a diagnostic
worker still blocked after timeout, do not repeatedly launch more probes. Keep
the existing workspace running while the result is investigated.

## What this check establishes

It records process identities across samples, kernel wait channels/stacks when
readable, FUSE activity, and CPU limits/throttling. A tmux `D` state is a kernel
wait, not detachment; `R` means running or runnable. A busy `squashfuse_ll` process
or a nonzero queue alone does not establish the cause of the slowdown.

The diagnostic and its local Linux checks are documented in the
[validation record](docs/validation.md#host-diagnostics-for-a-blocked-attachment).
For the report fields and interpretation, see
[the detailed guide](docs/session-locations.md#diagnose-a-stalled-attachment-from-the-host).

## CPU limits and filesystem waits

Interpret the CPU limit at **every ancestor** listed for the affected processes.
For example, `quota=200000 100000` means 200,000 microseconds of aggregate CPU
time per 100,000-microsecond period: **two logical CPUs' worth of time shared
by that group and its descendants**. It does not reserve two particular cores.
An idle machine can still throttle that group. A positive `throttled_delta`
confirms throttling during the capture; it counts events, not seconds lost.
`quota=?/?` on a child does not cancel a parent's limit. See the Linux kernel's
[CPU controller documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html#cpu).

| Report field | What it establishes |
| --- | --- |
| `tmux` in `D`, with `fuse_get_req` | The sampled thread is waiting in the FUSE request path. `D` does not mean detached. |
| Compiler threads in `squashfs_decompress` | They were sampled in the kernel's compressed-filesystem decompression path. The function name alone does not identify which image or filesystem backs the access. |
| `stack: Permission denied` | The diagnostic could not read the kernel stack. This is not evidence that a package recipe or build directory has bad ACLs. |
| Nonzero FUSE `waiting` | Requests are pending or being processed. During active work this alone does not prove deadlock. |
| Visible filesystem types | These filesystems appear in the process's mount namespace; the list does not identify the blocked file. |

Stack access is restricted by the kernel's process-inspection rules; FUSE
documents its waiting counter separately. See
[`/proc/PID/stack`](https://man7.org/linux/man-pages/man5/proc_pid_stack.5.html)
and [FUSE control counters](https://www.kernel.org/doc/html/latest/filesystems/fuse/fuse.html).

When throttling and filesystem waits occur together, the CPU budget is a
confirmed constraint. Whether it fully explains the attachment stall still
needs a comparison under an approved allocation; there may also be a filesystem
or decompression bottleneck. More PuTTY windows or compiler workers in the same
limited group do not provide more CPU time.

### Next action

Keep the current build running while preparing the
[compute-agent test](docs/blueback-compute-agent-test.md). It starts only a small
separate test allocation, checks placement, and tests command/agent access.
It does not resume or reconcretize the current build. If login-node builds are
intended for this project, give site support the saved summary and ask them to
confirm the user-slice CPU policy and inspect the FUSE/SquashFS waits.

A new terminal cannot migrate existing build processes. A build handoff requires
the current writer to finish or be deliberately stopped before one selected
`cse-build compute resume` is started. More resources do not require changing
the install tree, padding, or package overlays. Changing a jobs setting also
does not retune an already-running `make`.
