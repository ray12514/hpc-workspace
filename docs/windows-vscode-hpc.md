# Windows: connect to the workspace from VS Code

Start with **VS Code's integrated terminal and an SSH client already supplied by the approved kit**. That gives you a terminal for the same remote Bash, tmux, Neovim, and workspace tools. Full VS Code remote editing is a separate option, with extra prerequisites.

Known installed: VS Code, PuTTY, and the approved Kerberos/PKI kit. Remote - SSH, Plink, and an OpenSSH-compatible client have not yet been confirmed. Nothing in this guide requires downloading a Windows package, changing execution policy, or installing an extension without approval.

## Check existing tools once

In a VS Code PowerShell terminal:

```powershell
Get-Command code, ssh, plink, putty, kinit, klist -All -ErrorAction SilentlyContinue |
    Select-Object Name, Source
```

This checks PATH, not every installation directory. For missing entries, inspect the existing PuTTY shortcut's **Target** and the approved kit's folder/documentation. Do not assume Plink was installed just because PuTTY is present.

Open Extensions with **Ctrl-Shift-X**, filter with `@installed`, and look for **Remote - SSH** by Microsoft. If the `code` command is available, an alternative check is:

```powershell
code --list-extensions | Select-String '^ms-vscode-remote.remote-ssh$'
```

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

This folder and VS Code's Explorer are local Windows files. Remote work stays in the SSH terminal; use the workspace's Neovim there.

## Full remote editing, when the prerequisites exist

Remote - SSH needs the Microsoft extension, an **OpenSSH-compatible** client, and permission to run its VS Code Server on the Linux host. It installs/updates that server and may install remote extensions. With downloads prohibited, proceed only when the necessary components are already available or can be staged through the site's approved process. **PuTTY/Plink is not a supported Remote - SSH transport.** [Microsoft Remote - SSH requirements and limitations](https://code.visualstudio.com/docs/remote/ssh)

If those conditions are met:

1. Prove the approved OpenSSH-compatible client can connect from PowerShell using the kit's authentication. PuTTY saved sessions are not OpenSSH config entries; transfer the relevant local connection settings deliberately.
2. Set `remote.SSH.path` to that executable in VS Code. Use **Remote-SSH: Open SSH Configuration File** to choose a writable personal config, or specify it with `remote.SSH.configFile`.
3. Add local aliases for your approved endpoints, username, and any kit-required authentication settings. For a resumable connection, prefer the approved endpoint for a specific login node.
4. Use **Remote-SSH: Connect to Host**, select the alias, and open a remote project folder. Then run `ws session` in the remote terminal.

Keep Bash startup suitable for noninteractive SSH. The normal workspace PATH hook is fine; do not automatically replace every SSH shell with `ws enter` or tmux. The VS Code Server/editor runs on the host; entering the workspace in one terminal does not put the server or extensions inside the SIF.

Round-robin routing matters here too: Remote - SSH can make multiple connections, and different destination nodes can break the server/tunnel connection. Use a site-supported consistent route. See [Microsoft's guidance on dynamically assigned hosts and startup scripts](https://code.visualstudio.com/docs/remote/troubleshooting#connecting-to-systems-that-dynamically-assign-machines-per-connection).

## Return to a saved workspace

After reconnecting, check the actual node before starting another session. The new repository launcher offers `./bin/ws sessions` to look up recorded locations, including older 0.7.1 records when their metadata is present. It does not SSH to nodes or migrate tmux. Reconnect through the approved address for the recorded node, then select the same project and release. See [session locations and availability](session-locations.md).

An SSH terminal is a Linux shell; Remote - SSH adds remote file editing. Neither is a full Linux graphical desktop. If a desktop is needed, use the site's browser-based Open OnDemand desktop service when available and approved, or an already-approved remote desktop client. Keep compute-heavy work inside the site's normal allocation procedure.
