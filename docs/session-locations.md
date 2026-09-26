# Find a workspace after a round-robin login

A managed tmux workspace stays on the **actual login node** where it started. A name that distributes SSH connections across login nodes can send the next connection somewhere else. Shared home/project files are still visible there, but the running tmux server is on the original node.

## Find the node

**Availability:** `sessions` and the richer location records ship in **0.7.2-preview1**. From the native login shell after updating:

```bash
ws sessions
ws sessions --json
```

This command needs host Python 3.6+, but does not start Apptainer, load modules, contact other nodes, or require an image selection. It reads the configured site's shared state directory. Use the same `--site` or `--state-dir` override as the original session if you supplied one.

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
3. Change to the original project and run `ws session` with the same image/release and state location. An update selects a different release and therefore a different managed tmux server. Use the recorded image with `--image` if returning to an older release.

The lookup does not change SSH routing, renew Kerberos tickets, or move processes. If the session ended, start a new one and recover saved files/editor layouts normally. Keep workspace state on storage shared by the relevant login nodes; a node-local state directory cannot provide discovery from another node.

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
