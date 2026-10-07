# Diagnose tool library errors

A workspace pane contains packaged tools and visible host commands. The workspace preserves the host's `LD_LIBRARY_PATH` for site modules and native compilers. If that path names a libc older than the packaged tools expect, a packaged tool can fail with `GLIBC_... not found`. If it names an incompatible Nix or module library before the host's own libraries, a native command can fail with a `GLIBC_PRIVATE` symbol error. These messages identify a library mismatch; the path and command selected on the affected node determine which side supplied the mismatched library.

From the repository checkout **inside the affected workspace tmux pane**, run:

```bash
./scripts/diagnose-tool-libraries
```

The script prints the workspace release, whether it is inside a container and tmux, the command kinds and executable paths for `bat` and `sha256sum`, the `LD_LIBRARY_PATH` entries, and the results with the inherited library path and with it cleared for one command. It does not print alias bodies, keys, or other credential values. Review and redact site or personal directory names before sharing its output. If the error occurred before entering the workspace, also note the exact command and whether it ran in the native login shell.

For an immediate `bat` read without changing the pane's environment:

```bash
(unset LD_LIBRARY_PATH LD_PRELOAD; bat README.md)
```

The parentheses confine the change to that command. Site applications that need module libraries should continue to run with their approved environment. Do not globally replace the system libc or bind a second `/lib64` tree over the workspace image.

Preview10 packages the underlying `bat` executable with its own Nix library search path and starts `fortls` through the hardened workspace Python. An offline fixture placed Debian's older libc first in `LD_LIBRARY_PATH`: preview9 failed with `GLIBC_2.38 not found`, and the candidate tools passed. A live site check remains necessary because the reported checksum command and its selected libraries have not yet been observed on that system.
