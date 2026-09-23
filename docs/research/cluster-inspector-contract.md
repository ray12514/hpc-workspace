# Inspector YAML input used by the workspace

Reviewed 2026-09-22. This note describes the workspace input using the public `stack-planning` contract. No real cluster profiles or reports were used.

## Public contract

The source is [profile-v1.json](https://github.com/ray12514/stack-planning/blob/da6d6eaf2ed0fbf7486f3267ee94b972f3669b54/schemas/profile-v1.json), at public commit `da6d6eaf2ed0fbf7486f3267ee94b972f3669b54`. The public schema blob was verified to match the local reference (`88fb307b7a18b368ea1ba41ff87fc7387db2fd2f`).

The profile uses `schema_version: 1`. Required top-level facts in the canonical schema are `system`, `os`, `fabric`, `modules_system`, `filesystem`, and `node_types`. Compiler, MPI, GPU toolkit, and system-external inventories are optional. The schema is strict about known properties and their types. [Canonical schema](https://github.com/ray12514/stack-planning/blob/da6d6eaf2ed0fbf7486f3267ee94b972f3669b54/schemas/profile-v1.json)

The workspace reads an existing YAML file during initial setup or explicit refresh. It does not generate that file, invoke Inspector, or require changes to the producer. Its reader validates the supported version and the fields it consumes; it is not a replacement for the producer's full canonical-profile validation. Missing optional information does not prevent the core shell from starting.

## Useful existing fields

| Public profile fields | Workspace use |
| --- | --- |
| `system.name`, `system.family` | Saved system label and configuration scope |
| `os.name`, `major`, `minor`, `glibc` | Informational host userspace facts |
| `fabric.type`, `drivers[]`, `userspace[]` | Fabric/library names, versions, and available prefixes, including libfabric |
| `modules_system.tool`, `version` | Module-system identity |
| `compiler_providers[]` | Provider names, versions, prefixes, language commands, and module chains |
| `mpi_providers[]` | Provider names, versions, prefixes or compiler-specific flavors, module chains, and compatibility facts |
| `gpu_toolkit_modules` | CUDA, ROCm, and NVHPC module/version/prefix information when present |
| `system_externals[]` | Named external packages, prefixes, modules, and optional capabilities |
| `node_types` | Named node classes with CPU targets and nullable GPU information |
| `filesystem`, node `build_stage` | Observed path candidates retained as information |

These field shapes come from the [public schema](https://github.com/ray12514/stack-planning/blob/da6d6eaf2ed0fbf7486f3267ee94b972f3669b54/schemas/profile-v1.json). The [input-ownership design](https://github.com/ray12514/stack-planning/blob/da6d6eaf2ed0fbf7486f3267ee94b972f3669b54/docs/deployment_inputs_and_ownership_v1.md) distinguishes observed filesystem candidates from chosen deployment paths. For the workspace, personal binds similarly remain explicit configuration.

The importer selects a scheduler default from a single `system_externals` entry named `pbs` or `slurm`. If neither is present, an existing named workspace default can still apply. Conflicting entries leave the scheduler unresolved unless an explicit override is configured. The optional `capabilities.mpi_launch` information describes commands/plugins/development interfaces; it is retained as data rather than used to launch MPI automatically.

GPU records include a vendor, driver version, toolkit ceiling, and architecture target. These are recorded capabilities of a node class. Device exposure in a running allocation remains a separate runtime operation. Likewise, MPI and fabric prefixes provide useful configuration inputs but are not an activation or compatibility proof.

## Local configuration lifecycle

1. Read the supplied local YAML once using the reader bundled in the workspace SIF.
2. Save relevant facts and the source path, content hash, and import time as private workspace configuration. Keep personal overrides separate.
3. Reuse the saved configuration during ordinary startup, even if Inspector or the original YAML is no longer available there.
4. Refresh explicitly after the user updates the profile through the existing Inspector workflow. Preserve image selections, personal overrides, and saved state.

The import time records the workspace action; it is not a claim about when the source system was observed. Job scripts and native scheduler behavior continue to handle job resources and placement. The importer does not need account, queue, authentication, or host-membership discovery.

The [setup and refresh guide](../inspector-integration.md) documents the implemented interface. The committed [synthetic YAML fixture](../../tests/fixtures/inspector-slurm.yaml) and tests exercise typed provider paths, malformed input, optional facts, initial setup, cached startup, and explicit refresh without using cluster data.
