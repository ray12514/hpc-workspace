# A native tools layer for everyday HPC work

Research date: 23 September 2026. This is a proposed direction following the clarified requirement: keep the normal cluster shell and add consistent appearance and useful tools. No target cluster was accessed, no private profile was inspected, and no cluster compatibility is claimed. The reported tmux startup and bat/SSL failures are separate diagnostic questions; their causes cannot be inferred from an approximate error description.

## Recommendation

Make **native Bash plus the versioned workspace configuration** the everyday interface. Keep native tmux, scheduler commands, environment modules, Git/SSH, filesystem access, and scientific launch commands in that environment. Add a deliberately selected set of tools through a versioned tool directory. Keep the SIF as an explicit optional environment for applications that benefit from its complete userspace.

This changes the deployment boundary, not the desired consistent experience. A container provides a consistent userspace; the user now wants consistent tools within the site's userspace. Trying to expose enough of the host to make a container indistinguishable from the native shell creates extra integration work. Filesystem binds expose paths, while environment handling and executable dependencies remain separate concerns. Apptainer documents all three separately. [Bind mounts](https://apptainer.org/docs/user/1.3/bind_paths_and_mounts.html), [environment handling](https://apptainer.org/docs/user/1.3/environment_and_metadata.html), [MPI integration](https://apptainer.org/docs/user/1.3/mpi.html)

Choose the package backend after the native interface is established:

| Delivery choice | Recommended role | Feasibility condition |
| --- | --- | --- |
| Verified upstream portable binaries | First implementation for simple utilities with suitable official artifacts | Each artifact passes CPU/kernel/dependency checks and a local smoke test |
| Site-supported Nix profile | Strong option for a larger, consistent general-purpose toolbox | A supported store and installation method are available on every intended node |
| Spack environment and build cache | Strong option when the site's Spack workflow is already useful, especially for scientific dependencies | Compatible cached builds and correctly described local externals exist |
| Per-tool Apptainer wrapper | Optional fallback for self-contained tools | The tool's paths, subprocesses, credentials, and terminal behavior have a clear contract |
| Entire daily shell inside Apptainer | Retain as an explicit workspace mode | The user intentionally wants the image's environment |

The table is an architectural judgment based on the mechanisms below, not a claim that one package manager is universally better. Do not require both Nix and Spack merely to obtain prompt styling and file navigation.

## Native tools: add commands without replacing the host

The first native release should expose selected commands such as `rg`, `fd`, `fzf`, and `bat`, with one pinned version and checksum per supported artifact. Official ripgrep releases include static Linux executables; bat publishes statically linked `musl` artifacts. These are practical candidates for direct distribution, but that property must be checked for each selected tool and asset. It should not be assumed for Neovim, tmux, language servers, or agent runtimes. [Ripgrep installation](https://github.com/BurntSushi/ripgrep#installation), [bat binary installation](https://github.com/sharkdp/bat#from-binaries)

Proposed rules for the native layer:

- Preserve the site's normal Bash startup and loaded modules. Add an idempotent interactive configuration hook after normal initialization. Compose with existing prompt hooks; do not replace them blindly.
- Expose only intended tools through the workspace's command directory. Do not put a package backend's entire dependency tree ahead of host commands. Leave `qsub`, `sbatch`, `srun`, `mpirun`, compilers, Python, curl, SSH, and Git native unless the user explicitly selects an alternative.
- Do not globally add workspace library directories to `LD_LIBRARY_PATH`, `LD_PRELOAD`, `CPATH`, or `PKG_CONFIG_PATH`. Preserve the native scientific environment. A tool requiring a special environment gets a narrowly scoped wrapper and a documented subprocess contract.
- Keep application configuration scoped to that application where practical. Do not change `XDG_CONFIG_HOME` for every host application just to style Neovim or bat.
- Keep ordinary terminal colors and text symbols as the default. Add optional enhanced visuals only after testing PuTTY and VS Code terminals.
- Release a manifest recording versions, hashes, architecture/CPU requirements, required shared libraries, source/license, and update ownership. Download and build during release preparation, not shell startup. Keep the previous release for rollback.

Native utilities still need a compatibility baseline. A Linux binary built against newer glibc may require symbols absent on an older host. Spack's own binary-cache tutorial demonstrates this constraint and explains that matching the distribution name is not itself sufficient or necessary. For dynamic native tools, build/test against the supported ABI baseline; for genuinely static tools, still verify CPU and kernel compatibility. Apptainer's version and the version of `apt` are separate from this native-binary requirement. [Spack binary compatibility example](https://spack-tutorial.readthedocs.io/en/latest/tutorial_binary_cache.html)

## Where Nix fits

Nix profiles are versioned directories of links into the store. Adding a profile's `bin` directory to the shell's path makes those tools available without changing the login shell or installing NixOS. Profile generations support rollback. For this project, pin the package-set input and expose only the selected toolbox commands rather than shadowing the host's full toolchain. [Nix profiles](https://nix.dev/manual/nix/2.34/command-ref/new-cli/nix3-profile.html)

The conventional multi-user installer creates system users and a daemon and uses elevated privileges. The single-user installer still requires an appropriate `/nix` directory; without one, creating it normally requires administrator help. Therefore, “single user” is not a guarantee of installation without site preparation. [Nix installation](https://nix.dev/manual/nix/2.34/installation/installing-binary.html)

Modern Nix supports chroot stores whose physical storage is elsewhere but whose logical path remains `/nix/store`. Running them on Linux requires mount and user namespaces. Changing the logical store path avoids that layout but prevents use of normal `/nix/store` binary substitutes. A working host-visible store is consequently simpler for this native-shell goal than a virtualized store. [Nix local stores](https://nix.dev/manual/nix/2.34/store/types/local-store.html)

Rootless projects are alternatives to evaluate, not assumed cluster capabilities. `nix-user-chroot` requires unprivileged user namespaces. `nix-portable` can use several runtimes, including a PRoot fallback, but its documentation warns that external programs cannot directly access tools in the virtualized store and that PRoot can add substantial overhead. Wrapper entry points may bridge invocation, but they do not make that boundary disappear. Use only site-supported mechanisms; this recommendation does not call for changing cluster namespace policy. [nix-user-chroot](https://github.com/nix-community/nix-user-chroot), [nix-portable considerations](https://github.com/DavHau/nix-portable#drawbacks--considerations)

Offline operation is feasible: build the intended Linux closure elsewhere, transfer all required store objects by an approved route, and import them into the compatible destination store. `nix-store --export` does not automatically include dependencies; the closure must be enumerated or copied using a closure-aware method. Runtime closure transfer is sufficient for executing already-built tools, but offline rebuilding additionally requires its build inputs and sources. Keep the deployed generation rooted against garbage collection. [Nix export](https://nix.dev/manual/nix/2.34/command-ref/nix-store/export.html)

## Where Spack fits

Spack environments provide a package manifest and a concrete lockfile. They can activate a filesystem view in the existing shell, or activate without changing the view/environment. A normal view also affects build-discovery variables, so a small command-only toolbox exposure is preferable to activating a scientific environment globally for appearance tools. Keep project toolchains separately activated. [Spack environments](https://spack.readthedocs.io/en/latest/environments.html)

Externals are a real advantage here: Spack can describe existing installations by prefix or module. Merely listing an external does not force its use; `buildable: false` and appropriate requirements express when the native provider is mandatory. This is useful for site MPI, compilers, and intentionally shared system libraries. Detection is not universal, and module-provided packages may need their modules loaded for detection. Record local details locally. [Spack externals](https://spack.readthedocs.io/en/latest/packages_yaml.html#external-packages)

**Spack does not require rebuilding every tool on every cluster.** A signed build cache may be a transferred local directory, and Spack relocates encoded installation paths when installing cached artifacts. Relocation has limits, including available path space. The build-cache-only installation option can prevent an unavailable binary from silently turning into a source build. Relocation handles location changes; it does not make incompatible libraries or CPU instructions compatible. [Spack build caches and relocation](https://spack.readthedocs.io/en/latest/binary_caches.html)

Use compatible deployment families and local external declarations, rather than promise one scientific lockfile will work everywhere. An external dependency is a destination prerequisite, not a library that automatically arrives with the cached application. The tutorial explicitly shows glibc remaining external. Build externally where a representative environment is sufficient; use an approved site build when proprietary/site-specific interfaces require it. [Spack binary-cache tutorial](https://spack-tutorial.readthedocs.io/en/latest/tutorial_binary_cache.html)

The linked Spack `latest` manual currently identifies itself as development documentation. This note uses its established concepts, not a requirement to install a development release. Select and test a particular stable Spack version before implementing commands or configuration syntax.

## Per-tool containers: useful with an explicit boundary

An Apptainer wrapper can launch a bundled tool from native Bash while leaving the parent shell native. Preserve its arguments, standard streams, exit status, current directory, and required data paths. Apptainer normally binds home and the current directory, subject to configuration and symlink rules; shared work/archive paths may need additional binds. Keeping the same absolute path inside and outside makes editor and project behavior easier to reason about. [Apptainer binds](https://apptainer.org/docs/user/1.3/bind_paths_and_mounts.html)

`--cleanenv` limits inherited variables, while explicit environment options supply the tool's needs. That is useful for a contained utility, but can also remove settings needed for authentication, proxies, or local services. Define these inputs per tool. Do not feed the complete module environment into every bundled program. [Apptainer environment](https://apptainer.org/docs/user/1.3/environment_and_metadata.html)

The process and its children still execute in the container environment. This matters for Neovim terminals, language servers, Git hooks, credential helpers, and coding agents that run arbitrary project commands. Binding a host executable into the container does not bring all of its loader, libraries, configuration, helper programs, and service connections with it. Treating those applications as transparent host tools would require additional integration; native deployment is the cleaner default for this requirement. This is an architectural inference from the documented filesystem/environment boundary, not an Apptainer limitation on interactive applications themselves.

SSH-agent access requires both the `SSH_AUTH_SOCK` value and access to its Unix socket; copying the variable alone is insufficient. Certificates are another distinct input: trusting a site's CA does not require loading the site's OpenSSL binary. Configure the appropriate certificate file/directory for each applicable TLS client. [SSH agent interface](https://man.openbsd.org/ssh-agent.1), [curl certificate handling](https://curl.se/docs/sslcerts.html)

Test a wrapper with file arguments, stdin, pipes, terminal resize, Ctrl-C, pager exit, and subprocesses before presenting it as interchangeable with a native command. Keep the main tmux server native on the selected host. A reconnect preserves a server on that host; it does not migrate a live process to another node. [Tmux manual](https://man.openbsd.org/tmux.1)

## Library isolation and security updates

The user's shared-library patching rationale is valid **when the application actually loads that maintained shared library**. It is not determined simply by which package manager installed the executable.

| Dependency arrangement | What an administrator's host-library update changes |
| --- | --- |
| Application dynamically uses the updated, ABI-compatible host library | New processes can load the patched library; existing processes generally need restarting |
| Spack application deliberately linked to a host external | Same benefit if runtime resolution still selects that external and compatibility is preserved |
| Application uses its own private shared library, including one in a Nix closure or SIF | The private copy remains unchanged; distribute an updated package/closure/image |
| Library is statically incorporated into an executable | Rebuild or replace the executable containing that library |

The distinction follows dynamic versus static linking and the loader's selection of actual files. OpenSSL documents compatibility within its major-version policy; libcurl documents upgrade compatibility and limitations when downgrading. Compatibility still depends on required symbols and the particular build. Running processes retain mapped libraries until restarted. [Linux loader](https://man7.org/linux/man-pages/man8/ld.so.8.html), [curl static linking](https://curl.se/docs/install.html#static), [OpenSSL compatibility policy](https://www.openssl-library.org/policies/releasestrat/), [libcurl ABI](https://curl.se/libcurl/abi.html), [Red Hat update behavior](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/10/html/using_image_mode_for_rhel_to_build_deploy_and_manage_operating_systems/performing-soft-reboots-to-rhel-bootc-images)

Do not solve this by adding host library directories globally to bundled tools. On Linux, `LD_LIBRARY_PATH` can take precedence over `DT_RUNPATH`; a matching filename may therefore select an unintended build. Missing symbols, differing ABI requirements, and transitive dependency mismatches are possible. Keep dependency sets coherent and inspect the actual resolved libraries. This is a general failure mechanism, **not a diagnosis of the reported bat error**. [Dynamic-loader search order](https://man7.org/linux/man-pages/man8/ld.so.8.html)

Nix normally records dependencies through store paths, so an OS update does not rewrite the toolbox's stored libraries. Update the pinned package set, realize a patched closure, and distribute/select the new generation. Private dependencies in other packaging formats likewise need an explicit update owner. Static binaries simplify deployment but do not remove patch responsibility. [Nix dependency model](https://nix.dev/manual/nix/2.34/introduction.html)

## Keep MPI/GPU stacks separate

The daily prompt, editor, search tools, and file navigation do not need distinct CUDA and ROCm editions merely because a cluster has one GPU vendor or the other. Package them for the intended CPU/platform baseline. Select scientific compilers, MPI, fabric libraries, and CUDA/ROCm through explicit project environments or runtime images.

For native science workflows, continue using the site's tested modules and launch conventions. For containerized science workflows, retain a separately validated MPI/GPU integration. Apptainer documents MPI compatibility, matching process-management support, and fabric requirements; its GPU support binds host libraries and warns about host/container libc mismatches. Neither Nix nor Spack metadata eliminates those runtime compatibility checks. [Apptainer MPI](https://apptainer.org/docs/user/1.3/mpi.html), [Apptainer GPU support](https://apptainer.org/docs/user/1.3/gpu.html)

## Feasibility checks that stay on the target machines

These checks can be run locally by the user or site support. No profile, hostname, directory listing, credential, or library inventory needs to be exported to this project. Public test fixtures can be transferred inward. Local reports remain local.

| Gate | Local check | Decision supported |
| --- | --- | --- |
| Native configuration | Enter and leave a test shell; compare modules, scheduler command resolution, and expected prompt hooks | The new layer preserves the native environment |
| Binary compatibility | Check CPU/ISA, kernel/glibc baseline, ELF interpreter/dependencies, then run the selected artifact with synthetic input | Select the right native build family or container fallback |
| Store support | Check whether site Nix already works across intended nodes; assess an approved rootless mechanism only if necessary | Use a native Nix profile, or keep it optional |
| Spack reuse | Try installing one representative tool from the transferred cache using build-cache-only mode; validate externals locally | Establish reuse without assuming per-cluster compilation |
| Storage | Confirm permitted executable storage, capacity/inodes, persistence, and availability on login and compute nodes | Choose the installation prefix and caching policy |
| Shell/terminal | Check Bash version, completion/fzf behavior, tmux version and terminfo, and PuTTY/VS Code input/resize behavior | Establish supported versions and fallbacks |
| Application integration | Use a disposable project to check native Git/SSH helpers, editor subprocesses, shared paths, and agent command execution | Catch boundaries that a `--version` check cannot test |
| Scientific runtime | Use approved small MPI/GPU tests within an allocation, separately from toolbox checks | Validate each actual project/runtime combination |

For ELF inspection, `readelf`/`objdump` can inspect metadata without executing the target; smoke tests should use the already verified artifacts. A glibc/CPU match is a prerequisite, not a substitute for the integration tests above.

## Migration without discarding the current work

1. Preserve the v0.4 SIF mode while diagnosing its reported failures independently. Architecture changes must not be presented as proof that either failure is fixed.
2. Extract shared appearance and navigation configuration from container-specific startup. The current Bash file resets `PATH` to `/opt/...` and replaces `PROMPT_COMMAND`; it must not be sourced unchanged on the host. Make asset paths relative to the selected workspace release and compose with native hooks.
3. Retain `~/.config/hpc-workspace/` personal overrides and the create-if-missing behavior. Add native application loaders without rewriting user preferences. Keep history, editor state, site facts, and private credentials separate from the public release.
4. Add opt-in native activation with a small verified tool manifest. Preserve ordinary host scheduler commands and filesystems directly; a submission bridge is unnecessary for this native mode. Reuse the existing prompt, tmux layout/state policy, Neovim preferences, fzf bindings, and PuTTY-safe appearance after testing their host assumptions.
5. Run the local gates for the small toolkit. Use site-supported Nix for a larger uniform toolbox where feasible; use Spack/cache delivery where its existing workflow or externals make it the better fit. Keep both backends behind the same configuration/command interface rather than duplicate the user experience.
6. Extend the toolkit only after native invocation and application subprocesses behave correctly. Add scientific Spack environments and CUDA/ROCm/MPI images as separate project choices. Existing Inspector imports remain optional cached local configuration, not a startup probe or a prerequisite for using the shell.

The result should feel like the cluster's normal shell with the user's consistent workspace added. Packaging supplies the tools; it should not determine how ordinary job submission, site modules, or shared directories behave.
