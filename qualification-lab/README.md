# Qualification Lab has moved

The experiment and qualification dashboard now lives in
[HPC Qualification](https://github.com/ray12514/hpc-qualification/tree/main/dashboard).
HPC Workspace continues to provide the portable development environment.

```bash
git clone git@github.com:ray12514/hpc-qualification.git
cd hpc-qualification
python3 dashboard/lab.py --system-id YOUR_EXISTING_SYSTEM_ID serve --port 8080
```

Use the same system ID and any explicit `--data` path as your existing installation.
The default remains `~/.local/share/qualification-lab/workspace.sqlite`; source
updates do not move or reset your database. Export a backup and stop the old
server before switching code. Existing version-1 bundles remain compatible.

See the [dashboard instructions](https://github.com/ray12514/hpc-qualification/blob/main/dashboard/README.md)
for SSH forwarding and aggregation, and the
[migration notes](https://github.com/ray12514/hpc-qualification/blob/main/docs/migration.md)
for existing installations. This directory retains this pointer only.
