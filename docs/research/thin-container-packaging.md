# Packaging a thin container that uses the cluster's software

Research date: 23 September 2026. Status: design evidence and pilot recommendation. The selected direction remains an Apptainer/SIF development container. This note does not propose replacing it with a host-installed toolbox. No target cluster was accessed, no private configuration was collected, and no target compatibility has been established. The reported tmux and bat failures remain separate diagnostic questions.

## Recommendation

Use **Nix to prepare the developer-tool packages inside the image**, and pilot a **coherent host-userspace mount profile** for the desired Open OnDemand-like experience. Keep the workspace's tool store and startup files outside the host directories that this profile replaces. This is a proposed implementation choice, not a claim that every tool already exists in the package set or that the existing image supports these mounts.

The intended result is one container shell with two deliberate software sources: pinned workspace tools under `/nix/store`, and the cluster's normal commands at their normal paths. Shared storage retains the same paths. Host scheduler commands, modules, and compiler installations are reused; the container does not recreate the scheduler or its configuration.

Open OnDemand documents a close precedent: its LinuxHost adapter can use a base image matching the host OS and bind most of the host filesystem so applications installed on the host can run inside. Its documented mount set includes `/etc`, `/usr`, `/opt`, `/run`, and `/var`; a troubleshooting example also includes `/lib` and `/lib64`. It specifically excludes replacing `/`, because the runtime needs container metadata at the root. This establishes a real pattern, **not a tested mount recipe for Ruth, Jean, or Blueback**. [Open OnDemand LinuxHost](https://osc.github.io/ood-documentation/latest/installation/resource-manager/linuxhost.html)

Retain a narrower image-userspace mode for self-contained work and as a diagnostic comparison. Use Spack where a scientific environment actually needs its compiler, variant, and external-package model; adopting both package managers for the initial shell toolbox is unnecessary.

## Two container strategies, with different contracts

| Strategy | What supplies the normal Linux userspace? | Host software support | Main responsibility |
| --- | --- | --- | --- |
| Image userspace with curated site mounts | The image supplies `/usr`, its loader, and system libraries | Explicitly selected client/runtime installations are mounted and tested against that userspace | Maintain a compatible client dependency set and its configuration |
| Coherent host userspace with a private toolbox | A validated profile exposes the host's matching executable, loader, library, and configuration trees | Broad access to native commands is the goal, while workspace commands use their private packages | Keep the host trees coherent and preserve the private store and container startup paths |

**Design judgment:** the second strategy better matches the user's desktop-container precedent and desire to run ordinary site commands. The first is a useful smaller integration pilot, but should not quietly become the permanent answer if it only supports a few scheduler operations.

Mounting a single binary is insufficient evidence of runtime compatibility. An ELF executable identifies a dynamic interpreter; its libraries are resolved using encoded paths, environment settings, the library cache, and default locations. Scripts also need their interpreter and any commands they invoke. These paths resolve in the container's filesystem view. A host executable mounted under `/host` does not thereby execute outside that view. [Linux dynamic loader](https://man7.org/linux/man-pages/man8/ld.so.8.html), [Apptainer runtime scripts](https://apptainer.org/docs/user/1.3/definition_files.html)

For the coherent-host strategy, treat `/usr`, the relevant `/lib*` trees, `/bin`/`/sbin` layout, configuration, and site installations as one compatibility set. Replacing only the host loader while leaving unrelated image libraries underneath is not that strategy. Start with a scaffold matching the host's OS family and root layout, as the OOD precedent does. Whether one scaffold can serve every target is a pilot result, not an assumption based on GPU vendor.

Do not relax the existing launcher's generic bind restrictions to implement this. Add a named, separately validated runtime strategy. In particular, a host `/opt` bind would hide the current `/opt/workspace` entrypoint. Proposed workspace-owned paths must be outside replaced trees, and the launcher must reject profiles that cover them or `/.singularity.d`.

## Why Nix is the initial toolbox candidate

Nix-built Linux packages can use a loader and dependency paths within `/nix/store`, distinct from ordinary distribution library paths. That layout is the useful property here: a host `/usr` mount need not hide the tool's private dependency set. It does not imply that arbitrary host executables become Nix packages. [NixOS binary packaging guide](https://wiki.nixos.org/wiki/Packaging/Binaries)

Nix's container builders include the runtime closure of referenced packages in the generated image. Nixpkgs also supplies helpers for conventional `/bin/sh`, `/usr/bin/env`, CA files, and basic account files when building minimal images. Those helpers are image-building components, not a replacement for cluster identity integration. [Nixpkgs container builders](https://nixos.org/manual/nixpkgs/stable/#sec-pkgs-dockerTools)

The proposed release process is:

1. Pin the package-set revision and any separately packaged upstream tools.
2. Realize the Linux toolbox in the local build environment; use binary substitutes when available and build missing packages there.
3. Put the selected tools and their complete runtime closure at their original `/nix/store` paths in the image.
4. Add the workspace startup/configuration layer at a protected path, plus a small directory exposing only the selected user-facing commands.
5. Produce, test, checksum, and transfer the SIF using the existing offline delivery workflow.

Daily startup should invoke already-built programs directly. It should not run a package install, evaluate a development shell, or require a Nix daemon on the cluster. A SIF containing the tools' store paths does not require `/nix` to be installed on the cluster host. Nix's documented Docker-image workflow runs the resulting image through the container runtime. [Nix container workflow](https://nix.dev/tutorials/nixos/building-and-running-docker-images.html)

Keep the initial runtime store read-only. Put history, editor state, tool caches, credentials, and personal dotfiles in the chosen writable user locations. Updating tools initially means selecting a new SIF and retaining the old one for rollback. This is a project delivery decision, not a restriction that Nix requires an immutable container.

If later requirements call for package installation during a session, design that as a separate feature: writable store/database locations, ownership, locking, quota, concurrent access, offline sources, and garbage-collection roots all need a contract. Nix normally opens its store database for writing even for queries; its explicit read-only store mode has additional conditions. Merely including the `nix` executable in a SIF does not solve this. [Nix local-store behavior](https://nix.dev/manual/nix/2.34/store/types/local-store.html)

Offline cache transfer remains possible for release preparation or a later mutable tool layer. `nix copy` copies closures to and from stores, including a local filesystem binary cache. An executable's runtime closure is different from the additional sources and build inputs needed to rebuild it offline. [Nix closure copying](https://nix.dev/manual/nix/2.34/command-ref/new-cli/nix3-copy.html)

## Where Spack fits inside the container

Spack is also a valid image-building backend. Its container support produces Dockerfiles or Singularity definition files, uses build/runtime stages, and permits custom final images. Its documentation makes the builder responsible for ensuring the resulting artifacts execute in that final userspace. [Spack container recipes](https://spack.readthedocs.io/en/v1.0.0/containers.html)

Spack's external packages can describe site installations by prefix or module and require them when appropriate. That is useful for scientific toolchains and intentionally host-maintained dependencies. An external declaration describes an installation; it neither mounts that installation into an Apptainer runtime nor supplies its service configuration. Those remain runtime responsibilities. [Spack external packages](https://spack.readthedocs.io/en/v1.0.0/packages_yaml.html#external-packages)

Spack supports reusable binary caches, including local filesystem mirrors. This design comparison does **not** assume a rebuild on every cluster. [Spack binary caches](https://spack.readthedocs.io/en/v1.0.0/binary_caches.html)

The deciding difference for this proposal is the userspace boundary. Spack's binary-cache tutorial explicitly treats glibc as external and demonstrates a container failing without a compatible base libc. A Spack toolbox can therefore work well with a validated host/base compatibility family; it is not automatically insulated from replacing the image's distribution runtime. [Spack container and libc example](https://spack-tutorial.readthedocs.io/en/latest/tutorial_binary_cache.html)

| Initial requirement | Proposed choice |
| --- | --- |
| Consistent editor, terminal, search/navigation tools, and agent runtimes | Nix closure in the SIF, subject to package and integration checks |
| Existing scheduler clients, module software, and site compiler installations | Runtime mount/environment profile; neither package manager recreates these |
| Future scientific stacks with compiler variants and site MPI/GPU externals | Evaluate a separate Spack environment or image for that workload |
| Custom HPC utilities such as Lib Locator | Package the public utility and its private dependencies with the toolbox; retain private discovery/configuration on the site |

The Spack 1.0 documentation above establishes available mechanisms; it is not a version pin for implementation. The implementation must select and test a maintained release of each chosen build tool.

## Integration issues that the private store does not remove

### Environment and child commands

Apptainer adjusts `PATH` and `LD_LIBRARY_PATH`, and `--cleanenv` suppresses most inherited variables. Therefore, the current clean environment and hardcoded image PATH do not preserve a loaded site environment automatically. A host-integrated strategy needs explicit startup ordering and a documented treatment of module variables. [Apptainer 1.3 environment handling](https://apptainer.org/docs/user/1.3/environment_and_metadata.html), [Apptainer 1.5 environment handling](https://apptainer.org/docs/user/1.5/environment_and_metadata.html)

Proposed startup order: make the selected site runtime paths available; initialize the site's module mechanism using its supported Bash initialization; then add the selected workspace commands and appearance configuration. Modules are shell functions/aliases that apply generated environment changes, so copying a `module` executable or preserving only `MODULEPATH` is insufficient. [Lmod initialization](https://lmod.readthedocs.io/en/latest/030_installing.html), [how the module function works](https://lmod.readthedocs.io/en/latest/040_FAQ.html)

Private paths are not immunity from injected libraries. `LD_LIBRARY_PATH` can precede `DT_RUNPATH`, and preloads can affect a program before it starts. Do not globally add private toolbox libraries to the shell environment. [Linux loader search rules](https://man7.org/linux/man-pages/man8/ld.so.8.html)

**Pilot requirement:** verify toolbox commands both before and after representative module loads. A blanket wrapper that unsets site library variables can protect an editor's startup but also removes those variables from the compiler, debugger, terminal, or agent command that the editor starts. The solution must be checked at both the application and subprocess levels. Do not claim generic wrapper transparency until these tests pass.

Keep scientific compiler search variables and language environments scoped to their intended workloads. Do not expose every dependency's `bin` directory just because it exists in the toolbox closure. In particular, a private Python, compiler, or curl needed internally by a tool need not become the shell's default command.

### Identity, name service, certificates, and interpreters

Apptainer supplies adapted account/group files and DNS configuration under its normal configuration. That gives an important baseline but does not prove every directory-service lookup from every library works. [Apptainer 1.3 default binds](https://apptainer.org/docs/user/1.3/bind_paths_and_mounts.html)

Name-service configuration can select dynamically loaded NSS modules. Nixpkgs' glibc configuration still uses `/etc` for system configuration, so binding host configuration can make a private Nix process request a site-specific service. Test current-user/group lookup, other relevant account lookup, and DNS from both host-linked and Nix-linked commands. Do not assume host NSS plugins can be inserted into a different glibc without checking compatibility; an existing supported name-service daemon interface may be applicable, but is a site-specific decision. [NSS configuration](https://man7.org/linux/man-pages/man5/nsswitch.conf.5.html), [Nixpkgs glibc configuration](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/pkgs/development/libraries/glibc/common.nix), [nscd](https://man7.org/linux/man-pages/man8/nscd.8.html)

A site CA file is trust configuration, distinct from the OpenSSL library. Expose approved trust files locally and configure the relevant clients to use them; do not disable verification to get a successful network test. Different clients need their own verified behavior. [curl certificate configuration](https://curl.se/docs/sslcerts.html)

Nixpkgs rewrites installed script shebangs to store interpreters. Existing user/site scripts can still reference `/bin/bash` or `/usr/bin/env` and select a different interpreter. Test those ordinary script paths, Neovim terminals, Git hooks, and agent subprocesses against the intended command precedence. [Nixpkgs shebang handling](https://nixos.org/manual/nixpkgs/stable/#sec-stdenv)

### Native scheduler submission

The goal remains ordinary `sbatch`, `qsub`, query commands, and native arguments. Mount the client runtime, plugins, configuration, and service interfaces required by the site's real installation. For example, Slurm's official container examples expose its configuration and the MUNGE socket where that authentication method is in use; the method and paths must not be assumed from the word “Slurm.” [Slurm container integration](https://slurm.schedmd.com/containers.html)

PBS is a separate feasibility check. OpenPBS documents installations with a setuid `pbs_iff` helper, while Apptainer normally prevents privilege elevation in containers. The existence of `qsub` and its libraries therefore does not prove submission works under every PBS authentication arrangement. A failed local pilot must lead to the site's supported submission path, not an attempt to bypass that behavior. [OpenPBS installation](https://github.com/openpbs/openpbs/blob/master/INSTALL), [Apptainer privilege model](https://apptainer.org/docs/user/1.3/security.html)

Successful submission also does not prove the resulting job has the intended environment. Slurm `sbatch` defaults to exporting the caller's environment. A toolbox-only PATH or variables pointing inside the SIF can then reach a native job where those paths do not exist. PBS has its own `-v`/`-V` and original-environment variables; do not translate the Slurm rules to it. [Slurm environment export](https://slurm.schedmd.com/sbatch.html#OPT_export), [PBS Professional user guide](https://help.altair.com/2024.1.0/PBS%20Professional/PBSUserGuide2024.1.pdf)

**Design requirement:** preserve native submission arguments and explicit user export requests. Decide and test how workspace-only environment additions are excluded from a native job without discarding intentional module or user changes. No silent universal `--export=NONE`, no hidden scheduler-language translation, and no blanket claim that the existing host bridge supports every command. A job script should re-enter the SIF explicitly when it needs the toolbox there.

## Runtime mounts and delivery boundaries

Apptainer 1.3 and 1.5 both support explicit read-only/read-write binds and mounts from SquashFS/SIF data images. Automatic home/current-directory binds and administrator defaults are configurable; current-directory symlinks can affect the automatic bind. Record an intentional site recipe instead of treating those defaults as a portable guarantee. [Apptainer 1.3 bind interface](https://apptainer.org/docs/user/1.3/bind_paths_and_mounts.html), [Apptainer 1.5 bind interface](https://apptainer.org/docs/user/1.5/bind_paths_and_mounts.html)

Missing bind destinations depend on overlay/underlay support, and writable containers require existing destinations. Administrator policy also controls user binds and mount propagation, including visibility of later autofs mounts. Build predictable mount points and test the actual site configuration on the 1.3.6 baseline and supported 1.5 version. A manual for a version family is not an execution test of a site's patched binary. [Apptainer mount configuration](https://apptainer.org/docs/admin/1.3/configfiles.html)

Proposed mount categories are:

- User data and persistent state: home, work, scratch, archives, and workspace state at stable paths, with the user's existing permissions.
- Host software and configuration: a coherent userspace recipe, generally read-only, plus selected configuration and plugin trees.
- Live host interfaces: specific runtime/socket paths needed by the chosen services; do not infer that every file under `/var` or `/run` is required.
- Workspace-owned content: the Nix store, tool entrypoints, startup configuration, and Apptainer metadata remain visible and protected from covering mounts.

A separate read-only SquashFS toolbox layer is a reasonable later delivery optimization. It needs a complete compatible closure at `/nix/store`; mounting another store there hides the store already in the base image, so it is not automatically an additive package merge. Start with the complete closure in one SIF to keep update and rollback behavior clear. This is an inference from bind-mount replacement semantics and a proposed staging choice, not a restriction on Apptainer's image-mount support.

Host libraries that are actually loaded remain under site update ownership. Libraries copied into the image or a Nix/Spack private installation remain under workspace release ownership. A host library patch does not rewrite a private stored copy. Conversely, deliberately using a host external requires preserving its ABI and runtime selection. Verify loaded paths rather than infer patch ownership from the package manager's name. [Nix package dependency model](https://nix.dev/manual/nix/2.34/introduction.html), [Spack externals](https://spack.readthedocs.io/en/v1.0.0/packages_yaml.html#external-packages)

## What the pilot must establish

These are proposed acceptance tests. They have not been run on the target systems.

| Check | Required outcome |
| --- | --- |
| Startup and mounts | Protected image files remain visible; selected host paths resolve as intended; missing required mounts fail clearly |
| Toolbox | Bash interaction, tmux keyboard/resize, bat paging and Git diff, fzf history, and Neovim work with read-only image content and writable user state |
| Mixed runtime | Host and private tools resolve the intended libraries before/after site module loads; current identity, DNS, trust, locales, and terminal behavior work |
| Modules and compilers | Site module initialization and a small compiler invocation work; Neovim/agent child commands see the same intended site environment |
| Scheduler | Query and a minimal native script submission work with existing authentication and unchanged native arguments |
| Native job environment | The job sees deliberate user/module settings and does not accidentally depend on container-only paths; explicit export options retain their meaning |
| Interactive allocation | The same SIF can be entered on an allocated node with the appropriate node-local profile and shared state |
| Updates | A new image is selected without overwriting personal configuration; the previous image remains usable |

Test local fixtures on both supported Apptainer versions before delivery. Site checks and their detailed output stay on the relevant machines; public templates need only generic schema, example placeholders, and expected outcomes. Cluster Inspector can supply existing local discovery facts when available, but its presence does not itself establish that a mount or scheduler authentication path has passed these tests.

The first milestone is evidence for the two sources of software sharing one container shell. MPI, GPU execution, and fabric integration remain workload-specific extensions after that milestone; neither Nix nor Spack removes their runtime compatibility requirements. [Apptainer MPI integration](https://apptainer.org/docs/user/1.3/mpi.html), [Apptainer GPU integration](https://apptainer.org/docs/user/1.3/gpu.html)
