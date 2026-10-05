# Shipped skills

The 2026-09-21 baseline contains 25 skills from [Matt Pocock's skills repository](https://github.com/mattpocock/skills/tree/c55ee46073ed923f86ce59a5eb3b6d895095d1b7) at commit `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`, plus `find-skills` from [Vercel's skills repository](https://github.com/vercel-labs/skills/tree/7407f3893ad4dceab546ac002c3ef806e4000c73) at commit `7407f3893ad4dceab546ac002c3ef806e4000c73`.

The source copies are under `share/skills`; `share/skills.lock.json` records their source paths and folder hashes. Original license texts are retained as `share/LICENSE-mattpocock` and `share/LICENSE-vercel`. The copies were verified against the updated workstation installation before being included in the image.

Starting with 0.7.3-preview7, the thin image bundles these copies under `/workspace-tools/share/skills`. On entry, it copies them into a versioned, persistent snapshot under `~/.local/share/hpc-workspace/skills/RELEASE` and links each skill into `~/.agents/skills`, where Codex discovers user skills. The native Codex TOML does not control skill discovery. New Codex sessions see the skills after a new workspace entry; restart Codex if an already-running process has not refreshed its list.

An existing user skill at the same path, whether a directory or an external symlink, is preserved. Workspace-managed links from older snapshots are updated to the selected release. Entering an older image again can select its older snapshot, so use a new workspace entry with the release you intend to run. The older 0.4 core entrypoint used the same user-owned snapshot approach. A `~/.local/share/hpc-workspace/skills` directory alone is not a runtime installation.

Inside a new preview7 workspace, check activation without printing credentials:

```bash
test -f ~/.agents/skills/codebase-design/SKILL.md && echo 'Workspace skills ready'
```

In Codex, `/skills` lists available skills. Codex also accepts `$` followed by a skill name in a prompt. Pi may have its own skill discovery behavior; this activation has been verified for the documented Codex user path.

To refresh, review the upstream changes, update the workstation's shared skills through the existing skills installer, and copy the selected skill folders, lock record, and licenses into a new image release. Start new Codex and Pi sessions after switching releases. Skills are instructions and supporting files; shipping them does not automatically install every optional tool that an individual skill might call.
