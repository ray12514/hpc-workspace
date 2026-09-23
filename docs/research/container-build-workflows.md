# Building and testing containers from the workspace

Research date: 23 September 2026. **Status: alternatives and proposed first experiment, not a selected migration.** The current direction remains a thin development container. The user has now invited comparison with other approaches and wants to build and test other people's containers. Podman availability and configuration on Ruth, Jean, and Blueback are unverified. No cluster was accessed and no private information is required by this note.

## Recommendation

Keep the workspace container, configuration, and host container runtimes as distinct pieces. **Use Apptainer for the existing SIF workspace and HPC runtime tests; use a supported host Podman installation for OCI builds and OCI behavior tests.** Having Podman does not itself justify replacing Apptainer. This is an architectural recommendation based on their interfaces: Podman builds Dockerfiles/Containerfiles, while Apptainer converts and executes OCI images with HPC-oriented runtime behavior. [Podman build](https://docs.podman.io/en/stable/markdown/podman-build.1.html), [Apptainer OCI support](https://apptainer.org/docs/user/1.3/docker_and_oci.html)

For the first iteration, retain a native host terminal beside the container terminal. Both see the project at the same absolute path. Edit with workspace tools, then build/test using the site's runtime from that native terminal. This preserves the container design while giving container operations an uncomplicated starting point. A later client inside the workspace may control a same-user host Podman service after the gates below pass. Do not make nested engines a prerequisite for daily work.

Choosing Nix or Spack for workspace tools is a separate packaging decision. Neither supplies the host's missing kernel features, scheduler integration, storage configuration, or permission to run containers. Avoid embedding another runtime simply because that package manager makes it available.

## Runtime roles

| Workflow | First choice to evaluate | Reason and limit |
| --- | --- | --- |
| Enter the existing development SIF | Host Apptainer | Keeps the current delivery and mount model |
| Build a collaborator's Dockerfile | Host Podman | Native Dockerfile/Containerfile workflow; test required features |
| Reproduce ordinary OCI behavior | Host Podman | Avoid confusing image defects with SIF conversion differences |
| Test a delivered SIF under a batch allocation | Host Apptainer | Exercises the actual deployment runtime |
| Launch another container from workspace tools | Host Podman API client, conditionally | Host performs execution; socket, path, and allocation rules apply |
| Test truly nested runtime behavior | Explicit experiment | Separate compatibility target, not the default architecture |

Podman uses Buildah internally. Its `buildx build` compatibility alias does not promise every Docker Buildx feature. Apptainer 1.5 also documents Containerfile builds through a configured BuildKit service, but that cannot be assumed for the project's Apptainer 1.3.6 baseline. Thus Podman is a convenient builder, not the only possible builder. [Podman build semantics](https://docs.podman.io/en/stable/markdown/podman-build.1.html), [Apptainer 1.5 installation requirements](https://apptainer.org/docs/admin/1.5/installation.html)

## Rootless Podman: installed is not configured

Ordinary rootless Podman relies on user namespaces and subordinate UID/GID mappings. Upstream also documents a single-UID HPC mode using `ignore_chown_errors`; flattening ownership can break images, so this is a site-selected compatibility mode rather than a universal fallback. Storage, runtime, network helper, and cgroup support must match the installed release. [Podman rootless mode](https://docs.podman.io/en/stable/markdown/podman.1.html#rootless-mode)

Podman's rootless image/layer storage must use a supported filesystem. Upstream excludes NFS and several distributed filesystems and recommends moving `graphroot` to local storage when home is on NFS. **This limitation concerns container storage; it does not mean shared project files cannot be bind-mounted.** Keep disposable layers/build cache on approved node-local storage and persist finished archives in normal project storage. Account for local disk capacity and cleanup when an allocation ends. Do not share one active storage directory across nodes. [Rootless storage restrictions](https://docs.podman.io/en/stable/markdown/podman.1.html#note-unsupported-file-systems-in-rootless-mode)

Shared files and devices may rely on supplementary groups. Podman's `keep-groups` option requires `crun` and is currently documented as unavailable for remote commands. That is a concrete acceptance gate for a client-inside-workspace design, not a reason to assume it works everywhere. [Podman group handling](https://docs.podman.io/en/stable/markdown/podman-run.1.html#group-add-group-keep-groups)

## From inside the workspace: sibling containers or true nesting

**Host-service model:** a Podman client inside the development container connects to the user's Podman Unix socket on the host. The host service creates another container alongside the workspace, rather than installing its engine/storage inside the workspace. Podman documents container access through a mounted socket; SELinux labeling may require additional site-supported configuration. [Podman API service](https://docs.podman.io/en/stable/markdown/podman-system-service.1.html)

The API grants the full authority of its service account, including arbitrary execution as that user. It is not a limited build-only interface. Use only the intended same-user rootless service; keep the socket private and do not expose it to a container under test. A socket mount is an explicit grant of host authority to the trusted development environment. A broadly mounted development shell should not be treated as an isolation boundary for untrusted images. [Podman API security](https://docs.podman.io/en/stable/markdown/podman-system-service.1.html#security)

Volume source paths resolve on the service host. A path existing only inside the workspace is not a usable host bind source. Preserve matching project paths and verify the working directory and output ownership. Image-transport paths can also refer to the server; some CLI options are unavailable remotely. Test the actual build command rather than assuming local/remote parity. [Podman volumes](https://docs.podman.io/en/stable/markdown/podman-run.1.html#volume-v-source-volume-host-dir-container-dir-options), [Remote build transport behavior](https://docs.podman.io/en/stable/markdown/podman-build.1.html#from)

**Allocation placement matters:** a client running inside a compute job does not automatically put a separately running API service or its children inside that job. The service determines the execution node and process context. Slurm explicitly uses cgroups to constrain allocated CPUs, memory, and GPUs. As a design rule, require an allocation-scoped service with verified accounting and cleanup, or execute the native runtime directly within the job through the site-supported method. A persistent login-node socket must not silently become the compute execution endpoint. PBS needs its own local equivalent check. [Podman service model](https://docs.podman.io/en/stable/markdown/podman-system-service.1.html), [Slurm cgroups](https://slurm.schedmd.com/cgroups.html)

**True nesting:** Apptainer explicitly documents nested execution, including inherited `APPTAINER_BIND` settings, and its newer installation guide describes running inside other containers. It is not categorically impossible. However, runtime binaries alone do not provide the required namespace, mount, FUSE, and security-policy support. Inherited workspace mounts should be deliberately reviewed before a nested test. [Apptainer 1.3 nested binds](https://apptainer.org/docs/user/1.3/bind_paths_and_mounts.html), [Apptainer nested-runtime requirements](https://apptainer.org/docs/admin/1.5/installation.html#running-inside-docker)

Red Hat also documents nested Podman without full privileged mode, with explicit device and security settings. These examples establish feasibility, not compatibility with the clusters' configurations. This project should not require privileged nesting or changing site security policy to provide a consistent shell. [Red Hat nested Podman documentation](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_running-skopeo-buildah-and-podman-in-a-container)

## Transfer and image lifecycle

A registry is optional. On a supported build host, a possible offline path is:

```sh
podman build -t localhost/example:test .
podman save --format docker-archive -o example.tar localhost/example:test
apptainer build example.sif docker-archive:example.tar
```

Transfer the archive for `podman load`, or the finished SIF for Apptainer. Record the image/platform and checksum. Use an image archive from `save`, not a filesystem export, when preserving image metadata and layers is intended. Podman supports Docker and OCI archives; the explicit Docker archive above is documented by the Apptainer 1.3 baseline. [Podman save](https://docs.podman.io/en/stable/markdown/podman-save.1.html), [Podman load](https://docs.podman.io/en/stable/markdown/podman-load.1.html), [Apptainer archive conversion](https://apptainer.org/docs/user/1.3/docker_and_oci.html#containers-in-docker-archive-files)

Conversion is not behavioral equivalence. Normal Apptainer execution ignores Dockerfile `USER`, has different default mounts, and uses a read-only SIF filesystem. Test OCI behavior in Podman and deployment behavior in Apptainer when both matter. [Apptainer compatibility differences](https://apptainer.org/docs/user/1.3/docker_and_oci.html#differences-and-limitations-vs-docker)

Keep released workspace packages immutable; mount settings, history, editor data, projects, and caches separately. A writable overlay can support experiments, but it becomes additional versioned state that must be tracked or discarded. It should not silently turn each cluster's workspace into a different installation. Apptainer supports persistent overlays and temporary writable layers; filesystem support must still be checked. [Persistent overlays](https://apptainer.org/docs/user/1.3/persistent_overlays.html)

## Small first-iteration acceptance gates

These checks run locally on each target. Results and private configuration stay there.

| Gate | Evidence needed before adoption |
| --- | --- |
| Host runtime | A permitted rootless Podman build and run succeed; installed Apptainer runs the SIF |
| Files and identity | Workspace and test container can access the intended project; file owner/group and permissions remain correct |
| Storage | Graphroot/build scratch use approved filesystems with sufficient space; saved output survives cleanup |
| Interactive behavior | Terminal input, resize, Ctrl-C, exit codes, and child cleanup work |
| Offline transfer | Saved archive loads; converted SIF passes its own test without registry access |
| Compute allocation | Runtime children remain under expected allocation limits and end with the job |
| Optional API access | Same-user socket, client/server compatibility, paths, groups, and allocation placement all pass |

First prove the native host build/test path beside the development shell. Then evaluate the socket convenience layer. The result can guide whether a Podman-based workspace is worthwhile without discarding the working SIF or committing to a second engine before it solves a demonstrated problem.
