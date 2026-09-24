# Workspace dotfiles

Shared defaults are versioned in `image/config/` beside the image recipe. The **0.6 thin preview** carries them under `/workspace-tools/config` and uses the same personal `bashrc`, `inputrc`, `nvim.lua`, `tmux.conf`, and bat configuration locations described below. It applies settings to those tools without globally changing the host's XDG directories. The thin Neovim launcher loads the shared configuration and personal `nvim.lua` directly; `xdg/nvim/init.lua` remains the older core-image loader. Git uses its normal host configuration; the shell defaults to the Delta pager only when no pager was chosen already.

The thin release also seeds missing `xdg/superfile/config.toml`, `xdg/lazygit/config.yml`, `xdg/btop/btop.conf`, and `xdg/tealdeer/config.toml`. Their wrappers select these settings only for those applications. Shared Neovim plugins/parsers remain in the image and personal `nvim.lua` loads last. Packaged tmux runs inside the thin environment and reads personal `tmux.conf` after the image defaults. See the [current editor and tool guide](editor-and-agents.md).

The remaining image-path and global-XDG details on this page describe the retained **0.4 core release**, which uses `/opt/workspace/config`. See the [thin startup guide](thin-start.md) for the current workflow. No dotfile manager or startup download is required.

## Personal configuration

On first container entry, missing starter files are created under `~/.config/hpc-workspace/`. Existing files and symlinks are preserved, including the Bash and Neovim overrides supported by earlier releases. Files are published atomically so two simultaneous first entries cannot replace one another's preferences. New files are private to the user.

```text
~/.config/hpc-workspace/
    bashrc                  personal Bash aliases and preferences
    inputrc                 personal Readline settings and keybindings
    nvim.lua                personal Neovim overrides
    tmux.conf               personal workspace tmux overrides
    xdg/
        nvim/init.lua       loads defaults from the selected image
        bat/config          personal bat options
        git/config          personal workspace Git configuration
```

This folder can also contain the existing local `config.json` used by Inspector import. It remains separate from the dotfile mechanism and is never overwritten by it. Keep site facts, credentials, histories, and local reports out of the public dotfile sources. Portable preferences can be transferred independently using the approved method.

The container sets `XDG_CONFIG_HOME` to this writable `xdg` directory and `XDG_CONFIG_DIRS` to the image defaults. Programs can save personal settings without writing into the SIF. Per-application loading behavior is documented below; setting an XDG search path alone does not make every application merge configuration files. [XDG specification](https://specifications.freedesktop.org/basedir/latest/)

The launcher explicitly sets Apptainer's home destination to the same path it binds from your host environment. This also handles a host `HOME` that differs from the account database's default. [Apptainer home option](https://apptainer.org/docs/user/1.3/cli/apptainer_exec.html#options)

## Loading order

| Tool | Defaults and personal settings |
| --- | --- |
| Bash | Loads the image's `bashrc`, enhanced command completion, and the bundled fzf bindings. Reapplies personal Readline choices, then sources personal `bashrc` last. |
| Readline | `INPUTRC` selects the personal `inputrc`; its starter file includes the image defaults before personal settings. Retain that include to receive future default updates. |
| Neovim | The personal `xdg/nvim/init.lua` starter loads the current image's configuration; that configuration loads personal `nvim.lua` last. The image directory supplies the shared colorscheme. Keep the starter loader to receive default updates. |
| tmux | `ws session` starts its dedicated host tmux server with the matching source bundle's defaults, then sources personal `tmux.conf` if present. It does not load or modify normal host `~/.tmux.conf`. |
| Git | `GIT_CONFIG_SYSTEM` selects the image's editor/color defaults. Git then reads workspace `xdg/git/config`, normal `~/.gitconfig`, and repository configuration in its normal precedence order. Identity and credentials are not supplied by the image. |
| bat | Reads its native configuration from workspace `xdg/bat/config`. The interactive shell supplies the existing shared theme; personal Bash settings can change `BAT_THEME`. |

Normal host Bash, Readline, and Neovim startup files are not sourced or changed by container entry. Git's normal `~/.gitconfig` remains available for existing user identity and settings. Normal host `~/.config/git/config` is outside the workspace's XDG directory; deliberately include it from a personal Git config if needed. [Git configuration locations and ordering](https://git-scm.com/docs/git-config#FILES)

Files for tools not yet installed, such as delta/eza/lazygit, will be added with their tested integrations. This release establishes configuration handling for the current toolset.

## Everyday adjustments

Edit personal `bashrc` for aliases or environment preferences, `nvim.lua` for editor options, and `tmux.conf` for session styling or shortcuts. The starter files contain small examples. Use `xdg/bat/config` for bat's native command-line options and `xdg/git/config` for workspace-specific Git preferences.

Start a fresh workspace shell after Bash or Readline changes. Restart Neovim after editor changes. Tmux reads its configuration when its server is first created; reconnecting to an existing session does not load a newer image or configuration. To apply just a personal tmux edit, use the tmux command prompt (`Ctrl-b :`) and enter:

```text
source-file ~/.config/hpc-workspace/tmux.conf
```

The initialized files are user-owned and never overwritten by entry. To recreate one starter file, move that particular file to a backup and enter again. Keep the rest of the directory, especially the local workspace `config.json`.

## Shell integration fixed in this release

The earlier image installed fzf, but its key-binding script was omitted by the base image's documentation exclusions. The build now retains the package's matching script and installs it as a runtime asset. Bash also explicitly initializes its installed completion framework.

- **Ctrl-R:** choose a historical command and place it on the editable command line; selection does not execute it.
- **Ctrl-T:** insert a selected file/directory path.
- **Alt-C:** select a directory to enter.
- **Tab:** complete supported command options and arguments, including Git commands.

The source of the bindings remains the pinned distribution package; the broader newest-stable toolkit upgrade is tracked in the [toolkit roadmap](toolkit-roadmap.md). Perform file picking from the intended project directory. [Fzf integration for the packaged release](https://github.com/junegunn/fzf/blob/0.44.1/README.md#key-bindings-for-command-line)

## Updates and persistent state

New image releases supply new shared defaults. Starter include/loader files keep selecting the current image's defaults, while personal settings are retained. A self-contained personal configuration intentionally replaces that application's starter behavior. No automatic merge of edited preferences is performed.

Command history, editor undo and sessions, skill state, and caches retain their existing persistent locations under the workspace state directory. Cluster profiles, personal dotfiles, and application state have separate roles. The host launcher continues to own scheduler and mount configuration; dotfiles do not choose an MPI/GPU runtime or submit jobs.
