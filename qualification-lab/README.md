# Qualification Lab — SSH-local HPC edition

A standalone, single-operator performance-engineering and continuous-qualification dashboard. Run it on an approved HPC service, visualization or allocated node; view it from your workstation through SSH local port forwarding. No external website, ChatGPT sign-in, package download or internet access is needed at runtime.

**Runtime:** Python 3.9+ with its standard-library `sqlite3` module. Browser assets are committed in `web/`; Node.js is only needed when developing the frontend. This component runs independently of the HPC workspace image and installer.

## Start on a system

From the repository checkout:

```bash
cd qualification-lab
python3 lab.py --system-id pilot-a serve --port 8080
```

Choose a stable, unique system ID on each installation. Use your site's permitted host and execution method; benchmark jobs still run through PBS or Slurm. The server prints an access key. Keep its terminal private and leave it running while using the dashboard.

On your workstation, connect to the same host:

```bash
ssh -N -L 127.0.0.1:8080:127.0.0.1:8080 your-user@hpc-host
```

Open **http://127.0.0.1:8080/login** and enter the printed key. The server binds only to `127.0.0.1`. Other users on a shared host still need the random key; authentication is not replaced by loopback binding. The key and browser session rotate on restart. SSH forwarding must be permitted by your site. If the server runs on a compute node behind a gateway and SSH to that node is allowed:

```bash
ssh -J your-user@login-host -N \
  -L 127.0.0.1:8080:127.0.0.1:8080 your-user@compute-host
```

This is a personal SSH-local tool, not a public or multi-user web service. Keep the listener and its access key within the intended operator workflow.

## Data and updates

The default SQLite file is `~/.local/share/qualification-lab/workspace.sqlite`. Use `--data /your/private/path/workspace.sqlite` before the subcommand to choose another location. Prefer node-local storage with reliable SQLite locking; do not share a live SQLite database among nodes on a parallel filesystem. For ephemeral allocated nodes, export before the allocation ends and preserve the database through a site-supported persistence path.

Stop with Ctrl-C before updating, then run `git pull --ff-only` from the repository and restart the same command. Keep the same system ID and database path. Code updates do not replace your data. Back up with the export command below before updating. The browser also exports a plain JSON workspace backup; that format is distinct from the checksummed cross-system bundle.

## Measured workflow

Six editable starter plans cover CPU optimization, GPU portability, MPI, AI training, serving and production recovery. All profiles are generic and all results begin unmeasured. Replace application/version, input hashes, stack and allocation placeholders with your actual experiment contract.

A run must have at least 3 positive wall-time samples, correctness within tolerance, passed correctness/recovery/operations gates and evidence references to qualify. A pinned baseline additionally enforces its slowdown budget. Gates are operator-attested, not a substitute for inspecting output/profiler evidence. Historical run snapshots cannot be edited through the API. Fork a plan for a new configuration. Markdown templates, ADRs, lifecycle history and evidence briefs are included.

## Export and aggregate across systems

On each source system, export a versioned snapshot (use a new filename each time):

```bash
python3 lab.py --system-id pilot-a export --output /your/private/export/pilot-a-001.bundle.json
```

Transfer the bundles through your approved internal path to the machine hosting the master workspace. Then:

```bash
python3 lab.py --system-id master --data /your/private/master.sqlite \
  ingest /your/private/incoming/pilot-a-001.bundle.json /your/private/incoming/pilot-b-001.bundle.json
python3 lab.py --system-id master --data /your/private/master.sqlite serve --port 8080
```

Each bundle has `schema_version`, `system_id`, `source_revision`, `workspace` and a SHA-256 checksum over the canonical envelope. Checksums detect accidental changes; they are not signatures or source authentication. Ingestion namespaces IDs by source, replaces that source's prior snapshot on a newer revision, ignores identical repeats, and rejects stale or conflicting revisions. Imported source records are read-only in the master; edit them on their source systems and import a newer bundle. Reload the master browser after ingestion. Import source-system bundles directly into the master; do not re-export masters into other masters. A source whose local history was reset needs a new system ID.

Keep collected outputs, bundles, databases, credentials and profiler traces in approved internal storage. The repository contains only generic code, templates and unmeasured profiles. GitHub is the software distribution path; it does not receive results automatically.

## GitLab handoff

The included `gitlab-ci.example.yml` can be copied into a **private internal aggregation repository**. Place approved bundles under `incoming/` there. The pipeline ingests them into a master database and packages an offline application bundle as an artifact. Download that artifact to an approved internal host, extract it, and run the documented master `serve` command through an SSH tunnel. The example intentionally does not publish GitLab Pages or upload results to GitHub. Large evidence files remain in internal storage, linked by paths/checksums in run records.

## Frontend development and verification

On a connected development machine with Node.js 22.13+ and npm:

```bash
npm ci
npm run seed
npm run build
python3 -m unittest discover -s tests -v
node --experimental-strip-types tests/qualification.test.mjs
```

Commit source, `seed.json`, the lockfile, and rebuilt `web/` assets together. Runtime hosts need none of these JavaScript build tools. The checks exercise local HTTP authentication, origin and host restrictions, persistence, revision conflicts, immutable measurements, namespaced aggregation, checksums, stale bundles and path containment. Cluster launch and live scheduler behavior require a pilot on your systems.

Documentation: [OpenSSH forwarding](https://man.openbsd.org/ssh#L), [Python sqlite3](https://docs.python.org/3.12/library/sqlite3.html), [Python HTTP server](https://docs.python.org/3.12/library/http.server.html), [Vite builds](https://vite.dev/guide/build), [GitLab job artifacts](https://docs.gitlab.com/ci/jobs/job_artifacts/), [Git pull](https://git-scm.com/docs/git-pull).
