# Nested Apptainer execution: EINVAL investigation

2026-09-21. Public-source research only; no containers were changed or executed by this research agent.

## Subsequent local result

The implementation task subsequently verified that the SIF's `/usr/bin/true` and ELF interpreter hashes exactly match the working Docker image. A syscall trace showed Linux returning EINVAL from the actual `execve("/bin/true", ...)`; this rules out the Go NUL-string prevalidation hypothesis for this failure. With Docker's system-path restrictions relaxed for the extraction helper, Apptainer 1.3.6 successfully executed the same SIF using `--unsquash`. Relaxing those restrictions alone did not fix direct mounted-SIF execution. The failure is therefore isolated to the local mounted execution path, while its exact kernel/FUSE mechanism remains unconfirmed. The release's [validation record](../validation.md) records the final full-tool results and the scope of the workaround. The source investigation below is retained as background.

## Observations supplied by the implementation task

- A newly converted, plain gzip SIF containing the Ubuntu 24.04 workspace fails with `exec /bin/true failed: invalid argument` under both Apptainer 1.3.6 and 1.5.3.
- The corresponding Docker image passes its smoke and persistence checks offline as uid 501. The Apptainer fixture runs as its configured non-root `node` user, with `seccomp=unconfined` and `/dev/fuse` available.
- The actual VM/kernel is native x86_64, `6.12.76-linuxkit`; amd64 emulation is therefore not a useful hypothesis here.
- A user namespace probe succeeds. The first 1.3.6 `--unsquash` probe instead failed while mounting `/proc` for its extraction helper. A fixture with `systempaths=unconfined` is being tested separately.

These are local reports, not conclusions established by the sources below. No exact upstream issue matching the final EINVAL was found. Do not describe this as a confirmed FUSE bug or a confirmed incompatible SIF.

## Most useful source finding: EINVAL can precede execve

Apptainer 1.3.6 calls Go's `syscall.Exec(args[0], args, env)` and passes a remaining error through as the displayed `exec … failed` message. Its diagnostic examines the shell's architecture, and gives a different diagnostic for ENOENT. The observed string therefore does not identify a mount failure by itself. [Pinned Apptainer execution source, lines 624–655](https://github.com/apptainer/apptainer/blob/v1.3.6/internal/pkg/runtime/engine/apptainer/process_linux.go#L624)

Go's `Exec` converts both argument and environment strings before invoking Linux. `SlicePtrFromStrings` returns EINVAL immediately if a string contains an embedded NUL byte. An image environment script evaluated by Apptainer could therefore cause the same message without any `execve("/bin/true", …)` system call. This is a **falsifiable hypothesis**, not an observed cause. [Go argument conversion, lines 84–100](https://github.com/golang/go/blob/go1.22.7/src/syscall/exec_unix.go#L84), [Go Exec, lines 268 onward](https://github.com/golang/go/blob/go1.22.7/src/syscall/exec_unix.go#L268)

Highest-value probe, inside a disposable diagnostic fixture with `strace` available:

```sh
strace -ff -e trace=execve,execveat -s 128 \
  -o /tmp/apptainer-exec \
  apptainer --debug exec /input/dev.sif /bin/true
```

Inspect every child trace. If there is **no final attempt** to execute `/bin/true`, inspect generated arguments and image environment evaluation first. If the syscall itself returns EINVAL, investigate the executable, interpreter, filesystem, and kernel path. Do not use `strace -v` or dump the entire environment when credentials may be present.

For an environment comparison, test `--no-eval` as one change; then test a minimal outer environment and `--cleanenv` separately. Apptainer documents that image environment is retained despite `--cleanenv`, whereas `--no-eval` changes environment and OCI argument evaluation. Inspect the embedded environment scripts or `inspect --environment`; look for values that can evaluate to NUL rather than assuming the archive literally contains NUL. These are diagnostic settings, not a recommendation to change the MPI launch environment. [Environment handling and evaluation](https://apptainer.org/docs/user/1.3/environment_and_metadata.html), [Exec options](https://apptainer.org/docs/user/1.3/cli/apptainer_exec.html)

## Known nested FUSE issue: relevant comparison, different signature

Upstream issue #3504 reproduced a `squashfuse_ll` crash in unprivileged Docker. The mounted filesystem initially worked, then became inaccessible with `Transport endpoint is not connected`; the helper received SIGSEGV. The linked squashfuse investigation narrowed it to extended-attribute lookup. The maintainers report the fix in squashfuse 0.6.2, and Apptainer's 1.5.1 changelog records bundling that fix. [Apptainer #3504](https://github.com/apptainer/apptainer/issues/3504), [Squashfuse #148](https://github.com/vasi/squashfuse/issues/148), [Apptainer 1.5.3 changelog](https://github.com/apptainer/apptainer/blob/v1.5.3/CHANGELOG.md)

Thus, unchanged behavior under 1.5.3 weakens this particular explanation, assuming that fixture really selects its bundled helper. Confirm the chosen helper path in Apptainer debug output; capture its exit status. A helper crash or ENOTCONN would strengthen the connection. A live helper and plain EINVAL from the final launch would not.

## Falsifiable follow-up probes

| Probe | What it distinguishes |
| --- | --- |
| Complete `--unsquash` with the required helper mount permissions | Passing extracted execution with failing mounted execution implicates the mounted filesystem path. A failure before execution is inconclusive. |
| Read `apptainer sif list`, dump the **observed** SquashFS descriptor ID with `sif dump`, and extract with standalone `unsquashfs` | Separates payload extraction/integrity from the Apptainer extraction helper. Do not assume the descriptor ID is always 4. |
| Compare hashes and `readelf -h -l` output for extracted `/usr/bin/true` and its declared ELF interpreter against the working Docker image | Establishes whether conversion changed executable bytes or interpreter resolution. Linux ELF loading has several EINVAL branches; the error alone does not establish which one. |
| Execute that extracted root directory with Apptainer as a sandbox | If it fails identically, SquashFS mounting is unnecessary to reproduce the failure. If it works, compare FUSE and overlay behavior. |
| Repeat using the same SIF copied into Docker-local storage instead of a macOS shared bind | Separates host file-sharing behavior from image content while preserving the SIF bytes. Check hashes before and after. |
| If syscall tracing shows actual `execve` EINVAL, invoke the image's verified ELF loader directly with `/bin/true` as its argument | Distinguishes the direct executable/interpreter load path. This should be a diagnostic command only. |

The dump/extract technique is recommended by an upstream maintainer in the squashfuse investigation. Linux's ELF loader can return EINVAL for invalid mapping/layout conditions; this supports checking exact bytes rather than inferring corruption. [Maintainer's extraction guidance](https://github.com/vasi/squashfuse/issues/148#issuecomment-4513035226), [Linux 6.12 ELF loader](https://github.com/torvalds/linux/blob/v6.12/fs/binfmt_elf.c)

Upstream documents `systempaths=unconfined` for nested Apptainer operations involving PID/proc containment. Therefore the reported `/proc` denial in the extraction helper is a separate permissions observation, not evidence against the contents of the SIF. Adding only that option to the disposable fixture is a targeted test; broad privileged mode would obscure which permission mattered. [Official nested-Docker guidance](https://apptainer.org/docs/admin/1.5/installation.html#running-inside-docker)

The immediate next decision should follow the final-exec trace and the completed extracted-directory test. Until one succeeds, local SIF runtime compatibility remains unverified even though Docker execution and SIF conversion succeeded.
