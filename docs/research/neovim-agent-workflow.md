# Neovim and coding-agent workflow

Historical research snapshot: the 0.6 release subsequently implemented the initial plugin/parser and language-server bundle. Use the [current editor guide](../editor-and-agents.md) and [daily tutorial](../daily-workflow.md) for installed behavior; descriptions below are from the original review.

Reviewed 2026-09-22. Proposal only: no tools, plugins, image, or cluster settings were changed. This note uses public upstream documentation and local repository files. The recommendations need integration testing in the selected image and terminal modes.

## Current configuration

The [Neovim configuration](../../image/config/nvim/init.lua) already provides a terminal-aware theme, numbered lines, persistent undo, project-directory-based layout save/restore, native file browsing through `:Explore`, and native LSP configuration for installed `clangd`. It has no third-party plugin bundle or configured Python/Fortran/Bash language servers. The [asset manifest](../../image/assets.lock.json) records Neovim **0.12.5**; this is the current local pin, not a claim that it is the latest upstream release. The [Dockerfile](../../image/Dockerfile) includes `clangd`, `gdb`, `shellcheck`, `shfmt`, `fzf`, `fd`, and `rg`.

## Recommended editor package

Keep native LSP, native sessions, the existing theme, and the existing file browser. Add one component per missing capability:

| Addition | Everyday benefit | Proposed default and compatibility |
| --- | --- | --- |
| [fzf-lua](https://github.com/ibhagwan/fzf-lua) | Find files, search project text, switch buffers, and select symbols/references with previews. | Reuse `fzf`/`fd`/`rg`; disable file/Git icons and use plain borders. Searches start in the project. Upstream requires Neovim >=0.9 and fzf >0.36. |
| [which-key.nvim](https://github.com/folke/which-key.nvim) | Press Space and see the available commands instead of memorizing every shortcut. | Disable mapping icons **and** replace the default key labels/separators with text such as `Space`, `Enter`, `Ctrl`, and `>`. Requires Neovim >=0.9.4. |
| [gitsigns.nvim](https://github.com/lewis6991/gitsigns.nvim) | See changed lines, preview individual changes, and stage selected hunks. | ASCII `+`, `~`, `-` signs; continuous line blame off. Requires Neovim >=0.11. |
| [blink.cmp](https://cmp.saghen.dev/installation) | One completion menu for language-server results, paths, and buffer words. | Plain text item types; use Ctrl-N/P or arrows to select and Ctrl-Y to accept. No automatic insertion of the first suggestion. Requires Neovim >=0.10. |
| [conform.nvim](https://github.com/stevearc/conform.nvim) | One explicit “format this file/selection” command across languages. | Start with manual formatting; format-on-save can be a project preference. Use `shfmt`, Ruff, and `clang-format` where configured. Requires Neovim >=0.10. |
| [nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter) and selected parsers | Syntax-aware highlighting and optional folding. | Build the selected parsers in the image; retain ordinary syntax as a fallback and disable expensive highlighting for large files. |

Blink's default configuration can download its Rust matcher at runtime. For the first implementation, explicitly select `fuzzy.implementation = "lua"`; a prebuilt matcher can be packaged later if measured performance warrants it. Set completion `preselect = false` and `auto_insert = false`. These avoid a first-launch download and unwanted insertion while browsing suggestions. [Matcher options](https://cmp.saghen.dev/configuration/fuzzy), [completion behavior](https://cmp.saghen.dev/configuration/completion)

The current Treesitter `main` is an incompatible rewrite requiring Neovim >=0.12.0 and tree-sitter CLI >=0.26.1, with compiler/tar/curl available during installation. Its queries and parser versions must match. Pin and test the plugin, queries, parser revisions, and runtime together; do not copy older `master`-branch configuration into the new API. Do installation synchronously during the image build; no `TSUpdate` or parser downloads during normal startup. [Treesitter requirements and setup](https://github.com/nvim-treesitter/nvim-treesitter#quickstart)

Use the current native `vim.lsp.config` / `vim.lsp.enable` interface for the small set of servers. Another completion engine or LSP installer is unnecessary for this image. Native LSP already provides diagnostics, definitions, references, hover, rename, and code actions when the server supports them. [Neovim LSP documentation](https://neovim.io/doc/user/lsp/)

## Languages that match this workspace

| Language | Recommendation | HPC-specific setup |
| --- | --- | --- |
| C/C++ | Keep `clangd`; add matching `clang-format` for explicit formatting. | Use the project's `compile_commands.json` so include paths and compiler flags are correct. CMake can export it. Site headers/toolchains must be visible to the editor for complete diagnostics; the base image alone cannot infer them. [clangd project setup](https://clangd.llvm.org/installation#project-setup) |
| Fortran | Add `fortls`. | Configure `.fortls` source/include paths and preprocessors as needed; cap initialization threads and exclude build/output trees. Explicitly disable its automatic updater. Its project configuration takes precedence over command-line settings, which must be accounted for when enforcing the image's no-update behavior. [fortls integration](https://fortls.fortran-lang.org/editor_integration.html), [configuration](https://fortls.fortran-lang.org/options.html) |
| Python | Add **basedpyright + Ruff**. | Basedpyright provides type-aware navigation/completion; Ruff handles linting, fixes, and formatting. Select the actual project interpreter. Use `diagnosticMode = "openFilesOnly"` and respect project type-checking configuration; avoid two providers offering the same hover/import actions. [basedpyright settings](https://docs.basedpyright.com/latest/configuration/language-server-settings/), [Ruff editor setup](https://docs.astral.sh/ruff/editors/setup/) |
| Bash | Add **bash-language-server**, using installed ShellCheck and shfmt. | Keep external explainshell access disabled; use local diagnostics for submission scripts. Upstream currently requires Node >=20, which the image's Node 24 baseline satisfies. [Server documentation](https://github.com/bash-lsp/bash-language-server), [configuration source](https://github.com/bash-lsp/bash-language-server/blob/main/server/src/config.ts) |

Optional next servers: [yaml-language-server](https://github.com/redhat-developer/yaml-language-server) for configuration files, [LuaLS](https://github.com/LuaLS/lua-language-server) for editor configuration, and [cmake-language-server](https://github.com/regen100/cmake-language-server) for CMake. If YAML support is added, bundle required schemas locally and disable automatic SchemaStore/CRD downloads; remote `$schema` references also need deliberate handling. Do not enable every language server for every directory.

Recommended source roots are actual repositories or explicit project directories. Keep home, archives, generated output, and large datasets outside editor search/index roots. Background indexing should be bounded and configurable, especially on login nodes. These are design choices, not measurements from the target systems. Language-server assistance does not replace the site's compiler, MPI, GPU runtime, or scheduler validation.

## Agent workflow

Use a stable tmux layout with an editor window, an agent window, and a shell/native-host window. Run Codex or Claude Code from the appropriate project checkout. This works without an agent-specific Neovim plugin. Keep the existing host submission and allocation workflow: opening a project or saving a file should not submit a job.

1. Save the files the agent will work on and give it a specific task.
2. Let unmodified editor buffers follow on-disk changes. Use native `autoread` and `:checktime`; add focus/buffer-entry checks where necessary. Modified buffers must retain their changes and present a conflict instead of forcing `:edit!`. Shared-filesystem notification behavior needs testing. [Neovim external-change handling](https://neovim.io/doc/user/editing/#timestamp)
3. Review the resulting changes using gitsigns and the shell's Git/delta/lazygit view, then run the relevant tests before staging or committing. If edits must be reviewed before any disk mutation, use the agent's planning/review mode rather than treating buffer reloading as approval.
4. Give simultaneous agents separate Git worktrees so they have distinct checkouts. This separates edited files, although it is not a security sandbox. [Git worktree](https://git-scm.com/docs/git-worktree)

`EDITOR=nvim` and `VISUAL=nvim` already exist in the workspace Bash configuration. Codex documents Ctrl-G to edit the prompt in `VISUAL` or `EDITOR`; saving and exiting returns the text for review before sending. [Codex CLI customization](https://learn.chatgpt.com/docs/cli-customization) Claude Code documents Ctrl-G or Ctrl-X Ctrl-E to edit a prompt in the default editor, and supports worktree-based parallel sessions. [Claude interactive mode](https://code.claude.com/docs/en/interactive-mode), [parallel worktrees](https://code.claude.com/docs/en/common-workflows#run-parallel-sessions-with-worktrees) These are native CLI features. The environment exports provide the basis, but the actual editor shortcuts were not exercised in the pinned CLIs during this research; verify them before adding them to the shipped shortcut sheet.

**Optional later:** [sidekick.nvim](https://github.com/folke/sidekick.nvim) is a third-party adapter that can open agent CLIs and send selected editor context. It requires Neovim >=0.11.2. Its CLI functionality is independent of Copilot; disable `nes` for a CLI-only setup and replace its default icons. It adds convenience but is not an official Codex/Anthropic integration, is not needed for the baseline, and needs separate verification of context sending, external-file reloading, and terminal behavior. Do not enable automatic context transmission as an incidental effect of opening a file.

Keep current session/undo persistence. Session recovery restores editor layout; it does not preserve an allocation or migrate a live process between nodes. Agent conversation resume is separate from editor/session restoration. [Existing workspace workflow](../daily-workflow.md)

## Suggested shortcut vocabulary

These are proposed mappings, not implemented bindings. Use Space followed by ordinary letters so essential actions do not depend on terminal-specific modified keys.

| Keys | Action |
| --- | --- |
| `Space f f` / `Space f g` | Find files / search project text |
| `Space f b` / `Space f s` | Switch buffers / find symbols |
| `Space c d` / `Space c a` | Diagnostics / code actions |
| `Space c r` / `Space c f` | Rename symbol / format |
| `Space g p` / `Space g s` | Preview change / stage hunk |
| `Space w s` / `Space w r` | Existing save / restore layout |
| `Space e` / `Space ?` | Existing file browser / shortcut help |

Use ordinary characters, readable text labels, 256-color styling, and the existing truecolor opt-in. Check narrow terminals, `NO_COLOR`, and plain-font PuTTY; a VS Code-only screenshot is insufficient acceptance evidence.

## Packaging and verification

At each image update, select the newest stable versions that pass the combined compatibility checks, then record exact revisions and hashes. Bundle plugins in a read-only native package directory in the image, with generated help tags. Neovim supports unpacked packages in `pack/*/start/*` and optional packages in `pack/*/opt/*`; this does not require a first-launch package manager. [Native packages](https://neovim.io/doc/user/pack/)

Install language servers and formatters in the image build, with pinned dependencies. Leave histories, undo, sessions, caches, and personal overrides in writable persistent state. Include offline/read-only-image checks for first launch, pickers, actual completion and diagnostics on tiny C/Fortran/Python/Bash fixtures, manual formatting, modified-buffer conflicts, undo/session recovery, and plain-font terminal rendering. Test the selected set before releasing it; this research note does not establish that the proposed integrations already work.
