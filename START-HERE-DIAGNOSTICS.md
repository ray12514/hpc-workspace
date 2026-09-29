# Blueback workspace diagnostics: start here

This page contains the complete procedure for collecting diagnostics when the
existing workspace will not reattach, including intermittent tmux `D`/`R` states.
The diagnostic is already on GitHub in **ray12514/hpc-workspace**, branch
**codex/session-reconnect**. You do not need to push anything from Blueback.

## 1. Open the right terminal

Open a second PuTTY connection to the **same actual login node where your build
and tmux processes are running**. Use your normal native Bash shell, outside the
workspace/container. You can start in any directory. Leave the existing build
and workspace running; no workspace activation, update, or restart is required.

## 2. Copy and run this entire block

This downloads a separate copy of the correct GitHub branch under `/tmp` and
runs its diagnostic. It supplies every required file, selects the branch for
you, and saves both the printed summary and the detailed report. It does not
change an existing checkout or install a new workspace release.

Native Git, Python 3.6+, Bash, and access to the public GitHub repository are
required. No GitHub sign-in or agent API key is needed for this procedure.

```bash
ws_diag_source=$(mktemp -d /tmp/ws-diagnostics.XXXXXX) &&
GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false \
git -c credential.helper= clone --depth 1 --single-branch \
  --branch codex/session-reconnect \
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
Blueback's underlying attachment/build problem remains under investigation.
