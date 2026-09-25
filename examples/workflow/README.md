# Workspace practice project

Small, synthetic files for the [daily workflow guide](../../docs/daily-workflow.md). Copy this directory to a writable practice location before editing. Nothing here submits a scheduler job, accesses a node inventory, uses an AI API, or downloads a dependency.

`just check` runs the packaged lint/format checks. `just run` uses host `python3` to execute the tiny solver. `config/`, `logs/`, and `reports/` are independent sample inputs for navigation, search, and data-query exercises; the solver does not consume them. `jobs/check.sh` is a local shell script, not a PBS or Slurm submission template.
