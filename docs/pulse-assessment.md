# Pulse integration assessment

Pulse is the telemetry application in the adjacent `pulse` repository. It provides a small CLI/TUI, but useful job monitoring is a service deployment: Prometheus stores metrics, `node_exporter` and optional GPU collectors run against allocated nodes, and scheduler hooks publish job targets. The terminal UI queries Prometheus; it does not collect metrics by itself. See Pulse's [architecture](https://github.com/ray12514/pulse/blob/af1483a/docs/ARCHITECTURE.md), [exporter configuration](https://github.com/ray12514/pulse/blob/af1483a/configs/pulse-exporters.yaml), and [individual deployment guide](https://github.com/ray12514/pulse/blob/af1483a/docs/admin/individual-deployment-guide.md).

## Recommendation

Keep Pulse separately versioned in a persistent, user or site managed prefix, then use its CLI from the workspace. The workspace mounts the host's software and home paths, so a compatible Pulse installation can be visible without rebuilding the development SIF. Keep Prometheus data and process lifetime outside a short `ws enter` shell. Pulse's own personal mode and `pulse attach` are designed for this lifecycle. Do not auto-start network services just because a user enters the workspace.

Bundling only the Pulse CLI would be modest in size, but would not meet the monitoring requirement. The local beta archive is about 5.6 MiB compressed and currently contains `pulse-installer` but no `bin/pulse`, Prometheus, `node_exporter`, or GPU exporter binaries. The active Pulse checkout also has uncommitted implementation work. A reproducible bundle should first be cut from a chosen commit with all required binaries, versions, and checksums recorded.

## Site dependencies to resolve

- Confirm a persistent, site-appropriate Prometheus data path and a login or service host allowed to run its listener. A shared home directory is not automatically a suitable TSDB path.
- Confirm compute-to-service-host connectivity and a shared target directory for job discovery.
- Confirm the scheduler hooks and the one-job-per-node accounting assumption for the target queues. Whole-node `node_exporter` metrics would misattribute use on shared nodes.
- For NVIDIA, match DCGM Exporter to the site's driver/DCGM stack and test on an allocated GPU node. For AMD, the shipped textfile collector calls the node's `amd-smi` or `rocm-smi`; the workspace SIF cannot supply the host driver.
- Validate Pulse from the user's ordinary host shell and then from a new workspace shell. Check that service processes survive leaving that shell only when explicitly managed by Pulse or the site.

The 0.7.3-preview7 workspace release adds `nvtop` for immediate, local GPU observation. It does not start Pulse, Prometheus, or exporters. The next Pulse integration should begin with a complete, pinned Pulse release and site-specific service acceptance; image inclusion can then be decided from actual sizes and runtime behavior.
