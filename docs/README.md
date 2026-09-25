# Workspace documentation

These user guides describe the **0.7 thin workspace** and the repository's **`./setup`** installer. Start with installation once, then use the daily guide. Updating the repo updates these documents; a running workspace keeps the release with which it started.

| What you want to do | Read this |
| --- | --- |
| Install, update, transfer offline, or repair a missing `ws` | [Setup and startup](thin-start.md) |
| Learn a complete working routine, with a practice project | [Daily workflow](daily-workflow.md) |
| Look up a command or shortcut quickly | [Command reference](command-reference.md) |
| Understand editor features, agents, tmux, and interactive allocations | [Editor and sessions](editor-and-agents.md) |
| Find the login node that holds a detached workspace | [Session locations](session-locations.md) (new repository command; not yet in 0.7.1) |
| Use existing Windows connection tools from VS Code | [Windows, Kerberos, and VS Code](windows-vscode-hpc.md) |
| Change your preferences and understand what persists | [Personal configuration](dotfiles.md) |
| Reuse an existing local system profile | [Inspector integration](inspector-integration.md) |
| Resolve startup, terminal, locale, or tool problems | [Troubleshooting](troubleshooting-startup.md) |
| Configure a module-provided Apptainer once | [Runtime setup](runtime-setup.md) |
| See the plan for forms that create and edit configuration files | [Guided configuration](guided-configuration.md) |
| Configure agents, rotate keys, and switch API gateways | [Agent profiles and forms](agent-profiles.md) |
| Use a restricted native Codex configuration with custom headers and a CA | [Site-provided Codex configuration](restricted-codex.md) |
| Understand which agent skills are shipped and activated | [Skills](skills.md) |
| See exactly what was tested | [Validation record](validation.md) |

The daily guide uses the bundled Bash, fd, ripgrep, fzf, bat, Neovim, and other tools with the site's existing files, Git, Python, compilers, and scheduler clients. `find` is a normal host utility; `fd` is the packaged convenience alternative. Run `ws tools` inside the workspace for the actual image's tool versions.

## Design and release records

[Current architecture and future scientific stacks](design-direction.md), [requirements](workflow-options.md), [implementation plan](thin-container-plan.md), and [toolkit roadmap](toolkit-roadmap.md) explain decisions and remaining work. Features marked proposed are not commands to use today.

The [0.7.1 notes](releases/0.7.1-preview1.md) describe the form contrast fix; the [0.7.0 notes](releases/0.7.0-preview1.md) introduce configuration and gateway profiles. Older [release notes](releases/), [research snapshots](research/), and [terminal pictures](previews/README.md) retain their original version context. They are historical evidence, not the current installation instructions. The [0.4 transfer guide](transfer.md), [core workflow](legacy/core-workflow.md), [core dotfiles](legacy/core-dotfiles.md), and [core troubleshooting](legacy/core-troubleshooting.md) remain available for that older image.
