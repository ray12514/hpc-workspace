# Workspace validation

## Managed tmux selection: 0.7.2-preview1 source checks

Date: **2026-09-25**. The shipped 0.7.1 wrapper reproduced a wrong-server failure inside a managed pane: it supplied its release-default socket even though `TMUX` identified the active project server. The underlying tmux binary reached the correct server in the same pane. The wrapper now preserves that implicit selection while keeping explicit `-L` and `-S` overrides.

- The new regression fails with the original wrapper and passes with the fix. It runs a managed server alongside a separate default server, checks implicit and explicit clients, invokes the actual layout-save helper from a managed pane, and checks that the snapshot contains the project's three windows without the decoy session. The save binding must also initialize on the managed server.
- The session lookup also works inside the workspace. The general host-command guard initially rejected it; a focused regression demonstrates that rejection and passes once this read-only action is allowed. The lookup requires no image/runtime selection and does not create state.
- The existing real tmux/editor interaction suite passes. The Linux unit suite runs **88 tests: 85 pass and 3 skip** because the fixture lacks wget and the importable YAML parser. Host modules parse with Python 3.6 syntax rules; focused Ruff, documentation links, and code fences pass.

Final SIF, installation, and publication results will be recorded after artifact validation. Tool versions and the Nix lock remain unchanged. No private cluster or credential is involved in these checks.

## Session locations and connection guides: repository update

Date: **2026-09-25**. This source update adds `bin/ws sessions`, readable node/project/release records for managed thin sessions, a Windows/VS Code connection guide, and a restricted native Codex configuration outline. It does **not** publish a replacement for 0.7.1-preview1 or extend its gateway form.

- The Linux source suite runs **87 tests: 84 pass and 3 skip** (the fixture lacks wget and the importable YAML parser). Eight focused session tests cover another node with a colliding PID, local ready/starting/ended keepers, a changed boot identity, older metadata, malformed/missing records, private record creation and keeper reuse, safe display, and a lookup that needs no runtime/image and writes no state. Those eight also pass on macOS.
- Host modules parse with Python 3.6 syntax rules. Changed Python files pass focused Ruff checks. JSON examples, local documentation links, and code fences validate.
- The shipped **Codex 0.155.1** parses the example TOML in a disposable home with networking disabled. Its feature listing confirms both historical WebSocket flags are marked removed. This proves parsing, not private gateway connectivity or enforcement of every field; the active provider mapping is checked against official OpenAI documentation.

No Windows client, Kerberos kit, target cluster, real gateway, private configuration, or credential was accessed. The VS Code profiles/tasks are documented setup examples, not an end-to-end Windows acceptance result. No new SIF was built. Existing 0.7.1 records can be inspected with the updated repository launcher; remote records are explicitly unverified.

## Configuration form contrast: 0.7.1-preview1

Date: **2026-09-25**. A real PTY running the shipped Gum **2.0.1** reproduced fixed dark-gray labels on black: the heading's palette color 240 has a 2.95:1 contrast ratio against black. The form now inherits the terminal's normal text/background colors. Color suppression is local to the Gum child process, including inherited forced-color settings.

- The original reproduction passes after the fix. The regression fails on the previous form and passes with xterm, xterm-256color, screen-256color, and tmux-256color, including truecolor advertisement and conflicting inherited Gum/forced-color settings. Headings, help, placeholders, choices, saved values, and typed text emit no fixed colors or dim/concealed text. The parent environment is unchanged.
- Real form checks also pass selection, a masked synthetic credential longer than 400 characters, cancellation without writing files, and a complete basic-prompt configuration edit. These tests use disposable homes and no external network access.
- The actual **729,800,704-byte** SIF passes those focused form checks as a non-root user through Apptainer **1.3.6 and 1.5.3**, using `--unsquash` in the local Docker fixtures. SHA-256: `712700b60a6bd4421152f389b537f70439af1cd3f29e0be5f0ec0a04f8e33d39`.
- The patch layer reuses the verified 0.7.0 tool image. All **198** shipped source/configuration/skill assets and the Nix lock match source commit `ca6afdc96619d9fabdc8a50be1eedecd139e85ee`. The source archive, matching installer, and image match their manifest sizes/checksums. Focused Ruff, ShellCheck, Python syntax, documentation-link, and code-fence checks pass. The broader unchanged toolkit/installer suites were not rerun for this display-only patch.
- All eight published assets match the tested filenames, sizes, and GitHub-recorded SHA-256 digests. The publicly downloaded manifest matches the local bundle, with SHA-256 `38f55e30e51db79b616d571f8905e1071c51da3f421e17553f33e5baf1c553ee`. The repository recommendation now selects this release for `./setup`.

No actual PuTTY client, VS Code terminal, cluster, or real credential was accessed. Inheriting terminal colors preserves the contrast of ordinary terminal text; it cannot repair an unreadable foreground/background pair selected in the terminal itself. The prior tool/runtime validation is recorded under 0.7.0 below.

## Configuration forms and runtime setup: 0.7.0-preview1

Date: **2026-09-25**. The source adds Gum forms, named Codex/Claude gateways, private credential updates, and remembered native Apptainer setup. The Nix lock is unchanged; Gum **2.0.1** and TOMLKit **0.15.0** are added from that pinned package set. The packaged agents remain Codex **0.155.1** and Claude Code **2.1.280**.

- **Source:** 79 Linux unit tests run successfully; the wget fallback test is skipped because this fixture provides curl only. Coverage includes private backups, symlink preservation, duplicate-key rejection, concurrent edits, rollback after a partial write, separate gateways, key rotation, missing credentials, endpoint/credential binding, workspace-field preservation, and saved runtime/module invocation. All host modules parse using Python 3.6 syntax rules; an actual Python 3.6 interpreter was not exercised. Focused Ruff checks, ShellCheck for changed shell scripts, documentation links, and code fences pass.
- **Real terminal and agents:** the offline, read-only Linux fixture drives Gum selection, masked input longer than 400 characters, cancellation, and a complete plain-prompt edit. Actual packaged Codex and Claude Code processes send requests to a loopback-only synthetic gateway using separate selected keys; inherited conflicting keys and Claude routing settings are not used. The fixture returns a synthetic authentication error, so this verifies request routing and header selection, not a successful model response or a real gateway's compatibility. Stored-key rotation leaves the other profile unchanged.
- **Existing environment:** packaged tool/agent startup, locale preservation, offline help, YAML/CSV/log tools, job-environment cleanup, and the editor integration suite pass with an intentionally incompatible host SSL library present.

- **Final SIF:** the complete integrated suite passes as a non-root user under Apptainer **1.3.6 and 1.5.3**, using `--unsquash` in the local Docker fixtures. Both exercise the actual forms and synthetic gateway requests, native client/library behavior, editor, locale fallback, tmux input/exit/reconnect, and optional Inspector import.
- **Image provenance:** the release stage was applied to the already validated tool image after the builder exhausted its temporary storage. Its tool closure uses the same pinned Nix inputs. All **198** shipped source/configuration/skill assets and the Nix lock match source commit `d69c3bcaf5e0ce3daf8bf09e58cd905e2032cf0c`; the image labels and release manifest identify that commit. The SIF is **729,800,704 bytes** (696.0 MiB), with SHA-256 `60720dfa52d3fcbbab2b01044d932c862f65120df9f4ca3ea698a448b1b6ce4e`.

- **Transfer bundle:** the actual standalone installer discovers and saves its working runtime. A fresh environment with no Apptainer on PATH enters the SIF using that saved executable. Installation from a skills-only home, reinstallation, ordinary Bash login/terminal startup, an update inside the workspace, and custom site-loaded startup files all pass. Skills and personal configuration survive both installation flows.
- **Publication:** all eight uploaded release assets match their tested local filenames, sizes, and SHA-256 hashes. The published manifest's SHA-256 is `3573da5b0784b899fa9450bc0294207feafbbb0a3feebbe5dce9cdc2522f7a36`; `./setup` now selects this release through `releases/recommended.json`.

No target cluster, real gateway, real credential, PuTTY client, or live scheduler job was accessed. Cloud federation, enterprise saved gateway login, managed routing, child/background agent sessions, and generic YAML schemas are outside this first adapter's verified scope. Normal mounted-SIF execution remains a site-local check.

## Guide refresh and practice workflow (0.6.1)

Date: **2026-09-24**. The user guides now follow the repository's `./setup` workflow and the 0.6.1 thin environment. Earlier core-image instructions are retained in a clearly marked archive. The practice project contains synthetic files only.

- A non-root, read-only Linux toolkit fixture with networking disabled passes the practice project's checks and run, file/content searches, data queries, log/storage commands, host-Python virtual environment, direnv example, and small benchmark. It uses the packaged tools and current shared configuration; this documentation change does not rebuild the SIF.
- The exact `fedit` function from the guide preserves filenames containing spaces and newlines and does nothing on cancellation. Real packaged Neovim opens those filenames. The `find` and `rg` pipelines also preserve NUL-delimited filenames through fzf.
- The shipped Bash Ctrl-R binding, navigation helpers, Neovim picker mappings, and editor session command are present. Documentation links, heading targets, code fences, and example JSON are checked locally; the practice scripts also pass ShellCheck, shfmt, and Ruff checks inside the fixture.

No real scheduler job, AI API request, target cluster, or PuTTY client was exercised for this documentation update. Remembered Apptainer setup and terminal configuration forms are proposed designs, not features added by these checks.

## One-command release setup

Date: **2026-09-24**. The repository now provides `./setup` to download, verify, and install the recommended release without an existing `ws`. This host-side addition delivers the unchanged, published **0.6.1-preview1** image and matching installer.

- The Linux unit suite passes **65 tests**, with one wget-only test skipped because that fixture lacks wget. The focused macOS run passes six bootstrap tests, including real wget download/resume; two Linux installer tests skip there. Both curl and wget are exercised against a synthetic local HTTP server.
- Bootstrap tests cover complete download, reuse without network access, resumed partial transfers, integrity failure before installer execution, invalid manifest records, unsupported hosts, installation from a skills-only home, repeat installation, and a synthetic 0.5-to-0.6.1 upgrade retaining a custom prefix/startup file and rollback.
- The actual `./setup --download-only` fetches the published manifest, source archive, and installer from GitHub and verifies them against the repo's recommendation. It reuses and verifies the previously downloaded production SIF.
- The actual command installs that exact bundle into a disposable Linux home with networking disabled. A fresh Bash finds the installed `ws` and its update command; personal shell settings and existing skills remain intact. Host bootstrap sources parse with Python 3.6 syntax rules; an actual Python 3.6 interpreter was not exercised.

No image rebuild or cluster access was needed for this change. The image/runtime acceptance results remain those recorded below.

## Tmux exit and installer recovery: 0.6.1-preview1

Date: **2026-09-24**. Tool versions and the Nix lock are unchanged from 0.6.0. The production change disables `remain-on-exit` in the shared tmux defaults; personal overrides continue to load last.

- A real terminal driving packaged tmux reproduced the old behavior: Ctrl-D exited Bash, left `pane_dead=1`, and kept the client attached. With the default changed, Ctrl-C leaves a usable shell, Ctrl-D and `exit` remove finished panes, another pane remains usable, and closing the final pane returns the attached client. The regression waits for an empty Bash prompt before sending EOF.
- All **58 Linux unit tests** pass. The nine installer unit tests also pass on macOS, changed Python test files parse, and the maintained build/test shell scripts pass ShellCheck.
- The exact SIF passes the complete integrated suite through Apptainer **1.3.6 and 1.5.3**, using extracted-SIF execution (`--unsquash`). Both pass direct terminal exit, native command/module/file access, tool and agent startup, locale handling, editor integration, tmux input/reconnect, and optional Inspector import. The managed-session check closes all three windows normally and verifies that the host keeper stops, instead of depending on forced server cleanup.
- The exact transfer bundle installs into a disposable Linux home containing an existing workspace skills directory but no runtime. It creates `runtime/bin/ws` and `runtime/activate.sh`, preserves the skill file and personal dotfiles, and makes `ws` available in fresh Bash login and terminal shells. Reinstallation and an update from inside the image pass. The separate custom-startup-file flow also passes, retaining its chosen files and leaving ordinary startup files unchanged.

The SIF is **724,914,176 bytes** (about **691.3 MiB**), built from source commit `4639c1c67d600a85f39160f4056c7b2cd3eb1e19`. SHA256: `4ea1af9efb54e79ce0c1c757970aae6587d1a20e54bdea63deb4684036066e50`. All eight uploaded transfer assets match their local sizes and SHA256 hashes.

These checks reproduce and fix the retained-dead-pane behavior locally; no target cluster or PuTTY client was accessed. The cause of the user's earlier missing runtime installation is not established. The tested standalone installation provides a repair path without requiring an existing launcher. Normal mounted-SIF execution, real scheduler authentication, AI API requests, and MPI/GPU workloads remain site-local acceptance work.

## Expanded toolkit and editor: 0.6.0-preview1

Date: **2026-09-24**. The Nixpkgs revision remains `8825bebf6324e0579d012936eff73379af284b6d`; the expanded tool set, plugin dependencies, selected parser/query pairs, and offline help pages are built together. `ws tools --json` reports the exact installed CLI versions. The image includes Codex **0.155.1**, Claude Code **2.1.280**, Neovim **0.12.5**, and tmux **3.7c**.

Source and runtime checks completed before packaging:

- All **58 Linux unit tests pass**. On macOS, 52 pass and six environment-specific checks skip. Changed shell scripts pass ShellCheck, and host Python modules parse with Python 3.6 syntax rules; an actual Python 3.6 interpreter was not tested.
- Non-root, read-only runtime fixtures with networking disabled start every packaged CLI and both AI clients. A deliberately incompatible `libssl.so.3` remains on the inherited library path. The tools keep their own libraries, while a native child receives the original module/library settings. This is a targeted collision check, not a guarantee for arbitrary preload libraries or every library-loading path.
- The previous SIF reproduced the missing `en_US.UTF-8` locale warning. The new matching archive is available before process initialization, and the expanded fixture preserves that valid locale without a Bash warning. Normalization is limited to actual locale categories; terminal metadata such as `LC_TERMINAL` remains unchanged.
- All 13 selected Treesitter parsers and highlight queries load. Real Python diagnostics/completion, Bash and Fortran document symbols, manual Ruff formatting, external-edit reload, and preservation of unsaved editor changes pass. Personal Neovim configuration loads last.
- Actual tmux input opens and quits Superfile, lazygit, and btop without private-use font glyphs; Neovim's file picker selects a file and its navigation reaches an adjacent tmux pane. Ctrl-R retrieves/reruns a history entry and Ctrl-C interrupts a command. The native job-environment check also runs from a tmux pane.
- Offline tldr pages, YAML/CSV tools, and log reading pass. No compiler, Python, or Node command is introduced ahead of the host's commands; editor/agent helpers use private runtimes.

The log viewer needs its indirect curl/OpenSSL dependency path scoped to its own loader. Its wrapper uses the loader's `--library-path` option without rewriting `LD_LIBRARY_PATH` for native children. Broadening every executable's RPATH caused a reproducible Go-tool startup regression during development; that change was removed, and real startup checks now run before image export. [Dynamic-loader options](https://man7.org/linux/man-pages/man8/ld.so.8.html)

The final SIF passes the complete integrated suite with real Apptainer **1.3.6 and 1.5.3**, using extracted-SIF execution (`--unsquash`) because of the Docker Desktop mount limitation described below. Both versions pass native command/module/file access, tool and agent startup, locale preservation and unavailable-locale fallback, editor integration, tmux input/reconnect/cleanup, stale login-node marker handling, and optional Inspector import. These larger-image fixtures use disposable disk-backed temporary storage rather than a RAM filesystem.

The exact transfer bundle also passes installation, repeated installation, fresh Bash login and terminal startup, and an update from inside the workspace. A separate custom-startup-file fixture confirms that updates remember the chosen site-loaded files and leave the ordinary startup files unchanged. Personal configuration survives both flows.

The SIF is **724,914,176 bytes** (about **691.3 MiB**), built from source commit `d473768818d0a2e8022b2cf914bcd3ffe9731849`. SHA256: `9a755f50601e7b1fb4dbed9869ecb7848c293f41e7b553983815b3fa7dc4739e`. All eight uploaded transfer assets match their local sizes and SHA256 hashes. The release manifest records the matching SIF, source commit, image identity, and checksums.

No real AI authentication/API request, scheduler submission, cluster mount, MPI/GPU workload, or nested container-engine test was performed. Login-node and compute-node API access and all site results remain local acceptance work.

## Bash startup and local startup preferences: 0.5.1-preview1

The tool versions and Nix lock are unchanged. This release adds ordinary Bash/login-profile setup, `--shell-startup FILE` for site-loaded files, and private persistence of that choice across updates. The installer, host launcher and in-container updater ship together.

- All **55 Linux unit tests pass**. Nine focused installer tests also pass on macOS. Checks cover actual Bash login and terminal startup, active-profile precedence, personal content and symlink/mode preservation, repeated setup, invalid blocks, custom files, remembered opt-out/custom choices, and existing install/update/rollback behavior.
- The exact transfer bundle installs and reinstalls in a disposable Linux home. Fresh Bash login and terminal shells find `ws` without manually sourcing `activate.sh`. Entry and an update from inside the workspace retain personal settings and working startup.
- A separate synthetic site home loads custom files through its own startup scripts. The repeated `--shell-startup` option selects those files, an in-container update reuses the saved choice, and fresh shells still find `ws`. The site's ordinary startup files remain byte-for-byte unchanged.
- The final SIF passes the integrated command/module/editor/tmux/Inspector regression suites on Debian with Apptainer **1.3.6** and Ubuntu with **1.5.3**, using the same extracted-SIF fixtures described below.

The SIF is **141,090,816 bytes** (about **134.6 MiB**), built from commit `1e58b6ab522a3b35d28ddd154d28e9dbe5f77096`. SHA256: `4a57a1cd7cbcfd35988f165fd9ff5d127b222d5203ee6292446d673aea4b1c07`. No target cluster or actual site startup profile was accessed. Normal cluster SIF mounts, real site authentication, MPI/GPU workloads and nested container engines remain local acceptance work.

## Integrated thin environment: 0.5.0-preview1

The first thin implementation uses Nixpkgs commit `8825bebf6324e0579d012936eff73379af284b6d`, with its content hash in `image/nix/flake.lock`. It contains Bash 5.3p15, Neovim 0.12.5, tmux 3.7c, bat 0.26.1, fzf 0.74.4, fd 10.5.0, ripgrep 15.2.0, jq 1.8.2, eza 0.23.5, zoxide 0.10.0 and less 704. Its prepared runtime closure is copied into the image; no package manager runs at shell startup.

Local validation uses synthetic data only:

- All 49 host unit tests pass on Linux; macOS passes the 45 applicable tests and skips four Linux-only peer-credential checks. Tests cover old launcher behavior, mount planning, private temporary snapshots, archive traversal rejection, checksum failure preservation, repeated installation, updates, rollback and personal shell-hook preservation.
- The image's tools and editor run with networking disabled and the image read-only.
- Real Apptainer tests exercise the same SIF on a Debian 12 userspace with Apptainer 1.3.6 and on Ubuntu 24.04 with Apptainer 1.5.3. The Debian 1.5.3 fixture also established the initial command/editor/session behavior. These use extracted-SIF execution (`--unsquash`) because direct nested SIF mounting is unavailable in the local Docker Desktop environment.
- From the integrated shell, synthetic native PBS/Slurm clients receive literal arguments, keep native exit codes, and see the shared project and caller UID. Exported module functions and module variables survive entry. Neovim invokes a native helper with the same project/module environment and loads personal overrides.
- A deliberately invalid `libssl.so.3` on the module library path does not replace bat's private dependencies. Native editor subprocesses still receive that original library path. This is a targeted collision test, not a guarantee for arbitrary preload libraries or every package.
- Packaged tmux starts without a host tmux dependency. Both windows accept keyboard input, Ctrl-R retrieves and reruns a historical command, Ctrl-C interrupts a command, and a second launcher invocation reconnects to the same session. The test checks that packaged executables still resolve after detachment.
- The optional existing Inspector YAML import works through the thin image.
- The exact transfer bundle installs and reinstalls in a disposable Linux home. Its generated launcher enters the SIF without `--site` or `--image`, retains personal Bash/Neovim settings, and completes `ws update` from inside the integrated shell. The managed PATH block remains unique and the original `.bashrc` content is retained.

The final SIF is **141,090,816 bytes** (about **134.6 MiB**), built from source commit `6b2f9084f7f78ab06d18369d148a4a023c596042`. Its SHA256 is `a72ca4ff21fee7d42881623654b402874f9c28cf9b93656de6aaf7f573666cc8`. The final artifact passes both Apptainer fixture suites described above, including keeper shutdown after tmux exits. The release manifest records the matching source, image identity and file checksums.

The session regression found during implementation was specific and reproducible: letting the container command return after starting detached tmux caused `--unsquash` cleanup to remove the tool files. A host keeper now holds the runtime open for the life of the packaged tmux server. The regression test checks executable resolution and actual Ctrl-R input after detachment; a live shell process alone is insufficient evidence.

No Ruth, Jean or Blueback node was accessed. Normal SIF mounting, real scheduler authentication, site module variants, MPI/fabric behavior, GPU workloads, and nested Podman/Apptainer operations remain local acceptance work. The earlier reported tmux freeze and bat SSL error have not been reproduced from cluster evidence; this release does not claim to identify their causes.


## Explicit dotfiles: 0.4.0-preview1

Date: **2026-09-22**. Built locally for Linux amd64. Core tool versions and package pins are unchanged. No cluster access, private configuration, AI authentication, or live scheduler submission was used.

- **Automated checks:** all **42 tests pass in Linux** with a read-only root, no network, and no capabilities. The macOS host passes 38 and skips four Linux peer-credential tests. The added checks cover preservation of edited files and dangling symlinks, private file permissions, and complete-file publication during simultaneous first entries.
- **Real applications:** non-root Docker runs use a read-only image and replace the container between phases. Personal Bash, Readline, Neovim, bat, and Git preferences survive, application configuration is writable, normal host Bash/Neovim files are not sourced, and Git still reads the user's normal identity configuration. Real tmux loads the personal override and preserves its existing layout save/restore behavior.
- **Interactive shell:** an actual non-root Bash PTY opens fzf with Ctrl-R, selects a synthetic history command without executing it, and completes `git chec` to `git checkout` with Tab. Existing prompt/color fallbacks and Neovim theme checks pass. Ctrl-T and Alt-C are provided by the same packaged binding script; their full picker interactions are not separately automated.
- **Source consistency:** all 27 shipped configuration, launcher, helper, and generic profile files match this checkout byte-for-byte. Maintained shell scripts pass ShellCheck. All seven host Python files parse with Python 3.6 syntax rules; an actual Python 3.6 interpreter was not tested.
- **Delivered SIF:** real Apptainer **1.3.6 and 1.5.3** runs pass as UID 1000 in `--unsquash` mode. Both verify writable application configuration and a retained personal Neovim preference after re-entry. The full launcher flow also checks an alternate host home: container `HOME` matches the explicit bind, and dotfiles are created there. Existing tool checks, synthetic PBS/Slurm host connections, and Inspector import/save/refresh checks pass under both versions.

The SIF is **628,187,136 bytes** (about **599.1 MiB**), unencrypted, with gzip SquashFS. These are local extracted-SIF checks. Normal SIF mounting and actual site scheduler, GPU, and MPI behavior remain local validation work; the Docker Desktop nested-mount limitation recorded below still applies.

## Optional Inspector configuration: 0.3.0-preview1

Date: **2026-09-22**. Built locally for Linux amd64. The image adds Ubuntu snapshot package `python3-yaml` **6.0.1-2build2** for the import helper; the existing core tools retain their pins. No cluster connection, real cluster profile, AI authentication, or live scheduler submission was used.

- **Automated checks:** all **40 tests pass in Linux** with a read-only root, no network, and no capabilities. The macOS host passes 36 tests and skips four Linux peer-credential tests. The 16 new checks cover initial import, optional/missing facts, PBS/Slurm defaults, explicit overrides, first-entry image/state preservation, cached startup without the source YAML or Inspector, concurrent edits, explicit refresh, and invalid/renamed-profile rejection.
- **YAML handling:** actual YAML parsing checks typed provider paths, modules, and node facts. Unsafe tags, duplicate keys, recursive aliases, malformed input, and unsupported versions are rejected. Imports snapshot the source, use the image's parser, and write private configuration atomically. Host launcher syntax was also checked against Python 3.6.
- **Delivered SIF:** real nested Apptainer **1.3.6 and 1.5.3** runs pass in `--unsquash` mode. Each tests initial import and preview through the SIF's reader, image selection, entry after deleting the original YAML, saved PBS/Slurm defaults, successful refresh, and preservation after a failed refresh. Existing SIF tool checks and actual container-to-host connections to synthetic PBS/Slurm clients also pass.
- **Existing daily environment:** the Docker checks pass tool/C/Python smoke tests, preservation of files/history/editor state/custom skills after replacing the container, tmux save/restore, Bash PTY colors/literal names, and Neovim theme modes. Submission export behavior is unchanged.
- **Source consistency:** the seven delivered launcher/library/entry files match the source byte-for-byte. Maintained shell scripts pass ShellCheck. The public documentation cites the public profile schema; the private implementation review and all build logs remain outside the release.

The SIF is **628,166,656 bytes** (about **599.1 MiB**), unencrypted, with gzip SquashFS. These are local extracted-SIF checks, not a claim that direct SIF mounting, scheduler authentication, GPU toolkits, or MPI communication have been validated on the target clusters. The previously recorded Docker Desktop nested-mount limitation still applies. Site checks remain local to those machines.

## Daily workflow: 0.2.0-preview1

Date: **2026-09-22**. Built locally for Linux amd64. Core tool versions and package pins are unchanged from the baseline table below. No cluster connection, private cluster files, AI authentication, or live job submission was used.

- **Launcher/scheduler:** all 24 tests pass in the Linux image as an ordinary user with a read-only root, no network, and no capabilities. The macOS host passes the 20 applicable tests; four Linux peer-credential tests are skipped there. Native-client fixtures cover PBS and Slurm, literal paths and arguments, working directory, selected host environment, explicit job variables, native job IDs/errors, dry-run behavior, and container fallback rejection.
- **Local submission connection:** Linux tests exercise actual Unix sockets and peer credentials, private directory/socket permissions, the container CLI, wrong-site/operation rejection, symlink escape rejection, malformed requests, four-request capacity, immediate busy errors, and cleanup. These tests use synthetic scheduler executables, not PBS/Slurm servers.
- **Terminal appearance:** real Bash PTYs pass 256-color, true-color, `NO_COLOR`, `WS_COLOR=never`, and `TERM=dumb` cases, including site/node/job labels and nonzero exit status. Path and branch names containing shell syntax render literally without executing it. Headless Neovim verifies the theme's 256-color highlights, true-color setting, and opt-out.
- **Existing behavior:** offline tool/C/Python smoke checks, replacement of the container with persistent files/history/editor state, preservation of independent skills, and real tmux save/restore all pass. Tmux restores shells; process replay remains disabled.
- **Build consistency:** the 12 delivered launcher, profile, theme, and entry files have the same SHA256 hashes as their source files. Maintained shell scripts pass ShellCheck. Host Python modules parse with Python 3.6 syntax rules; an actual Python 3.6 interpreter was not tested.
- **SIF:** the new gzip SquashFS SIF passes real tool smoke checks under **Apptainer 1.3.6 and 1.5.3**, using `--unsquash` as UID 1000. Under each version, inner-container `ws submit` and `ws jobs` reach synthetic PBS and Slurm clients on the outer host through the bound Unix socket. Tests verify script paths containing spaces and shell syntax, working directory, host environment selection, explicit input values, native failure status/stderr, and socket cleanup. The native scheduler clients are absent from the image PATH. There is no network access in these fixtures.

The fixtures establish the portable implementation, not a site's scheduler authentication, account/queue settings, client plugin dependencies, or production filesystem policy. The optional connection requires a permitted bind-mounted Unix socket and Linux peer credentials on the login host. Site-only client settings can be added to a local profile. Keep all actual cluster validation results local.

The first image was reported by the user to start on a target system. No detailed site report was requested or transmitted, and that report does not validate this update. The Docker Desktop direct nested SIF-mount limitation described below remains applicable; extraction tests do not establish native SIF mounting on each target. GPU stacks, MPI, interconnects, and distributed runtime validation remain outside this phase.

## Baseline: 0.1.0-preview1

Release: **0.1.0-preview1**, core, Linux amd64. Date: **2026-09-21**.

The workspace was built and exercised locally using Docker Desktop's native x86_64 Linux engine (`6.12.76-linuxkit`). No cluster was contacted, and no non-public cluster inventory, files, or credentials were used. Ruth/Jean/Blueback execution, GPU toolkits, MPI, interconnects, and live scheduler queries remain site-local validation work.

### Delivered image

| Component | Observed version |
| --- | --- |
| Ubuntu userspace | 24.04.5 LTS |
| glibc | 2.39 |
| Neovim | 0.12.5 |
| tmux | 3.4 |
| Node | 24.21.0 |
| Python | 3.12.3 |
| GCC | 13.3.0 |
| Codex | 0.155.1 |
| Claude Code | 2.1.278 |

Base-image digests, npm lock entries, and checked upstream assets are in `image/`. The installed Debian-package list, npm dependency tree, Node version, and asset lock are also stored inside the image under `/opt/workspace/manifests` and exported with the release.

### Passing checks

- **Host launcher:** 10 automated tests covering literal command arguments and paths containing spaces; dry-run without state writes or secret values; scheduler-specific allocation requirements; GPU-mask forwarding; isolation from inherited Apptainer injection variables; PBS/Slurm command selection; checksum-verified selection/update/rollback; detection of replaced images; compute-node session rejection; and protected bind destinations.
- **Offline Docker execution:** real core tools run with UID/GID 501:20, a read-only image, no network, all capabilities dropped, and no-new-privileges. Neovim configuration loads, both AI clients report their pinned versions, Python creates and uses a virtual environment, and GCC compiles and executes a C program from writable state. No AI authentication or API request is performed.
- **Replacement/persistence:** a second container reuses the same disposable home/project/state. Project contents, shell history, a two-window Neovim layout, installed skills, and an existing custom skill survive. The custom skill is preserved rather than replaced.
- **Tmux recovery:** the actual configured tmux server saves its windows; a new server restores them. Restored panes run shells, with process replay disabled. Snapshot paths and detach-save hooks are configured, and each workspace gets its own server/state location.
- **SIF conversion:** a standard, unencrypted, gzip SquashFS SIF is built from the Docker archive by pinned Apptainer 1.5.3. Conversion succeeds in an ordinary Docker container with no network, no privileged mode, and no Docker socket.
- **SIF execution after extraction:** the same SIF runs the real tool, Python-venv, skill, and C compilation smoke checks under both **Apptainer 1.3.6 and 1.5.3**, as UID/GID 1000:1000. The local fixture uses `--unsquash`, disposable writable binds, no network, and Docker namespace/extraction permissions.
- **Static checks:** ShellCheck for maintained shell scripts and Python compilation checks. Vendored skill/plugin files retain upstream contents.

### Exact limit of the runtime result

Direct execution from a nested SIF/FUSE mount failed under both runtimes on this Docker Desktop VM: Linux returned `EINVAL` from `execve("/bin/true", ...)`. The image had mounted and reached its final program launch. Relaxing Docker system-path restrictions alone did not change that result.

The extracted SIF passed. External extraction also showed that `/usr/bin/true` and its ELF interpreter have identical SHA256 hashes in the SIF and the working Docker image. A syscall trace ruled out Go rejecting a malformed argument/environment before execution. The failure is isolated to the local mounted-execution path; the exact kernel/FUSE mechanism is not established.

Accordingly, the release demonstrates working core image contents and Apptainer execution **through extraction**, not successful native SIF mounting on the target clusters. The host `ws` launcher keeps normal SIF execution as its default. Check that normal path locally on each cluster before adopting the release there. Nothing in this result establishes GPU-driver, MPI ABI, fabric, or scheduler integration.

`scripts/test-sif` defaults to the passing extraction fixture. `WS_SIF_TEST_MODE=mount ./scripts/test-sif` reproduces the direct-mount check on a suitable Linux Docker host. Local test permissions (`seccomp=unconfined`, `systempaths=unconfined`, and FUSE when testing mount mode) belong to these disposable Docker fixtures; they are not deployment instructions for HPCMP.

See the [focused investigation](research/nested-runtime-check.md) for primary-source references. Full local build/test logs are retained under ignored `build/`; release artifacts and checksums are under ignored `dist/`. The portable source bundle contains this result and the test scripts.
