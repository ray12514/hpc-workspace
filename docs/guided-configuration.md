# Guided configuration in the terminal

Status: **proposed; not implemented or included in 0.6.1-preview1.** This maps an optional form interface for workspace, agent, and project configuration. It does not change existing settings or require a form during ordinary login.

## What the user sees

A terminal form can present text inputs, lists, toggles, and help, then write a valid configuration file. Start from the saved values, change only what is needed, and review the resulting changes before saving. The underlying file remains usable in Neovim or another editor.

For example, the proposed `ws configure` entry point could present:

```text
Configure

  Workspace
  Codex
  Claude Code
  Project configuration

Choose a target -> load current values -> answer questions
                -> validate -> preview changes -> save
```

The destination is always visible. Personal agent settings, project settings, and local cluster configuration have different scopes; a form should not quietly choose between them. Cancellation leaves the original file unchanged. Existing command-line setup and unattended updates remain available.

## Tools to use

**Charm** provides Go terminal tools with different roles:

| Tool | Role in this workspace |
| --- | --- |
| [Gum](https://github.com/charmbracelet/gum) | Standalone commands for prompts, choices, confirmations, and file selection. Package it as a general scripting tool and use it for the first guided setup. |
| [Huh](https://github.com/charmbracelet/huh) | Go library for composing richer forms with field validation. Consider a compiled helper when multi-page forms justify it; users would not need Go installed. |
| [Bubble Tea](https://github.com/charmbracelet/bubbletea) | Broader framework for custom terminal applications. Keep it for a future interface that needs more than forms. |

**Recommendation: start with Gum and the existing Python configuration backend.** This keeps the first implementation small and also gives users reusable prompts for their own shell scripts. Huh is a useful next option, rather than a prerequisite for the first form. The [research note](research/terminal-config-forms.md) records the capabilities and terminal limitations behind this choice.

These projects provide interface components. They do not automatically know which keys a particular application accepts, where its files belong, or how to preserve an existing configuration. The workspace must supply that knowledge. `jq` and `yq` already help manipulate structured data, but they are not form generators or complete application validators.

## Configuration targets

| Target | File or input | First useful coverage |
| --- | --- | --- |
| Workspace | Existing local `config.json` and installer options | Review saved configuration, choose an existing Inspector profile, add an explicit bind when needed, and expose remembered runtime settings once supported |
| Codex | User `~/.codex/config.toml` or a selected project `.codex/config.toml` | A small set of documented preferences supported by the packaged client |
| Claude Code | User `~/.claude/settings.json`, shared `.claude/settings.json`, or personal project `.claude/settings.local.json` | A small set of documented preferences; use its own `/config` menu for options it already handles well |
| Project tools | A known YAML, JSON, or TOML template | Tool-specific paths, modes, and other fields with clear validation |

Codex's official documentation describes TOML configuration, user/project layers, and a published JSON Schema. Use that schema as a source for validation, with explicit compatibility against the client version in our release. A current online schema is not automatically the right schema for an older bundled client. [OpenAI configuration basics](https://learn.chatgpt.com/docs/config-file/config-basic), [OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)

Claude Code documents JSON settings at the scopes above and a built-in `/config` menu for some preferences. Its documentation links a published settings schema and notes that the schema can lag the CLI. Preserve the application's own authentication/state files and managed settings; a preferences form should not replace them. [Claude Code settings](https://code.claude.com/docs/en/settings)

Use each application's configured home directory when it differs from these defaults. Begin with ordinary preferences, not wholesale edits to every setting. Models, providers, hooks, and permissions need application-specific handling; do not copy a shared set of guessed options into both agent formats.

Inspector remains the source of imported cluster facts. The form selects and imports an existing local profile through the current workflow; it does not recreate Inspector or require users to enter facts that are already available. There is no requirement to select Ruth, Jean, or Blueback on each entry.

## From questions to a file

For each supported target, keep a versioned field definition: setting path, type, label, help, valid choices, and whether it is optional. A schema can establish types and allowed values; a small amount of interface metadata supplies sensible grouping and explanations. Start with deliberately selected fields, rather than trying to render every possible schema construct.

| Setting shape | Form control |
| --- | --- |
| Text or path | Input with a relevant format/path check |
| Fixed set of choices | Select list |
| Boolean | Toggle or explicit yes/no choice |
| Number | Input with type and range checks |
| Repeated objects, such as binds | Add/edit/remove one entry at a time |

The proposed implementation has three parts:

1. **Form:** collect answers, using current values as defaults. Pass values as data; do not build shell commands with `eval`.
2. **Target adapter:** map answers into the application's file, validate the edited values and resulting document, and report any supported-version limitation. Reuse the workspace's existing configuration validation/write path instead of creating a second implementation of it.
3. **Writer:** preview the affected fields, retain unrelated keys, make a private backup, and replace the file atomically. Detect a change made by another process while the form was open instead of overwriting it.

JSON serialization can preserve unrelated values, though whitespace may change. TOML and YAML need a writer that preserves comments and structure where supported. Do not advertise lossless editing until comments, multiline values, arrays, quoted keys, and YAML aliases have been tested. If an existing document uses an unsupported construct, offer an editor or a proposed patch instead of rewriting the entire file. Handle symlinked dotfiles deliberately, with the resolved destination shown.

Keep schemas and form definitions pinned with the release and usable offline. Never fetch schemas or generate forms through an AI service during normal setup. Configuration and cluster details stay on that system. Authentication continues through each agent's existing login/credential mechanism; private values must not leak into previews, logs, or public templates.

## Installation and terminal behavior

Build Gum centrally with the image's pinned package set, record it in `ws tools`, and distribute it with the normal SIF release. No per-cluster package build is needed. If Huh is adopted later, compile its helper in the release builder and ship the executable, not a requirement for a host Go toolchain.

A form tool inside the SIF cannot configure the runtime needed to start that SIF. Keep first-time [Apptainer discovery and validation](runtime-setup.md) in the host installer, using its existing dependencies and plain prompts or explicit options. Once the workspace starts, richer forms can edit the saved setup. Runtime checks must still execute in the appropriate host context.

Forms are explicitly invoked during setup or a configuration change. Updates validate compatibility and reuse saved answers; they should not force users through all the questions again. Daily startup applies the saved settings without discovery or a questionnaire.

Use plain labels, ordinary fonts, keyboard navigation, and a limited-color theme. Provide a simple line-prompt mode and a noninteractive command-line path. Detect a missing terminal and fail with usable instructions instead of hanging on input. Verify resize, cancellation, exit status, and terminal restoration under tmux, a real PuTTY session, and VS Code's terminal. Library support alone does not prove compatibility with our shipped build and the user's terminal settings.

## Delivery sequence

1. Complete remembered runtime setup with a host-only bootstrap path.
2. Package Gum and implement one workspace configuration form against the existing backend. Keep the supported fields small and preserve the current no-form installation path.
3. Add Codex and Claude adapters after validating their fields and scopes against the packaged client versions. Reuse built-in application menus where they already solve the problem.
4. Add named templates for personal HPC tools as those tools enter the workspace. Only then consider general schema-driven forms or a richer Huh application.

Before release, test new files and existing files, unknown-key preservation, invalid input, cancellation, concurrent edits, backups, symlinks, offline use, plain/noninteractive modes, and the actual target applications reading the result. Syntax validity alone does not establish that an application accepts a setting. This document is a design map; `ws configure`, Gum, and a Huh helper are not available in the current image.
