# Find a workspace after a round-robin login

A managed tmux workspace stays on the **actual login node** where it started. A name that distributes SSH connections across login nodes can send the next connection somewhere else. Shared home/project files are still visible there, but the running tmux server is on the original node.

## Find the node

**Availability:** `sessions` and the richer location records are in the repository launcher, after 0.7.1-preview1. They are not in the published 0.7.1 runtime/SIF. From an updated repository checkout in the native login shell:

```bash
git pull --ff-only
./bin/ws sessions
./bin/ws sessions --json
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

1. Use the site's approved way to reach the **recorded login node**. A short `hostname` is not necessarily a Windows-resolvable SSH address. Use a saved PuTTY connection or approved SSH alias for that specific node when supported; otherwise follow the site's supported hop/sticky-login procedure.
2. Check `hostname` after connecting.
3. Change to the original project and run `ws session` with the same image/release and state location. An update selects a different release and therefore a different managed tmux server. Use the recorded image with `--image` if returning to an older release.

The lookup does not change SSH routing, renew Kerberos tickets, or move processes. If the session ended, start a new one and recover saved files/editor layouts normally. Keep workspace state on storage shared by the relevant login nodes; a node-local state directory cannot provide discovery from another node.

Until using the updated launcher, `hostname` inside the workspace and the node in tmux's status bar provide the immediate reminder. You can use the repository lookup against the existing 0.7.1 installation without rebuilding its SIF. To record full metadata with that image, use the repository's `bin/ws session` with your existing `--image` and `--project` paths. Running `./setup` still installs the published recommended runtime, not unshipped repository changes.

See [Windows connections](windows-vscode-hpc.md), [tmux and interactive jobs](editor-and-agents.md#interactive-jobs-and-tmux), and [persistent state](dotfiles.md#persistent-state).
