# Local OCI archive to SIF conversion

Verified 2026-09-21. This note records public artifact checks and a proposed local workflow. The packages were downloaded and inspected, but neither package was installed or executed during this research. No Docker containers or cluster jobs were started.

## Pinned converter and compatibility packages

Use **Apptainer 1.5.3 in a Linux amd64 Debian 12 converter image**. The official installation guide assigns the ordinary amd64 Debian package to Debian 11/12; Debian 13 uses a separate `trixie+` package. Install the non-setuid package with `apt install ./package.deb` so its runtime dependencies are resolved. Pin the converter's base image digest separately. [Official installation instructions](https://apptainer.org/docs/admin/1.5/installation.html#install-debian-packages)

| Purpose | Package | SHA256 |
| --- | --- | --- |
| Conversion | [apptainer_1.5.3_amd64.deb](https://github.com/apptainer/apptainer/releases/download/v1.5.3/apptainer_1.5.3_amd64.deb) | `82b0bdddf459087d202383360b8318d526ad6826c748a2f669913cc6aef9ee40` |
| Separate older-runtime test | [apptainer_1.3.6_amd64.deb](https://github.com/apptainer/apptainer/releases/download/v1.3.6/apptainer_1.3.6_amd64.deb) | `2723b2928cfc30edf687723c49556ec4e013f0bf7cdb43a5a76bca7bd3c70792` |

The 1.5.3 download is 32,818,944 bytes. Its locally computed hash matches the release API's asset `digest`. The 1.3.6 download is 26,924,132 bytes; its hash above was computed from the official download, and that release API does **not** publish an asset digest. This distinction matters: the older hash records the bytes obtained, rather than an independently published checksum. [1.5.3 release API](https://api.github.com/repos/apptainer/apptainer/releases/tags/v1.5.3), [1.3.6 release API](https://api.github.com/repos/apptainer/apptainer/releases/tags/v1.3.6)

Direct inspection of the Debian archives found:

- Both identify `Package: apptainer`, `Architecture: amd64`, require glibc >=2.28, and supply `/usr/bin/apptainer`. Use separate images for the two versions.
- The 1.5.3 package includes `mksquashfs`, `unsquashfs`, `proot`, `squashfuse_ll`, and the non-setuid `starter` under `/usr/libexec/apptainer/bin`. It depends on the usual compression libraries, FUSE3, seccomp, uidmap, and fakeroot.
- The 1.3.6 package includes `squashfuse_ll` and `starter`, and declares a `squashfs-tools` dependency rather than including its own squashfs tools.

These observations are from the official package payloads linked above. No compiler, Go toolchain, Docker daemon, or Docker socket is required inside this proposed archive converter.

## Minimal conversion workflow

Export a **single-platform `linux/amd64` OCI image archive** from the existing build. Docker's `type=oci` exporter produces an OCI-layout tarball; `type=docker` produces a different layout. Its documentation requires a suitable builder driver such as `docker-container`. An example export setting is `--platform linux/amd64 --output type=oci,dest=dev.oci.tar`. [Docker OCI/Docker exporters](https://docs.docker.com/build/exporters/oci-docker/)

Apptainer 1.5.3 explicitly supports `oci-archive:`. Its pinned source extracts that archive into an OCI layout and selects the image using the requested platform. Use the matching transport; a Docker-format archive can instead use `docker-archive:`. [Supported transports](https://github.com/apptainer/apptainer/blob/v1.5.3/internal/pkg/ociimage/transport.go), [Archive fetch implementation](https://github.com/apptainer/apptainer/blob/v1.5.3/internal/pkg/ociimage/fetch.go)

After preparing the converter image, the conversion command inside it is:

```sh
apptainer build --disable-cache --notest --arch amd64 \
  --mksquashfs-args='-comp gzip -processors 2' \
  /output/dev.sif oci-archive:/input/dev.oci.tar
```

Use a read-only input mount, a dedicated writable output mount, and converter-local temporary storage with room for extracted layers plus the output. Network access can be disabled for this local archive operation. The image can use `ENTRYPOINT ["apptainer"]`. For the first conversion attempt, ordinary Docker root with its default capabilities is the minimal candidate; do not add privileged mode, FUSE, a Docker socket, or host filesystem mounts preemptively.

That permissions recommendation is an **inference from source, not a completed execution test**. The CLI does not implicitly invoke fakeroot for an unencrypted archive source, the OCI packer extracts layers and writes metadata rather than executing the image entrypoint, and the assembler constructs SquashFS/SIF files. A failure must be diagnosed before changing permissions. [CLI build prerequisites](https://github.com/apptainer/apptainer/blob/v1.5.3/cmd/internal/cli/build.go), [OCI packer](https://github.com/apptainer/apptainer/blob/v1.5.3/internal/pkg/build/sources/conveyorPacker_oci.go), [Layer extraction](https://github.com/apptainer/apptainer/blob/v1.5.3/internal/pkg/build/sources/oci_unpack.go), [SIF assembler](https://github.com/apptainer/apptainer/blob/v1.5.3/internal/pkg/build/assemblers/sif.go)

Gzip is Apptainer's compatibility-oriented default; explicitly selecting it avoids depending on another compressor's availability on older systems. The `--mksquashfs-args` setting above belongs to the 1.5.3 converter, not the 1.3.6 runtime. Use an ordinary unencrypted SIF without adding overlay or newer runtime features. Record the finished SIF hash and converter/image versions with the artifact. [Build options and compression compatibility](https://apptainer.org/docs/user/1.5/build_a_container.html#alternative-compressors)

## Local Apptainer 1.3.6 test

A separate Debian 12 test image with the older package is feasible as a **test fixture**, conditional on the Docker Linux VM's namespace and mount support. Keep it separate from the converter and do not treat it as a recommendation to deploy an old runtime. First check `apptainer version`, `apptainer sif list /input/dev.sif`, and `apptainer inspect /input/dev.sif`. Reading metadata alone does not demonstrate that the image executes.

Then test the actual SIF with the older binary:

```sh
apptainer exec --no-home --pwd / /input/dev.sif /bin/true
apptainer exec --no-home --pwd / /input/dev.sif /bin/bash --version
apptainer exec --no-home --pwd / /input/dev.sif nvim --version
apptainer exec --no-home --pwd / /input/dev.sif tmux -V
```

Add the installed AI CLI version commands and an explicit writable bind test. Use a real non-root user configured in the test image to approximate cluster execution. Apptainer 1.3 supports SIF execution and `--unsquash`, which extracts the SIF to a temporary sandbox before running it. This can diagnose a FUSE-related failure, but does not remove namespace requirements or prove that normal SIF mounting works. [Apptainer 1.3 exec reference](https://apptainer.org/docs/user/1.3/cli/apptainer_exec.html)

Full nested execution requires additional Docker permissions. Upstream documents unprivileged execution with `seccomp=unconfined`, `systempaths=unconfined`, and `/dev/fuse` on RHEL-based hosts, with AppArmor differences on Debian-based hosts. `systempaths` relaxation supports PID containment; avoid adding it merely for these basic checks. Upstream also documents `--privileged` as a broader working option. Choose settings for the actual Linux host/VM and report them with the result. [Official nested-Docker guidance](https://apptainer.org/docs/admin/1.5/installation.html#running-inside-docker)

On Apple Silicon, running an amd64 container involves emulation; Docker documents native nodes and emulation as distinct execution strategies. A successful OCI conversion is not evidence that nested amd64 Apptainer execution will work under the local emulator. If namespace, mount, or emulation limitations prevent the check, record it as untested and use a native amd64 Linux VM/host for the same fixture. [Docker platform/emulation documentation](https://docs.docker.com/build/building/multi-platform/)

A passing local 1.3.6 execution check would establish only that this SIF and these commands work under that fixture. It cannot establish Apptainer 1.2 compatibility or Ruth/Jean/Blueback GPU, MPI, scheduler, driver, and site-policy compatibility; those remain separate qualifications.

## Existing editor and tmux asset record

The previous verified Neovim, tmux-resurrect, and tmux-continuum versions, archive URLs, SHA256 values, archive root directories, and entrypoints are stored in [`image/assets.lock.json`](../../image/assets.lock.json). There is no separate Markdown note for those assets.
