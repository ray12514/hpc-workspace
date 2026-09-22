#!/bin/bash
#SBATCH --job-name=workspace-hello
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=00:02:00
# Add the site's required account, partition, and resource directives above.
set -eu
cd -- "$SLURM_SUBMIT_DIR"
printf 'Native Slurm job %s on %s\n' "$SLURM_JOB_ID" "$(hostname)"
printf 'Submission directory: %s\n' "$PWD"
# Initialize the site's module system here before loading a compiler or MPI.
