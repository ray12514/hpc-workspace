# Windows: connect from VS Code without extensions

Use **VS Code's built-in terminal and an SSH client already supplied by the approved kit**. That gives you a terminal for the same remote Bash, tmux, Neovim, and workspace tools. This workflow uses built-in terminal profiles, settings, and optional tasks. It requires no VS Code extensions or VS Code Server on the cluster. [VS Code terminal profiles](https://code.visualstudio.com/docs/terminal/profiles)

VS Code, PuTTY, and the approved Kerberos/PKI tools are already installed. **Installing VS Code extensions is not allowed for this setup.** Use the existing approved executables; no Windows package downloads or execution-policy changes are part of these instructions.

## Locate the existing client once

Open **Terminal → New Terminal** in VS Code and choose PowerShell. If you need to locate the kit's executables:

```powershell
Get-Command ssh, plink, putty, kinit, klist -All -ErrorAction SilentlyContinue |
    Select-Object Name, Source
```

This checks PATH, not every installation directory. For missing entries, inspect the existing PuTTY shortcut's **Target** and the approved kit's folder/documentation. Do not assume Plink was installed just because PuTTY is present.

Obtain or renew your Kerberos ticket using the same approved PKINIT/CAC/YubiKey procedure that works with PuTTY. Use that kit's credential manager or `klist`; a different Windows `klist.exe` can inspect a different credential cache. Preserve the kit's required environment and run VS Code as the same Windows user. If the kit requires launching applications through a supplied shortcut/environment, use that entry point. The exact local command belongs in your private connection notes. HPCMP's [public access overview](https://www.centers.hpc.mil/users/index.html) points users to its Kerberos kit and site instructions.

## Reuse PuTTY connections in the integrated terminal

If the approved installation includes **Plink**, test it in PowerShell with an existing saved PuTTY session:

```powershell
& 'C:\REPLACE_WITH_APPROVED_KIT_PATH\plink.exe' -load 'YOUR SAVED SESSION NAME' -t
```

Plink is PuTTY's console client; `-load` reuses a saved session and `-t` requests a remote terminal. Use the executable from the matching approved installation so it can use the same settings and authentication support. Keep its normal host-key/PIN prompts. See the [PuTTY Plink manual](https://the.earth.li/~sgtatham/putty/0.85/htmldoc/Chapter7.html).

Once connected:

```bash
hostname
cd /replace/with/your/project
ws session
```

Check ordinary typing, Ctrl-R, tmux detach/reattach, Neovim, and terminal resizing. `stty size` should reflect the new size after a resize. This client/kit combination has not been tested here. If full-screen behavior fails, use another already-approved compatible SSH client or the working PuTTY connection while resolving that specific issue.

To save connection choices, open **Preferences: Open User Settings (JSON)** from Ctrl-Shift-P. Merge the [terminal profiles example](../examples/vscode-hpc-terminals.json) into your existing settings, replacing executable paths and saved-session names locally. Do not overwrite unrelated settings or an existing `terminal.integrated.profiles.windows` object; add entries to it. The terminal dropdown then offers Ruth, Jean, and Blueback. A default profile applies to newly opened terminals, not automatically to VS Code startup. [VS Code terminal profiles](https://code.visualstudio.com/docs/terminal/profiles)

The [appearance settings](../examples/vscode-terminal.json) are optional and use ordinary fonts. They do not configure authentication. PuTTY's GUI window itself cannot be embedded as a VS Code terminal.

If Plink is absent but the kit supplies a working OpenSSH-compatible client, use that client instead. First verify it authenticates from PowerShell, then use its full path and an argument list such as `["-t", "ruth"]` in the terminal profile. The alias must exist in that client's configuration. Merely finding Windows `ssh.exe` does not establish compatibility with the kit's Kerberos tickets.

## Open directly into a connection

After a manual connection works, create a dedicated local folder such as `Documents\HPC Connections\Ruth`. Save a locally edited copy of [the task example](../examples/vscode-hpc-tasks.json) as `.vscode\tasks.json` there. It uses the existing client as a process and connects when that folder opens.

Open the folder in VS Code and allow automatic tasks for **that folder** when prompted. Older versions may expose this through **Tasks: Manage Automatic Tasks**. If your organization disables automatic tasks, use **Terminal: Run Task → Connect to HPC** instead. The task needs workspace trust; it does not bypass trust or credential prompts. [VS Code task run behavior](https://code.visualstudio.com/docs/debugtest/tasks#run-behavior)

Keep keys, PINs, and ticket acquisition out of these settings. The connection can start automatically; ticket renewal still follows the kit's procedure. Save one folder/profile per connection if useful. Avoid putting an unconditional SSH command in your general PowerShell profile, where unrelated terminals and tasks would trigger it.

## Edit files and use the workspace

VS Code displays the remote terminal, while Bash and all commands entered after SSH connects run on the cluster. Run `ws session`, then use Neovim, fzf, ripgrep, Codex, and the other workspace tools there as usual. Your normal kit authentication and site permissions still apply.

VS Code's Explorer and graphical editor remain local to Windows in this workflow. Opening an SSH terminal does not make them browse remote files. Edit remote files with `nvim` inside the workspace. The local connection folder contains only your terminal/task settings; remote projects do not need to be copied to Windows.

## Return to a saved workspace

After reconnecting, check the actual node before starting another session. The new repository launcher offers `./bin/ws sessions` to look up recorded locations, including older 0.7.1 records when their metadata is present. It does not SSH to nodes or migrate tmux. Reconnect through the approved address for the recorded node, then select the same project and release. See [session locations and availability](session-locations.md).

An SSH hop from one login node to another may authenticate without providing usable Kerberos tickets on the destination. Prefer a fresh connection from Windows to the recorded node when the site supports it, using the same approved kit. If a hop is required, follow the site's delegation procedure and verify tickets before attaching. Keep a session holding an interactive job alive while resolving access. The [Kerberos reconnect notes](session-locations.md#kerberos-across-an-ssh-hop) distinguish missing delegation from an old tmux pane retaining an outdated cache.

An SSH terminal gives you a Linux shell, not a full graphical desktop. If a desktop is needed, use the site's browser-based Open OnDemand desktop service when available and approved, or an already-approved remote desktop client. Keep compute-heavy work inside the site's normal allocation procedure.
