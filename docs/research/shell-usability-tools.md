# Shell usability tools for PuTTY and VS Code

Reviewed 2026-09-22. This is a proposed shortlist, not an installation or release record. Sources are upstream documentation, public source code, and a local image audit; no cluster data was used. Proposed additions still need testing against the versions selected for the image.

## Audited image: 0.3.0-preview1

**Follow-up:** release 0.4.0-preview1 repairs the fzf key bindings and enhanced Tab completion described below and adds explicit [dotfile configuration](../dotfiles.md). The following audit remains a record of the earlier image. The additional tools remain proposed.

The local `hpc-workspace:0.3.0-preview1` image was inspected in a disposable Docker container with a read-only filesystem and networking disabled. This confirms the built image's behavior, rather than only the intended package list in the [Dockerfile](../../image/Dockerfile).

| Item | Observed result |
| --- | --- |
| Existing executables | `fzf`, `rg`, `fd`, `bat`, `jq`, `htop`, `tmux`, and `nvim` present |
| fzf | `0.44.1 (debian)`; Ubuntu package `0.44.1-1ubuntu0.3` |
| fzf keyboard integration | `/usr/share/doc/fzf/examples/key-bindings.bash` absent, although the package metadata lists it; the workspace only conditionally sources that file |
| Ctrl-R | Still Bash's built-in `reverse-search-history`; the fzf history picker is not enabled |
| Bash completion | Package `1:2.11-8` installed; loader and fzf completion file present, but the workspace does not source the main loader and `complete -p` is empty |
| Proposed additions | `zoxide`, `delta`, `lazygit`, `eza`, `ncdu`, and `spf` absent |

The inspected interactive shell defined only `_ws_prompt`; no fzf functions were loaded. Ordinary Bash filename/command Tab completion remains available: the missing piece is enhanced programmable completion. The [workspace Bash configuration](../../image/config/bashrc) explains the missing initialization. The intended history key is **Ctrl-R**, not Command-R.

The first improvement should fix these two integration gaps. The matching fzf documentation distinguishes its executable from shell extensions and warns that distribution packages may not enable the key bindings. Modern instructions using `eval "$(fzf --bash)"` apply to fzf 0.48.0 and later; the installed 0.44.1 needs matching external shell scripts, or an intentional pinned upgrade. [Fzf 0.44.1 README](https://raw.githubusercontent.com/junegunn/fzf/0.44.1/README.md), [upstream 0.48.0 changelog](https://github.com/junegunn/fzf/blob/master/CHANGELOG.md#0480)

## Curated working set: 29 tools

First finish the shell integration of the tools already included in the [image definition](../../image/Dockerfile): `fzf`, `fd`, `rg`, `bat`, Bash completion, tmux, Neovim, and htop. Installing a package does not establish that its interactive shortcuts are loaded.

The intended fzf shortcuts are **Ctrl-R** for selecting a previous command onto the editable command line, **Ctrl-T** for inserting a selected file/directory path, and **Alt-C** for selecting a directory to enter. Choosing a history entry should not execute it immediately; it remains available to edit before pressing Enter. These are the proposed integrated behaviors, not currently enabled features of the audited image. [Fzf 0.44.1 shell-integration documentation](https://raw.githubusercontent.com/junegunn/fzf/0.44.1/README.md)

### Already included: 11 tools to make work together

These tools are in the current [image definition](../../image/Dockerfile). The audit above is narrower than the full package list; it separately establishes which interactive integrations are missing.

| Tool | Everyday use | Integration to provide |
| --- | --- | --- |
| [fzf](https://raw.githubusercontent.com/junegunn/fzf/0.44.1/README.md) | Search history and choose paths interactively | Repair the key bindings; use readable text markers. |
| [fd](https://github.com/sharkdp/fd) | Find files by name/type | Feed project-scoped file and directory candidates to fzf. |
| [ripgrep (`rg`)](https://github.com/BurntSushi/ripgrep) | Search text across a project | Share ignore rules with file picking; open a result at its line in the editor. |
| [bat](https://github.com/sharkdp/bat) | Read source/configuration with syntax colors | Use bounded text previews in fzf and file browsing. |
| [bash-completion](https://github.com/scop/bash-completion) | Complete command options and arguments | Load the main completion initialization correctly. |
| [jq](https://jqlang.org/) | Read and filter JSON | Keep as the dedicated JSON query tool. |
| [tmux](https://github.com/tmux/tmux/wiki) | Organize persistent terminal windows/panes | Keep the existing session workflow and readable status bar. |
| [Neovim](https://neovim.io/) | Edit code and scripts within either terminal | Use the separately planned editor configuration; no font-dependent labels required. |
| [htop](https://htop.dev/) | Inspect processes interactively | Keep as the default process viewer; btop is optional below. |
| [ShellCheck](https://www.shellcheck.net/) | Catch common shell-script mistakes | Make available from the editor and project checks. |
| [shfmt](https://github.com/mvdan/sh) | Format shell scripts consistently | Offer an explicit format action using project settings. |

### Shell additions from the first shortlist: 6 tools

| Priority | Tool | Useful behavior | Proposed default |
| --- | --- | --- | --- |
| Next | zoxide | `z project` jumps to a previously visited directory; `zi` selects through fzf. | Keep ordinary `cd`; persist the small navigation database with workspace state. Use the default directory-change hook. [Upstream README](https://github.com/ajeetdsouza/zoxide/blob/main/README.md) |
| Next | delta | Makes Git diffs easier to read with syntax highlighting and optional line numbers. | Unified diffs for narrow windows; detected color depth; no dependency on terminal hyperlinks. Preserve access to plain Git output. [Getting started](https://dandavison.github.io/delta/get-started.html), [options](https://github.com/dandavison/delta/blob/main/manual/src/full---help-output.md) |
| Next, optional interface | lazygit | Keyboard-driven interface for reviewing, staging, and committing changes. | Explicitly keep Nerd Font icons off; configure network checks and periodic repository refresh deliberately. [Configuration](https://github.com/jesseduffield/lazygit/blob/master/docs/Config.md) |
| Optional | eza | Clearer directory listings with colored metadata. | A separate short alias using `--icons=never --hyperlink=never --no-git`; retain `ls`. Avoid recursive size/tree options by default. [Manual](https://github.com/eza-community/eza/blob/main/man/eza.1.md) |
| Optional | ncdu | Interactive view of space used by a chosen directory. | Run on demand against an explicit project directory, with ASCII graphs and read-only controls. [Ncdu 2.8 manual](https://dev.yorhel.nl/ncdu/man/2_8) |
| Optional trial | Superfile | File browsing, operations, and previews in a terminal UI. | Use its supported no-Nerd-Font configuration, basic borders, and manual text previews. Verify PuTTY rendering before including it in the standard set. [Configuration](https://superfile.dev/configure/superfile-config/) |

### Further useful additions: 12 tools

"Default addition" means recommended for the next development image, pending the user's selection. It does not mean installed. "Optional" means valuable for a particular workflow or a substitute for an existing interface.

| Choice | Tool | What it adds | HPC and terminal defaults |
| --- | --- | --- | --- |
| Default addition | [tealdeer (`tldr`)](https://docs.tealdeer.org/stable/) | Short, practical command examples close to hand | Bundle the help-page cache in the image and disable automatic updates; help works without downloading at first use. |
| Default addition | [just](https://just.systems/man/en/) | Named project commands such as `just check` or `just build` | Run existing project scripts through recipes. Builds still use CMake/Make/Ninja; resource-heavy recipes run in an allocation. |
| Default addition | [uv](https://docs.astral.sh/uv/) | Python virtual environments, dependencies, lockfiles, and Python tool execution | Use project environments and a local cache. No environment creation/download from shell startup; Python downloads are explicit. |
| Default addition | [Ruff](https://docs.astral.sh/ruff/) | Python linting and formatting from the shell/editor | Respect project configuration; keep preview rules off and apply changes explicitly. |
| Default addition | [Mike Farah's yq](https://mikefarah.gitbook.io/yq) | Query/update YAML and convert structured configuration | Select the Go implementation from `mikefarah/yq`; document that exact implementation so another tool named `yq` is not substituted. |
| Default addition | [Miller (`mlr`)](https://miller.readthedocs.io/en/latest/) | Filter, reshape, and summarize CSV/TSV records by field name | Complements jq/yq for tabular job/test results. Scope input files; large sorts still need memory. |
| Default addition | [lnav](https://lnav.org/features) | Search and correlate multiple logs, with filters and SQL queries | Open explicitly selected job logs. Timestamp merging depends on recognizing the log format. Keep its state on the system. |
| Optional, per project | [direnv](https://direnv.net/) | Load/unload a project's environment when entering/leaving its directory | Enable the shell hook only when wanted, then require `direnv allow` for each reviewed `.envrc`; never globally auto-approve projects. |
| Optional, on demand | [watchexec](https://github.com/watchexec/watchexec/blob/main/doc/watchexec.1.md) | Rerun selected checks when source files change | Watch selected source directories, exclude generated output, debounce changes, and run substantial tests/builds in an allocation. |
| Optional, on demand | [hyperfine](https://github.com/sharkdp/hyperfine) | Repeated command timings with summaries and exports | Benchmark within an allocation using deliberate run counts; do not benchmark job-submission commands as if they were the job itself. |
| Optional alternative | [btop](https://github.com/aristocratos/btop) | A more visual CPU/memory/process dashboard | Retain htop as the simple default. Test `graph_symbol = "tty"`, color fallback, and a moderate refresh interval; GPU panels depend on available device/library access. |
| Optional specialist | [Difftastic (`difft`)](https://difftastic.wilfred.me.uk/) | Syntax-aware comparisons for changes obscured by formatting | Keep delta for routine Git diffs; invoke Difftastic explicitly for structural comparisons, rather than stacking two default diff paths. |

The highest-value expansion after the shell fixes is **zoxide, delta, tealdeer, just, uv, Ruff, yq, Miller, and lnav**. Lazygit and a file manager are useful interface choices. Btop and Difftastic overlap with existing capabilities and should earn their place through use. This is a workflow recommendation, not an argument to install every candidate.

## Use recent stable releases, then pin them

The upstream GitHub `releases/latest` pages resolved to the following stable release pages during this review. These are researched candidates, not versions installed in the current SIF. Recheck upstream when preparing the build because newer releases may appear after this note.

| Candidate | Release observed on 2026-09-22 |
| --- | --- |
| tealdeer | [1.9.0](https://github.com/tealdeer-rs/tealdeer/releases/tag/v1.9.0) |
| direnv | [2.37.1](https://github.com/direnv/direnv/releases/tag/v2.37.1) |
| just | [1.58.0](https://github.com/casey/just/releases/tag/1.58.0) |
| watchexec CLI | [2.7.3](https://github.com/watchexec/watchexec/releases/tag/v2.7.3) |
| uv | [0.12.17](https://github.com/astral-sh/uv/releases/tag/0.12.17) |
| Ruff | [0.16.8](https://github.com/astral-sh/ruff/releases/tag/0.16.8) |
| Mike Farah's yq | [4.53.6](https://github.com/mikefarah/yq/releases/tag/v4.53.6) |
| Miller | [6.21.0](https://github.com/johnkerl/miller/releases/tag/v6.21.0) |

Proposed update policy: select the latest stable release compatible with the base image; record exact versions, artifact hashes, and source URLs; bundle completions/help/configuration from matching releases; then validate and produce a new SIF. Keep the previous SIF for rollback. Avoid beta/nightly builds and floating `latest` downloads in build recipes. Runtime startup should use the bundled versions without updating them. This policy is a reproducibility recommendation; it has not been implemented by this research task.

## Details that make the expansion practical

Tealdeer's current configuration supports a chosen cache directory and disabled auto-updates. Seed a versioned help cache at image build time, including the pages' attribution/license information, and test it with networking disabled. Merely installing the `tldr` executable does not provide its page cache. Current stable documentation uses `[directories] cache_dir`; use the selected version's configuration, rather than copying environment-variable advice from old tutorials. [Cache directory](https://docs.tealdeer.org/stable/config_directories.html), [updates](https://docs.tealdeer.org/stable/config_updates.html), [usage](https://docs.tealdeer.org/stable/usage.html)

Uv supports explicit control over Python downloads, an offline mode, and local package sources. Prefer the Python already supplied by the image, with automatic interpreter downloads disabled. For disconnected work, prepare the project dependencies/cache or wheelhouse deliberately; a lockfile alone does not supply package artifacts. This tooling does not establish compatibility with a site's MPI, GPU toolkit, or vendor Python packages. [Uv settings](https://docs.astral.sh/uv/reference/settings/)

Direnv executes authorized `.envrc` code in a subshell and exports the resulting environment changes; its benefit is convenient local project setup. Keep approval explicit. Do not use it to assume that a host's module functions or GPU/MPI runtime will automatically work inside the container. [Direnv operation and authorization](https://direnv.net/)

Watchexec uses native filesystem notifications by default and provides polling when needed for filesystems where those notifications are unreliable. Polling can increase filesystem work, so choose it deliberately with a measured interval and a small watched tree. Hyperfine repeats commands; use it for completed work performed in the allocation, with the working directory and cache conditions recorded. These are usage recommendations rather than measurements of the target clusters. [Watchexec manual](https://github.com/watchexec/watchexec/blob/main/doc/watchexec.1.md), [hyperfine usage](https://github.com/sharkdp/hyperfine)

Miller streams many transformations, but operations such as sorting retain records in memory. Lnav's structured queries depend on recognized or configured log formats; arbitrary PBS/Slurm program output is not automatically a structured database. Start with selected logs/results, then add a format only if useful. [Miller memory behavior](https://miller.readthedocs.io/en/latest/streaming-and-memory/), [lnav features and formats](https://lnav.org/features)

## Superfile can run without Nerd Fonts

The supported setting is `nerdfont = false`; a separate minimal edition is unnecessary. The selection-checkbox setting is ignored when Nerd Fonts are disabled. Default borders still use Unicode line-drawing characters. The documented border fields accept any one-column character, so the following is a proposed compatibility configuration, not a tested guarantee that every screen is ASCII. [Superfile configuration](https://superfile.dev/configure/superfile-config/)

```toml
nerdfont = false
show_select_icons = false
show_image_preview = false
default_open_file_preview = false
auto_check_update = false
metadata = false
enable_md5_checksum = false
code_previewer = "bat"

border_top = "-"
border_bottom = "-"
border_left = "|"
border_right = "|"
border_top_left = "+"
border_top_right = "+"
border_bottom_left = "+"
border_bottom_right = "+"
border_middle_left = "+"
border_middle_right = "+"
```

These are documented controls; preview, metadata, and checksum defaults above are recommendations to keep large-file reads deliberate. Disabling the default preview still permits opening it when useful. The icon initializer describes ASCII replacements for its no-Nerd-Font path, but that is separate from border configuration and other UI rendering. [Superfile icon API/source](https://pkg.go.dev/github.com/yorukot/superfile/src/config/icon#InitIcon)

## Small configuration choices matter

Zoxide learns visited directories rather than needing an initial recursive filesystem catalog. Its `_ZO_DATA_DIR` and `_ZO_EXCLUDE_DIRS` settings provide database placement and exclusions. Preserve the default `pwd` hook rather than choosing the hook that updates at every prompt. This is a good fit for persistent per-workspace state. [Zoxide README](https://github.com/ajeetdsouza/zoxide/blob/main/README.md)

Delta supports `true-color = auto`; `never` explicitly avoids 24-bit colors. Terminal hyperlinks require terminal support, so they should remain optional. Line-number separators and wrap indicators can be customized if standard Unicode characters render poorly. [Delta options](https://github.com/dandavison/delta/blob/main/manual/src/full---help-output.md), [hyperlinks](https://dandavison.github.io/delta/hyperlinks.html)

Lazygit's documented `gui.nerdFontsVersion: ""` disables icons. Its default spinner and borders still contain ordinary Unicode. Border style can be `hidden`, and spinner frames are configurable if an ASCII fallback is needed. Suggested HPC configuration includes `git.autoFetch: false` and `update.method: never`; choose a conservative refresh interval, or disable automatic refresh for especially large repositories. Current upstream also exposes `git.autoDetectExternalChanges`; verify availability in the pinned version before using it. [Lazygit configuration](https://github.com/jesseduffield/lazygit/blob/master/docs/Config.md)

Ncdu 2.8 documents `-rr` to disable deletion and shell spawning, `-x` to stay on one filesystem, and `--graph-style hash` for ASCII bars. A single scan thread is its default. These controls do not make a large recursive scan cheap: select a project subtree, not an entire shared work/archive filesystem. Check the packaged version before copying version-specific flags. [Ncdu 2.8 manual](https://dev.yorhel.nl/ncdu/man/2_8)

## Terminal and filesystem baseline

Font glyph availability and color support are separate capabilities. PuTTY supports 256-color and truecolor modes, local font selection, and UTF-8 translation; it need not look plain. [PuTTY configuration manual](https://the.earth.li/~sgtatham/putty/0.85/htmldoc/Chapter4.html#config-colours) VS Code also documents terminal font selection and truecolor, including special treatment of some Powerline/box-drawing glyphs. A successful VS Code screenshot therefore does not prove that the same icons will render in a particular PuTTY font. Prefer a consistent no-Nerd-Font default and make icons a personal opt-in. [VS Code terminal appearance](https://code.visualstudio.com/docs/terminal/appearance)

VS Code can handle some shortcuts before the shell receives them; keep any required terminal shortcut adjustment narrow. [VS Code keyboard shortcuts and the shell](https://code.visualstudio.com/docs/terminal/advanced#keyboard-shortcuts-and-the-shell)

For HPC storage, the recommended behavior is on-demand project-scoped search and previews. Avoid automatic whole-home/archive indexes, recursive size calculation in ordinary listings, and filesystem traversal from every prompt. These are engineering choices based on the tools' documented operations, not performance measurements from Ruth, Jean, or Blueback. Keep all histories, navigation databases, and configuration local to the workspace on each system.
