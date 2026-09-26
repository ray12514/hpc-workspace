# Personal workspace configuration

This page describes the **0.7 thin workspace**. Shared defaults ship in the image; your preferences and state live in writable directories on the system. Updating with `./setup` changes the selected image and launcher while keeping those personal files. The [0.4 configuration guide](legacy/core-dotfiles.md) is retained separately.

## Installation and shell startup

`./setup` installs under `~/.local/share/hpc-workspace/runtime` by default. It adds a small managed PATH block to `.bashrc` and the active Bash login profile. That block makes `ws` available; it does not enter a container automatically. The installed `activate.sh` is the file it sources. Ordinary subsequent logins need only `ws enter` or `ws session`.

If the site loads another personal startup file, use `./setup --shell-startup /path/to/file`. `--prefix DIRECTORY` selects another runtime location; `--no-shell-hook` records that startup files should be left alone. Those preferences are retained by later setup at the same installation. See [setup](thin-start.md) for offline transfer and using an already-open terminal.

## Defaults and overrides

Container entry creates missing starter files in **`~/.config/hpc-workspace`** and preserves existing files and symlinks. It does not overwrite an edited file with a newer template. The shared defaults themselves are selected from `/workspace-tools/config` in the current image.

| Tool | Current loading behavior | Personal file |
| --- | --- | --- |
| Bash | Shared Bash settings, completion/fzf bindings, then personal settings | `~/.config/hpc-workspace/bashrc` |
| Readline | Shared defaults plus a generated copy of personal settings, reapplied after fzf bindings | `~/.config/hpc-workspace/inputrc` |
| Neovim | Shared config and bundled plugins, then personal Lua | `~/.config/hpc-workspace/nvim.lua` |
| tmux | Shared defaults on its workspace server, then personal tmux config | `~/.config/hpc-workspace/tmux.conf` |
| bat | Personal native bat options; shell chooses the shared theme when color is enabled | `~/.config/hpc-workspace/xdg/bat/config` |
| Superfile | Its wrapper selects the workspace application config | `~/.config/hpc-workspace/xdg/superfile/config.toml` |
| lazygit | Its wrapper selects the workspace application config | `~/.config/hpc-workspace/xdg/lazygit/config.yml` |
| btop | Its wrapper selects the workspace application config | `~/.config/hpc-workspace/xdg/btop/btop.conf` |
| tldr | Its wrapper selects configuration pointing at the bundled read-only help cache | `~/.config/hpc-workspace/xdg/tealdeer/config.toml` |
| lnav | Its wrapper scopes application configuration to workspace `xdg`; no starter file is seeded | Application-created files below `~/.config/hpc-workspace/xdg` |
| Git | Normal host/user/repository configuration; Delta is the fallback pager if none was chosen | Your existing Git configuration |

The thin workspace does **not globally replace `XDG_CONFIG_HOME`**. Some application wrappers select their own configuration; ordinary host programs retain their normal settings. Neovim's wrapper selects a workspace state directory without changing configuration for the entire shell.

The starter `xdg/nvim/init.lua` and `xdg/git/config` remain for compatibility with the old core image. The current thin Neovim wrapper directly loads `nvim.lua` after its shared config; it does not use that old init loader. Thin Git does not automatically read the old workspace `xdg/git/config`. Use your normal Git configuration for identity and preferences.

Your host shell has already initialized its environment before `ws enter`. The workspace inherits it and loads its own Bash configuration; it does not rerun your host login files as its interactive rcfile. Workspace tmux uses its own config, not host `~/.tmux.conf`. Personal Neovim configuration belongs in the workspace `nvim.lua`, not the host's usual `init.lua`.

## Small personal changes

For navigation aliases or the optional `fedit` helper from the [daily guide](daily-workflow.md#choose-a-filename-and-preview-it), edit:

```bash
nvim "$HOME/.config/hpc-workspace/bashrc"
```

For example, add `alias cproject='cd "$HOME/my-project"'` using your real local project path. Start a fresh workspace shell to apply it. To override editor line numbers, add `vim.opt.relativenumber = false` to `nvim.lua` and restart Neovim.

Choose shared color behavior **before entry**, for example `WS_COLOR=256 ws session`. A persistent choice can live in the native Bash startup file your site loads, alongside the installer's PATH hook. The prompt and tmux choose their colors during initialization; setting the variable later in personal workspace Bash is too late to recolor those existing objects. `WS_GIT_PROMPT=0` in personal workspace Bash disables branch lookups on subsequent prompt updates.

After changing personal tmux settings, use Ctrl-B then `:` and enter:

```text
source-file ~/.config/hpc-workspace/tmux.conf
```

That applies the personal file to this server. It does not replace the running image or reload a release's entire shared config. A newly created server uses the new release's defaults.

## Persistent state

The usual state root is **`~/.local/state/hpc-workspace/local`**. Saved site labels, `XDG_STATE_HOME`, or `--state-dir` can change it. Inside the workspace, `printf '%s\n' "$WS_STATE_HOME"` shows the actual path.

| State | Location / behavior |
| --- | --- |
| Bash history | `$WS_STATE_HOME/bash-history`; appended at prompts |
| Neovim undo | `$WS_STATE_HOME/apps/nvim/undo`; supports undo across saved editing sessions |
| Neovim swap | Normally `$WS_STATE_HOME/apps/nvim/swap`; `:set directory?` shows the effective value |
| Neovim layouts | `$WS_STATE_HOME/apps/nvim/sessions`; selected by the editor's starting directory |
| tmux snapshots | `$WS_STATE_HOME/tmux/<node>/<session>`; managed sessions are scoped to project and release |
| Host session bookkeeping | `$WS_STATE_HOME/session-hosts`; used to reconnect to the running keeper. Version 0.7.2 adds readable node/project/release metadata and a [location lookup](session-locations.md) |
| zoxide and other application data | Their ordinary application-specific locations unless a wrapper overrides them; zoxide honors `_ZO_DATA_DIR` and otherwise its normal XDG data location |

In Neovim, `:echo stdpath('state')` shows its state directory. `:wall` saves modified buffers; `:WorkspaceSave` saves layout and file references. Persistent undo is not a copy of all unsaved text. After an unexpected termination, use the swap recovery prompt or `nvim -r path/to/file`; recovery can only restore what was written to disk. Keep the state directory on persistent storage if you need it after an allocation ends.

Tmux snapshots restore arrangement, working directories, and shells. They do not migrate running processes, allocations, or unsaved editor buffers. A live detached login-node session is different: it keeps running while that node and its session survive. See the [daily save/return workflow](daily-workflow.md#save-your-work-and-return-later).

## Local system facts and updates

Inspector's optional `config.json` stores system facts and explicit overrides. Its default location is `${XDG_CONFIG_HOME:-$HOME/.config}/hpc-workspace/config.json`; `WS_CONFIG_DIR` changes that configuration location only. It does not relocate dotfiles, which remain under `~/.config/hpc-workspace`. See the [Inspector guide](inspector-integration.md).

Shared defaults update with the image; personal overrides load afterward. Review a template before adopting new options into an already-edited personal file. To regenerate one starter, move just that file to a backup and enter again. Keep local system facts, histories, credentials, reports, and session state on the originating system.
