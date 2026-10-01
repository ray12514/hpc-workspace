# Find a workspace after a round-robin login

A managed tmux workspace stays on the **actual login node** where it started. A name that distributes SSH connections across login nodes can send the next connection somewhere else. Shared home/project files are still visible there, but the running tmux server is on the original node.

## Find the node

**Availability:** `sessions` and the richer location records ship in **0.7.2-preview1**. From the native login shell or an updated workspace:

```bash
ws sessions
ws sessions --json
```

This command needs host Python 3.6+, but does not start Apptainer, load modules, contact other nodes, or require an image selection. It reads the configured site's shared state directory. Use the same `--site` or `--state-dir` override as the original session if you supplied one.

Inside the workspace, the lookup defaults to that shell's current state directory, including a custom location supplied at entry. Explicit `--site` or `--state-dir` options override that default.

Example output, with fictional node and project names:

```text
Current node: login-two
...
login-one  [recorded]
  session: ws-...
  project: /shared/my-project
  release: 0.7.1-preview1
  image: /shared/workspace/image.sif
  recorded_at: ...
```

New sessions started or reattached through the updated launcher record the actual hostname, site, project, image, release, and time of the last record update. Startup displays the hostname and points out records for the same project/release on other nodes. Files are private and remain under the site's workspace state directory; no credentials or environment values are added to these records.

The lookup also reads old session records. It obtains the hostname from the corresponding integration record and the release from the keeper's readiness record when those are available. Older project paths/timestamps may say **not recorded**. It cannot reconstruct missing information or discover plain `tmux` sessions that were never managed by `ws session`.

| Status | Meaning |
| --- | --- |
| `local-ready` | This node's keeper process matches its record and a readiness file exists |
| `local-starting` | This node's keeper matches, but readiness is not recorded yet |
| `local-ended` | This node's recorded keeper is gone or belongs to an earlier boot |
| `recorded` | A location on another node; its current liveness is unverified |
| `unknown-node` | An older record lacks usable hostname information |

The first two are observations of the keeper, not a health check of every program inside tmux. Remote records can be stale. A PID from another node is never checked against the current node's processes. New records include the boot identity to distinguish a restarted node; older records lack that additional check.

## Reconnect

1. Use the site's approved way to reach the **recorded login node with usable credentials**. When supported, open a fresh connection from Windows directly to that node using the same approved kit and authentication settings. A short `hostname` is not necessarily a Windows-resolvable SSH address. If a hop through another login node is required, check the Kerberos considerations below first.
2. Check `hostname` and your ticket status in the new SSH shell before attaching. Successful SSH authentication alone does not prove that the destination has tickets for other services.
3. With the source controls below, run `ws attach --session NAME` to select the recorded project and image. With the published 0.7.2 launcher, run `ws session` with the same project, image/release, and state location. An update selects a different release and therefore a different managed tmux server; use the recorded image with `--image` when returning to an older release.

The lookup does not change SSH routing, renew Kerberos tickets, or move processes. If the session ended, start a new one and recover saved files/editor layouts normally. Keep workspace state on storage shared by the relevant login nodes; a node-local state directory cannot provide discovery from another node.

## Reconnect and stop controls in the source launcher

**Availability:** `attach`, `stop`, and the immediate startup-lock diagnostic are on `codex/session-reconnect`, not in the published 0.7.2-preview1 bundle. These launcher controls work with the existing thin image. The editor-window fix in this branch requires a newly built image. `./setup` still installs the published bundle, not these changes.

From a native Bash shell with the installed `ws` already on PATH, this block downloads a separate checkout and activates its launcher **for this shell only**, preserving the current image selection and custom installation location. It does not edit startup files or merge into an existing checkout. The public HTTPS clone cannot prompt for credentials.

```bash
ws_reconnect_source=$(mktemp -d "$HOME/hpc-workspace-reconnect.XXXXXX") &&
GIT_TERMINAL_PROMPT=0 git clone --depth 1 --single-branch \
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

For offline use, transfer the complete checkout through the site's normal route. Do not copy only `bin/ws` over the installed launcher. On later logins, use the saved checkout's `bin/ws attach` or `stop` directly; these controls obtain the image from the selected record.

| Action, from the native shell on the recorded node | Command |
| --- | --- |
| List managed workspaces | `ws sessions` |
| Reconnect to an existing workspace only | `ws attach --session NAME` |
| Select by project, when exactly one live release matches | `ws attach --project /original/project` |
| Check the server without attaching | `ws attach --session NAME --check` |
| Detach old clients while preserving pane programs | `ws attach --session NAME --detach-others` |
| Close the selected workspace's tmux server and all its panes | `ws stop --session NAME` |

Replace `NAME` with the full recorded `ws-...` name. Repeat the original `--site`/`--state-dir` override if used. Attach uses the recorded project and image even after a release update. Without a selector it works only when exactly one live workspace is recorded on this node. Older records without a project need both `--session NAME` and the original `--project PATH`.

Attach never starts a replacement keeper or tmux server. Missing, ended, starting, ambiguous, and remote workspaces produce diagnostics. The first progress message precedes runtime entry; the second confirms entry reached the helper inside the image. Tmux probes time out after ten seconds. `--check` and `stop` also limit their runtime subprocess to 60 seconds by default (`--timeout SECONDS` adjusts this). Planning and filesystem reads can themselves wait on the filesystem; interactive attachment has no whole-session timeout.

Stop requires explicit selection and validates the local keeper identity. It targets only that managed tmux socket, then waits for its keeper to exit. It closes agents and local builds in those panes; unsaved work is not a checkpoint. It does not cancel scheduler jobs, signal all Apptainer processes, or remove lock files. An ended keeper is reported without sending a stop, but does not prove there are no orphaned processes. A still-starting workspace needs diagnosis from its displayed log; this command does not force-kill an unverified startup. Kernel I/O waits or blocked mounts can prevent shutdown.

## Diagnose a stalled attachment from the host

**Availability:** `scripts/diagnose-session` is standalone source on
`codex/session-reconnect`; it needs native Linux Python 3.6+, but no workspace
installation, image update, or activation. Run it from a second native SSH shell
on the same actual login node and under the same user as the existing session.
It does not start Apptainer, invoke tmux, select a different group, read workspace
configuration, or signal existing processes.

**Use [START-HERE-DIAGNOSTICS.md](../START-HERE-DIAGNOSTICS.md) for the complete
copy/paste procedure**, including selecting the correct branch, running the
diagnostic, saving its summary, and knowing what to send back. It is linked at
the top of the repository README so the whole procedure is available on GitHub
when working from another machine. It downloads a separate diagnostic checkout;
it does not pull/merge into an existing checkout or activate its launcher.
Nothing is pushed from the cluster.
For an offline node, transfer this source checkout through the approved route,
then run `python3 /path/to/checkout/scripts/diagnose-session --output /tmp/ws-report.json`.
The output path must be new. If Git cannot access the public repository, preserve
its error rather than changing credentials or disabling certificate checks.

The command normally takes about six seconds plus metadata collection. It prints
a compact summary and saves a mode-0600 JSON report. The report contains process
names/IDs, paths, namespaces, kernel wait channels/stacks when readable, selected
mount types, visible FUSE queue counters, CPU affinity and cgroup limits/counters.
It samples only the current user's processes and does not collect command arguments,
environment variable values, agent configuration, logs, or open-file contents. Paths
and hostnames still belong to the site: keep the detailed report there and share
only the relevant summary when asking for help. Kernel restrictions can hide wait
channels, stacks or counters; an unavailable value is not evidence of no wait.

The sampler runs as its own diagnostic child with a 30-second deadline. On timeout
only that child is signaled, and the controller reports any complete samples.
An uninterruptible diagnostic read can outlive the deadline; the controller reports
that diagnostic PID and returns rather than waiting indefinitely. Do not repeatedly
launch probes in that case. Interpreter startup and writing the output file are
outside that deadline; use the native interpreter and the `/tmp` location above.

Interpret the observations separately:

- **D** is an uninterruptible kernel wait, often I/O. It does not mean detached or
  establish a tmux application lock. `request_wait_answer`/FUSE stack frames point
  toward a FUSE request; Lustre/`ll_*`/`ptlrpc_*` frames point toward that filesystem
  path. Generic page/lock waits need the stack and mount context.
- A sleeping tmux **server** can be normal while an attaching **client** is in D.
  The table includes parent IDs and executable names to distinguish them.
- A `squashfuse_ll` process falling out of a CPU-sorted `top` view need not have
  exited. The report tracks PID plus process start identity across samples.
- A nonzero FUSE `waiting` counter includes in-flight requests; it alone does not
  prove a deadlock. Repeated waits, blocked-task stacks and daemon activity provide
  context. The helper never writes FUSE controls or unmounts anything.
- `throttled_delta` measures new CPU throttling during the sample window, including
  visible ancestor groups. A quiet node can still enforce a per-user/session CPU
  limit. Missing counters or a short sample without throttling do not rule out
  other limits or intermittent waits.

Sources: [Linux process states](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html),
[FUSE request counters](https://www.kernel.org/doc/html/latest/filesystems/fuse/fuse.html),
[CPU bandwidth control](https://www.kernel.org/doc/html/latest/scheduler/sched-bwc.html).
These are diagnostic distinctions, not a confirmed explanation of the Blueback
attachment/build stall. Preserve the running workspace while collecting evidence.

## Switch between two running workspaces

Start A with `ws session --project /project/A`, then start work inside its tmux shell. Press **Ctrl-B**, then **d** to detach to the native shell. Start B with `ws session --project /project/B`; detach the same way, then use `ws sessions` and `ws attach --session NAME` to return to A. Stop B with its own recorded name while A continues.

Use **detach** to leave work running. `exit` closes the current shell/pane; closing the final pane ends the server. `ws enter` opens a separate foreground container. For managed sessions, use `ws session` directly from the native shell. `attach` and `stop` are native-shell operations: detach before switching workspaces. A keeper plus attach clients can produce several Apptainer processes for one managed workspace, so process counts alone do not count workspaces.

## Bubblewrap errors inside Codex

The thin agent wrapper adds `/workspace-tools/agent-bin` to the end of Codex's PATH; that directory includes `bwrap`. A host `bwrap` earlier on PATH can take precedence. Codex uses Bubblewrap and seccomp for its Linux command sandbox, so a `bwrap` error during an agent tool call can originate in that inner sandbox. Workspace container entry uses Apptainer. [Official OpenAI sandbox documentation](https://learn.chatgpt.com/docs/agent-approvals-security)

The partial report of an “old root” unmount error does not establish its cause. Record the exact error and `codex --version`. A plain workspace imports substantial host userspace and data; it is not a reason to disable Codex's sandbox as a reconnect workaround.

The [local validation](validation.md#separate-codex-sandbox-observation) reproduced a different Bubblewrap bind-mount error inside nested Apptainer, both with and without tmux. Direct toolkit-container sandbox execution passed. That observation has not been confirmed on Blueback.

## Kerberos across an SSH hop

Authenticating **to** a login node and having credentials available **on** that node are separate things. A hop can succeed while the destination has no usable ticket-granting ticket (TGT). Missing delegation, a non-forwardable or expired ticket, or selection of an old credential cache are possible causes; none has been established for these sites from public information.

Kerberos supports forwarding when the ticket and site policy permit it. Use the approved kit's ticket acquisition/renewal procedure. On Linux with MIT Kerberos, `klist -f` shows the cache, expiry, and flags: uppercase `F` means forwardable. Run it locally before and after the hop; its output stays on the cluster. Do not replace the site's PKINIT procedure with a generic password-based `kinit` command. [MIT Kerberos ticket management](https://web.mit.edu/kerberos/krb5-latest/doc/user/tkt_mgmt.html)

Where supported and permitted, the relevant client settings are:

- PuTTY/Plink: the saved session's **Allow GSSAPI credential delegation** option, with the correct approved GSSAPI library. SSH-key/Pageant agent forwarding is a different mechanism. [PuTTY GSSAPI settings](https://the.earth.li/~sgtatham/putty/0.85/htmldoc/Chapter4.html#gssapi-delegation)
- Linux OpenSSH with GSSAPI support: `GSSAPIAuthentication yes` and `GSSAPIDelegateCredentials yes`, scoped to the approved destination. They can be tested for one connection as shown below. These options cannot grant delegation that the ticket or server policy disallows. [OpenSSH configuration](https://man.openbsd.org/ssh_config#GSSAPIDelegateCredentials)

```bash
# Use only the site's approved destination and delegation policy.
ssh -o GSSAPIAuthentication=yes -o GSSAPIDelegateCredentials=yes APPROVED_LOGIN_NODE
```

A second hop needs usable credentials on the first node and delegation on the onward connection. A fresh Windows-to-original-node connection avoids that extra hop, but still needs the site's correct incoming authentication/delegation setup. If the site supplies a sticky-login route, reconnect helper, or credential refresh command, use that supported mechanism. The workspace does not enable global delegation or copy ticket caches between nodes.

## Fresh login works, but an old tmux pane does not

An existing shell can retain an old `KRB5CCNAME` even after a new login obtained a valid cache. Tmux's `update-environment` setting can import selected variables when attaching and use them for **new** windows; it does not rewrite the environment of processes already running in old panes. [tmux session environments](https://man.openbsd.org/tmux.1#GLOBAL_AND_SESSION_ENVIRONMENT)

Check the ticket in the fresh native SSH shell, then in a new tmux window (**Ctrl-B c**) and the affected old pane. Inside the managed session, press **Ctrl-B :** and enter `show-options -v update-environment` to see whether `KRB5CCNAME` is included. If only old panes fail, use a new window for new work while keeping the active job pane intact. Use the site's credential-refresh procedure when needed; updating a cache name does not renew a ticket. FILE, KEYRING, and KCM caches can have different lifetime/access rules, so do not guess a cache path or copy a cache file into shared storage.

Tmux keeps processes alive; it does not extend ticket lifetime or guarantee that a login-created cache survives logout. Credential refresh must therefore be considered separately from session persistence.

## Starting on another node instead

Starting a fresh `ws session` on the node where you have working authentication is reasonable for ordinary editing. Leave the old session intact until you know it holds no work you need. **Do not kill an old tmux server as an automatic reconnect fallback.** Detaching the client with Ctrl-B d preserves its server; killing the server ends its panes and can interrupt the scheduler client inside one. [tmux session persistence](https://man.openbsd.org/tmux.1#DESCRIPTION)

| Work | What can return on another login node? |
| --- | --- |
| Files saved on shared storage | Open the same files from the new workspace |
| Saved Neovim layout and undo | Reuse the persistent workspace state for the same project; unsaved text is not a layout backup |
| Tmux windows, splits, directories | A saved layout can recreate shells, but current snapshots are stored under the originating node; cross-node selection/import is not automated |
| A running shell, editor, or agent | Its live process remains on the original node; layout restore does not migrate it |
| An interactive allocation held by a pane | Keep the original server/client alive; a new tmux server cannot inherit that terminal connection |
| An ordinary submitted batch job | Managed by the scheduler independently of its submission terminal; inspect it from the new node using normal site commands |

Our tmux defaults restore arrangement/directories and shells, with process replay and automatic restore disabled. Saving a layout does not save running job state. Before intentionally replacing an editing session, write files with Neovim's `:wall`, save its editor layout, and save the tmux layout with Ctrl-B Ctrl-S. The workspace does not yet provide a cross-node layout import command; Ctrl-B Ctrl-R on a different node does not automatically select the old node's snapshot.

For interactive work, loss of the submitting terminal/client can end the allocation. For example, Slurm documents that `salloc` releases its allocation on SIGHUP. A still-running job may have a site-supported attach procedure, but a new tmux server does not supply one. Slurm's `sattach` targets an existing job step and has PTY restrictions; it is not a general migration or allocation-recovery command. PBS behavior likewise depends on the site's interactive procedure. [Slurm salloc signals](https://slurm.schedmd.com/salloc.html#SECTION_SIGNALS), [Slurm sattach](https://slurm.schedmd.com/sattach.html)

`hostname` inside the workspace and the node in tmux's status bar provide an immediate reminder. If still using 0.7.1, you can run `./bin/ws sessions` from an updated checkout to inspect its existing records without rebuilding that SIF. To record full metadata with an older image, use the repository's `bin/ws session` with your existing `--image` and `--project` paths. The normal update command, `git pull --ff-only && ./setup`, installs the recommended matching image and runtime together.

See [Windows connections](windows-vscode-hpc.md), [tmux and interactive jobs](editor-and-agents.md#interactive-jobs-and-tmux), and [persistent state](dotfiles.md#persistent-state).
