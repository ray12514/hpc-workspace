# Shipped skills

The 2026-09-21 baseline contains 25 skills from [Matt Pocock's skills repository](https://github.com/mattpocock/skills/tree/c55ee46073ed923f86ce59a5eb3b6d895095d1b7) at commit `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`, plus `find-skills` from [Vercel's skills repository](https://github.com/vercel-labs/skills/tree/7407f3893ad4dceab546ac002c3ef806e4000c73) at commit `7407f3893ad4dceab546ac002c3ef806e4000c73`.

The source copies are under `share/skills`; `share/skills.lock.json` records their source paths and folder hashes. Original license texts are retained as `share/LICENSE-mattpocock` and `share/LICENSE-vercel`. The copies were verified against the updated workstation installation before being included in the image.

The current thin image **bundles these copies** under `/workspace-tools/share/skills`, but its entrypoint does **not** run the older skill-link installer. Bundled files therefore do not, by themselves, mean the skills are activated for an agent. Existing user-managed skills remain separate from the image. Automated activation in the thin runtime is an outstanding integration task.

The older 0.4 core entrypoint installed user-owned snapshots and managed agent links. Those existing snapshots/links can remain in the home directory after an upgrade. A `~/.local/share/hpc-workspace/skills` directory is not the runtime installation, and the thin release does not refresh it automatically. Do not infer active skill versions from the selected SIF alone.

To refresh, review the upstream changes, update the workstation's shared skills through the existing skills installer, and copy the selected skill folders, lock record, and licenses into a new image release. Start new Codex and Claude Code sessions after switching releases. Skills are instructions and supporting files; shipping them does not automatically install every optional tool that an individual skill might call.
