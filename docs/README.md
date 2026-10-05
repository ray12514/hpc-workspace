# Workspace documentation

These user guides describe the **0.7.3 thin workspace** and the repository's **`./setup`** installer. Start with installation once, then use the daily guide. Updating the repo updates these documents; a running workspace keeps the release with which it started.

| What you want to do | Read this |
| --- | --- |
| Diagnose the current Blueback workspace attachment/build stall | [START HERE: complete commands and what to send back](../START-HERE-DIAGNOSTICS.md) |
| Test Codex controlling a Blueback allocation or running inside it | [Compute-agent test: commands, placeholders and pass conditions](blueback-compute-agent-test.md) |
| Continue CCE on compute after option B passes | [Clean up old node processes without reattaching, then resume Codex/CSE](blueback-compute-handoff.md) |
| Install, update, transfer offline, or repair a missing `ws` | [Setup and startup](thin-start.md) |
| See how setup, the host, image, sessions, and agents fit together | [Architecture map](architecture-map.md) |
| Learn a complete working routine, with a practice project | [Daily workflow](daily-workflow.md) |
| Look up a command or shortcut quickly | [Command reference](command-reference.md) |
| Understand editor features, agents, tmux, and interactive allocations | [Editor and sessions](editor-and-agents.md) |
| Find, reconnect to, or stop a managed workspace | [Session locations](session-locations.md) |
| Use existing Windows connection tools in VS Code without extensions | [Windows, Kerberos, and VS Code](windows-vscode-hpc.md) |
| Change your preferences and understand what persists | [Personal configuration](dotfiles.md) |
| Reuse an existing local system profile | [Inspector integration](inspector-integration.md) |
| Resolve startup, terminal, locale, or tool problems | [Troubleshooting](troubleshooting-startup.md) |
| Configure a module-provided Apptainer once | [Runtime setup](runtime-setup.md) |
| See the plan for forms that create and edit configuration files | [Guided configuration](guided-configuration.md) |
| Configure agents, rotate keys, and switch API gateways | [Agent profiles and forms](agent-profiles.md) |
| Use a restricted native Codex configuration with custom headers and a CA | [Site-provided Codex configuration](restricted-codex.md) |
| Understand which agent skills are shipped and activated | [Skills](skills.md) |
| Assess Pulse telemetry alongside the workspace | [Pulse integration assessment](pulse-assessment.md) |
| See exactly what was tested | [Validation record](validation.md) |

The daily guide uses the bundled Bash, fd, ripgrep, fzf, bat, Neovim, and other tools with the site's existing files, Git, Python, compilers, and scheduler clients. `find` is a normal host utility; `fd` is the packaged convenience alternative. Run `ws tools` inside the workspace for the actual image's tool versions.

## Design and release records

[Current architecture and future scientific stacks](design-direction.md), [requirements](workflow-options.md), [implementation plan](thin-container-plan.md), and [toolkit roadmap](toolkit-roadmap.md) explain decisions and remaining work. Features marked proposed are not commands to use today.

The [0.7.3-preview9 notes](releases/0.7.3-preview9.md) cover named Codex custom-header profiles; [0.7.3-preview8](releases/0.7.3-preview8.md) added per-gateway Codex/Pi CA setup and native Codex key/CA setup; [0.7.3-preview7](releases/0.7.3-preview7.md) added skill activation and the one-command Codex launch; [0.7.3-preview6](releases/0.7.3-preview6.md) covered the confirmed RHEL prompt correction; [0.7.3-preview5](releases/0.7.3-preview5.md) addressed compound read-only site hooks, [0.7.3-preview4](releases/0.7.3-preview4.md) fixed rootless SSH transfers, [0.7.3-preview3](releases/0.7.3-preview3.md) removed the zoxide read-only error, [0.7.3-preview2](releases/0.7.3-preview2.md) added a read-only prompt fallback, and [0.7.3-preview1](releases/0.7.3-preview1.md) added Pi, reconnect/stop controls, the editor-window fix, and the key helper. [0.7.2](releases/0.7.2-preview1.md) fixed tmux routing and added session lookup. Older [release notes](releases/), [research snapshots](research/), and [terminal pictures](previews/README.md) retain their original version context. They are historical evidence, not the current installation instructions. The [0.4 transfer guide](transfer.md), [core workflow](legacy/core-workflow.md), [core dotfiles](legacy/core-dotfiles.md), and [core troubleshooting](legacy/core-troubleshooting.md) remain available for that older image.
