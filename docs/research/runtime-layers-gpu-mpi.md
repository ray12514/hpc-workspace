# Read-only software payloads, GPU access, and MPI

Research date: 2026-09-22. Public primary documentation and upstream source only. No cluster connection, private configuration, GPU execution, or MPI execution was used. The user reports that the baseline SIF starts successfully on a target system; that does not yet establish support for additional image mounts, GPU workloads, or MPI.

**Recommendation:** preserve the common development SIF and introduce optional, versioned software payloads only where they form a coherent installation prefix. A SquashFS payload is a useful distribution unit for compilers, Python environments, or a compatible CUDA/ROCm toolkit. Host GPU drivers, scheduler integration, and the native MPI/fabric connection remain a separate, locally qualified contract. Keep a complete GPU-specific SIF as an alternative when a toolkit needs extensive changes to the base operating environment. These are proposed design choices, not features already delivered by the workspace launcher.

## What Apptainer 1.3.6 supports

The 1.3 guide documents mounting the contents of an ext3, SquashFS, or SIF data image into an existing container. SquashFS is read-only. The `image-src` option identifies the directory **inside** the payload; omitting it mounts the image file itself. This is supported in the actual v1.3.6 implementation, including an explicit read-only mount flag for SquashFS data partitions. [Apptainer 1.3 image mounts](https://apptainer.org/docs/user/1.3/bind_paths_and_mounts.html#image-mounts), [v1.3.6 implementation](https://github.com/apptainer/apptainer/blob/v1.3.6/internal/pkg/runtime/engine/apptainer/container_linux.go#L1220-L1350)

Illustrative **raw Apptainer** commands, assuming a compatible payload has already been built with its installation contents at the payload root:

```bash
# Read-only data-image mount; available in the 1.3 baseline.
apptainer exec \
  --bind /path/toolkit.squashfs:/opt/toolkit:image-src=/ \
  /path/workspace.sif /opt/toolkit/bin/tool --version

# Equivalent long form, making read-only intent explicit.
apptainer exec \
  --mount type=bind,src=/path/toolkit.squashfs,dst=/opt/toolkit,image-src=/,ro \
  /path/workspace.sif /opt/toolkit/bin/tool --version
```

The current `ws` launcher accepts directory/file binds with `ro` or `rw`; it does not yet expose `image-src`. Supporting these examples through `ws` requires a launcher extension and tests. They are not current `ws` syntax. The 1.5 guide retains image mounts, so this design need not depend on a 1.5-only feature. [Apptainer 1.5 image mounts](https://apptainer.org/docs/user/1.5/bind_paths_and_mounts.html#image-mounts)

Three mechanisms have different purposes:

| Mechanism | Meaning for this workspace |
| --- | --- |
| Base SIF | Supplies the container's root filesystem and development tools. |
| SquashFS data-image bind | Adds one read-only directory tree at a selected prefix, such as `/opt/toolkit`. |
| Overlay | Merges another filesystem into the container filesystem; writable persistent overlays retain changes, while `--writable-tmpfs` discards changes at exit. |

The documented writable overlay formats are an ext3 image or directory. The v1.3.6 runtime can also use SquashFS as a read-only overlay lower layer. For this project, explicit data-image mounts make the boundary between independent toolkits easier to understand than stacking changes across `/usr` and `/lib`. The last sentence is a design recommendation. [Persistent overlays](https://apptainer.org/docs/user/1.3/persistent_overlays.html), [v1.3.6 overlay implementation](https://github.com/apptainer/apptainer/blob/v1.3.6/internal/pkg/runtime/engine/apptainer/container_linux.go#L1110-L1145)

## Mounting depends on the site's runtime configuration

Payload mounting does not inherently require root. Apptainer can use FUSE in unprivileged user namespaces. The admin guide recommends kernel 4.18 or newer for unprivileged FUSE mounts; filesystem and kernel configuration still matter. This uses Apptainer's image-mount machinery, not a requirement to install and operate a separate `--fusemount` command for every payload. [User namespace requirements](https://apptainer.org/docs/admin/1.3/user_namespace.html#user-namespace-requirements)

In v1.3.6, `allow setuid-mount squashfs` defaults to `iflimited`: without configured execution restrictions it selects FUSE; with container limits or the execution control list it selects kernel mounts. A site can alter this. User binds can also be disabled, and image-format or path restrictions may apply. Do not infer that a successful base SIF launch proves every additional image mount is permitted. Test one tiny data payload using the installed runtime before selecting this packaging strategy. [v1.3.6 configuration defaults](https://github.com/apptainer/apptainer/blob/v1.3.6/pkg/util/apptainerconf/config.go#L363-L394), [runtime configuration](https://apptainer.org/docs/admin/1.3/configfiles.html#bind-mount-management)

## A mounted toolkit must still be compatible

Mounting supplies files. It does not select dependency versions, relocate installed binaries, translate instruction sets, or reconcile incompatible ABIs. That is an engineering consequence of the mount operation and the compatibility requirements below. A software tree copied from a different OS or installed at another prefix is not automatically usable.

Build each payload against a declared base release and mount it at its installation prefix. Include its non-base dependencies or explicitly declare them. Install scripts, Python shebangs, binary RPATHs, and configuration files may encode paths. Spack's own binary-cache installer performs explicit relocation, including encoded paths in binaries and scripts; merely mounting a SquashFS does not perform that work. [Spack build-cache relocation](https://spack.readthedocs.io/en/v1.1.1/binary_caches.html#relocation)

**Proposed manifest fields:** payload name/version and hash; build recipe/source revision; compatible base SIF hashes or qualified releases; mount prefix; OS/glibc and compiler/C++/Fortran runtime requirements; CPU ISA; CUDA or ROCm version; supported GPU code targets; host-driver compatibility requirements; MPI ABI family if applicable; required external dependencies; activation environment; and locally completed validation stages. Choose a conservative CPU target for shared tools and specialized targets for performance-sensitive applications.

A payload should have one explicit activation procedure. Avoid unconditionally placing every payload library on the global `LD_LIBRARY_PATH`. If a toolkit cannot stay within a manageable prefix and dependency set, build a complete variant from the shared development recipe. Updating the base can require rebuilding or requalifying its payloads.

**Native batch jobs need a native-compatible build.** The current baseline has Ubuntu 24.04, glibc 2.39, and GCC 13.3.0, as recorded in [local validation](../validation.md). A binary compiled there may require symbols unavailable on an older host even if it does not use MPI. A glibc maintainer describes precisely this newer-binary/older-runtime failure mode. For jobs that run natively, use the host's supported scientific toolchain, or a deliberately compatible build environment/sysroot. Otherwise execute the application inside its matching runtime SIF and payload. Editing/submitting a native batch script from the development environment does not by itself make its executable depend on that environment. [glibc maintainer explanation](https://sourceware.org/pipermail/libc-alpha/2016-July/073191.html), [compatible container/sysroot approach](https://sourceware.org/pipermail/libc-alpha/2023-July/150164.html)

## GPU access and GPU development are separate concerns

Apptainer's `--nv` and `--rocm` expose GPU devices and selected host libraries and adjust library lookup. They do not install a full compiler/SDK into the container. An application must still have its required libraries and a supported device target. Host libraries injected by these flags can also encounter container libc incompatibility. Use the vendor flag appropriate to an allocated node, preserve its scheduler GPU selection, and check the libraries actually loaded. [Apptainer 1.3 GPU support](https://apptainer.org/docs/user/1.3/gpu.html)

The three relevant pieces are:

| Piece | Where it belongs |
| --- | --- |
| Kernel GPU driver and device access | Managed on the host; a toolkit payload cannot replace them. |
| CUDA/ROCm user-space compiler, headers, and libraries | A qualified payload or complete GPU SIF variant. |
| Application and compiled GPU kernels | Built for supported GPU targets against the selected runtime stack. |

For NVIDIA, select the toolkit using the host driver's supported range and the application's features. Minor-version compatibility has restrictions, including PTX and features needing newer drivers; it is not a promise that arbitrary CUDA versions work together. [NVIDIA CUDA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)

For AMD, the kernel driver remains on the host and compute access involves `/dev/kfd` and the relevant `/dev/dri` render devices. Use AMD's supported driver/user-space/GPU matrix for the intended ROCm release. Telemetry tools may have tighter driver requirements than most compute libraries. AMD lists MI200 and MI300 family code targets as `gfx90a` and `gfx942`, respectively; one ROCm payload can only cover both if its software and built kernels support both. [AMD container prerequisites](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/how-to/docker.html), [driver/user-space guidance](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/reference/user-kernel-space-compat-matrix.html), [AMD compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)

No particular toolkit version is selected by this note. The actual host-driver combinations remain local information. Device enumeration is the first test, followed by compiling and running a kernel with a known result.

## MPI remains a site integration task

Apptainer documents both a hybrid model, with compatible MPI inside the container, and a bind model, using host MPI libraries. Both normally put the native MPI launcher outside Apptainer. The application's build-time MPI must be compatible with its runtime MPI, and process management such as PMI2/PMIx must match the launch path. Mounting a different implementation cannot repair an incompatible MPI ABI. [Apptainer MPI models](https://apptainer.org/docs/user/1.3/mpi.html)

Conceptually, the application job uses:

```text
site-supported launcher → Apptainer + selected payloads → application ranks
```

HPE documents requirements for dynamically linked MPICH-ABI-compatible applications, compatible compiler/OS environments, and the site's supported launcher. Its MPI uses OFI/libfabric; Slingshot-11 requires the OFI path. GPU-aware communication also needs the appropriate vendor GTL components and `MPICH_GPU_SUPPORT_ENABLED=1` for GPU-buffer MPI operations. These requirements are additional to ordinary GPU access. [HPE Cray MPI documentation](https://cpe.ext.hpe.com/docs/latest/mpt/mpich9/intro_mpi.html)

A proposed local MPI adapter therefore records the approved MPI, PMI/PMIx or other launch support, libfabric/CXI or UCX/InfiniBand dependencies, device and configuration binds, library order, and required environment. The exact list is specific to each site's example and installed stack. Do not bind the host's entire `/usr` or `/lib` over the development image. Use a locally tested adapter or run the scientific application natively when its batch job does not need the development environment.

## Shared deployment: useful integrity, limited isolation

Read-only, versioned payloads reduce accidental modification and make rollback and shared testing easier. They do not establish that the software is trustworthy or make the entire session immutable: home/project binds remain writable where permitted. Apptainer processes retain the user's ordinary permissions, and process/network namespaces are not isolated by default. Treat the environment as consistent software packaging, not a separate-machine security boundary. [Apptainer security model](https://apptainer.org/docs/user/1.3/security.html)

For wider deployment, publish immutable release files and manifests, protect the shared release directory, keep user state separate, and update by adding a new version. Validate every external payload independently: a signature on the base SIF does not cover a separate mounted file. SIF supports signed objects and offline verification with distributed public keys; a data SIF can be considered if self-contained signatures are wanted. A checksum from a trusted release detects changes, while a validated signature additionally ties content to the chosen signing identity. [SIF signing and verification](https://apptainer.org/docs/user/1.3/signNverify.html)

There is a performance rationale beyond convenient distribution. CSCS documents the cost of many Python files and metadata lookups on Lustre, and packages such environments into SquashFS. LUMI demonstrates a SIF plus mounted SquashFS user-software environment. These are direct precedents for the proposed payload model. [CSCS storage guidance](https://docs.cscs.ch/guides/storage/), [LUMI container training](https://lumi-supercomputer.github.io/LUMI-training-materials/2day-20251020/205-Containers/)

Expected benefit: fewer shared-filesystem metadata operations and one file to stage. Not established here: a universal speedup. Compression, FUSE, caches, simultaneous startup, and payload size affect results. Benchmark both startup and the real workload; storage packaging itself does not improve an application's MPI transport or GPU kernels. Stage each selected payload once per node/job when local storage and site practice make that beneficial.

## Proposed bounded qualification sequence

1. **Mount pilot:** a tiny read-only payload with a known executable and checksum. Confirm visibility, executable permissions, write rejection, unmount at exit, and two concurrent sessions. Repeat on the oldest supported Apptainer and each target site's actual configuration.
2. **Dependency pilot:** one useful software prefix built against the current base. Verify activation, encoded paths, library selection, and preservation of the ordinary development tools. Record startup behavior on shared storage.
3. **Single-node GPU:** obtain an allocation, preserve assigned device visibility, compare native/container enumeration, then compile and run a known-answer CUDA/HIP example. Qualify each distinct GPU/driver class.
4. **CPU MPI:** establish a native baseline; run containerized ranks on one node and two nodes; check correctness, rank placement, intended fabric, and latency/bandwidth relative to native execution.
5. **GPU-aware MPI:** test GPU-buffer transfers and collectives within and between two nodes, including rank-to-GPU mapping and performance. CPU-buffer MPI passing does not satisfy this stage.
6. **Shared release:** publish only the combinations that passed, with their limits and rollback version. Requalify affected stages after base, payload, driver, MPI/fabric, or Apptainer changes. Keep cluster observations and site adapters on the systems; this workflow requires no upload of their private details.
