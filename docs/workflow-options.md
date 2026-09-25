# One development environment across systems

Updated 2026-09-25. These are the requirements for the current [0.7 thin workspace](thin-start.md), including centrally packaged CLI/AI tools, editor plugins, configuration forms, and the repo's `./setup` download/install command. They supersede the earlier proposal to divide everyday work between host and container windows. Use the [daily guide](daily-workflow.md) for current operations; site-specific compatibility work continues.

## User experience

Setting up tools and dotfiles on one Linux machine is straightforward. This project supplies that same experience across Ruth, Jean, and Blueback without separately building, configuring, or maintaining the tools on each system.

Enter the development environment and use its shell, appearance, navigation, editor, agents, and other development tools. From that same shell, retain the system's ordinary files, modules, scheduler clients, scientific software, and supported runtime commands. Existing submission scripts stay ordinary site scripts.

The thin container is the delivery mechanism for the prepared tool set and shared settings. The target combines an image-owned Nix store with automatically prepared host integration. Host integration is part of the implementation, not a reason to require the user to switch to another shell for normal system work.

## Maintenance

- Define tools, shared dotfiles, integration logic, and release packaging in one repository.
- Build and test the tool set centrally; ship its dependencies with the image. No toolbox compilation or host Nix installation is required on each target.
- Distribute one versioned release through the chosen transfer route. Use a repeatable installer/update operation to verify and select it on each system.
- Automate local setup and migration. Reuse available Inspector facts and local observations; keep cached facts and any private overrides on the system. Report unsupported cases locally instead of inventing configuration.
- Keep personal files, history, credentials, and state outside the immutable tools. Preserve personal overrides when updating common defaults.

The expected maintenance operation is to update the definition once, build a new release, and apply it through the same automation everywhere. It is not a separate configuration project on every cluster.

## Next implementation

Follow the [thin-container implementation plan](thin-container-plan.md): prepare a small pinned Nix tool set and bundled dotfiles, implement automated host integration, and prove that the same development shell can use both those tools and ordinary system commands. Include deployment, update, rollback, and local diagnostics in that first foundation. Diagnose the reported tmux/bat failures without claiming that changing packaging has fixed them.

Podman is an available runtime to integrate where supported; VS Code is an optional editor. They do not change the development-environment requirement. The [container-runtime research](research/container-build-workflows.md) retains technical findings for implementing build/test access. Its earlier host-terminal-first recommendation is superseded by this design.
