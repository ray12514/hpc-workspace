# Configure and switch API gateways

The 0.7 thin workspace adds Gum forms for named agent gateway profiles. Keep several connections, change their settings, rotate a key, and choose a default without manually swapping files. Start a fresh agent process after changing a connection or credential; a running process keeps its launch settings.

## First connection

Inside the workspace:

```bash
ws configure codex
# Or:
ws configure claude
```

Choose **Add a gateway**, name it (for example `team-a`), and enter the endpoint and model supplied by its operator. The form shows destination files and previews changes before Save. Cancelling does not save. `ws configure --plain` uses basic prompts; `TERM=dumb` selects that mode automatically.

Choose a **stored key**, entered with hidden input, or a **gateway-specific environment variable** such as `TEAM_A_API_KEY`. The variable option stores its name, not its value. Supply that variable through the site's normal approved mechanism. Real keys belong on the system, outside this repository, chat, project templates, and shell command history.

Codex uses an **OpenAI Responses-compatible** endpoint. Claude uses an **Anthropic Messages-compatible** endpoint; choose the Bearer token or API-key header that gateway requires. Changing a URL does not translate between protocols. This first adapter does not configure cloud-provider authentication, extra headers/query parameters, federation, or automatic credential refresh. [Codex providers](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers), [Claude gateway protocol](https://code.claude.com/docs/en/llm-gateway-protocol)

## Launch and switch

```bash
ws agent codex team-a
ws agent claude team-a
ws agent codex --list
ws agent claude --list

# Native agent arguments follow --:
ws agent codex team-a -- --model another-model
```

Create `team-b` through the same form, then launch it by name. There is no need to prepare two YAML files yourself. Each connection gets its own native profile and credential source; selecting one leaves the others intact.

To make one the normal choice, open its form and choose **Use by default**, then Save:

```bash
ws configure codex team-a
codex
```

The same default-selection workflow applies to Claude. It affects new launches of the packaged agent. To use ordinary agent configuration for one invocation:

```bash
ws agent codex --native
ws agent claude --native
```

The form also offers **Use ordinary agent settings** to clear a saved default. Help, version, and login/logout commands keep their ordinary behavior. Additional native profile/remote/settings-overlay options require `--native`; a managed gateway launch owns its connection settings.

## Rotate or edit

```bash
ws configure codex team-a
ws configure claude team-a
```

Choose **Rotate key** to replace a stored key without re-entering the endpoint or model. Choose **Edit connection** to change those fields, the credential source, or Claude's header mode. Existing values appear in the form; stored keys never appear in its preview. For an environment-backed credential, update the variable through its existing source and start a new agent process.

If a credential is absent, that profile fails to launch with an actionable message. It does not silently use another profile's key. Editing an endpoint directly in a managed native file requires reviewing its credential binding through the form before launching again.

## Files and scope

| Contents | Default location |
| --- | --- |
| Profile names and defaults | `~/.config/hpc-workspace/agents.json` |
| Private credential source | `~/.config/hpc-workspace/credentials/TOOL-NAME.json` |
| Codex native profile | `~/.codex/ws-NAME.config.toml` |
| Claude native preferences overlay | `~/.claude/workspace-profiles/NAME.json` |
| Private copies of replaced files | `~/.config/hpc-workspace/backups/` |

`WS_CONFIG_DIR`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` select corresponding alternate locations. The form shows resolved destinations and preserves symlinked dotfiles. New files and backups use mode 600. Backups can contain old credentials and remain local. Stored keys use private files, not encryption or an OS keychain.

The adapters edit their named profile files. Ordinary user/project settings remain in place. Unrelated fields in managed profiles are retained; TOMLKit preserves TOML comments. Saving checks for intervening file changes and rolls back partial writes where its own contents are still present.

Codex receives the selected key in its child environment and loads the native profile with `--profile`. Claude receives a private per-process settings overlay because `settings.env` can override inherited environment values. That temporary file is removed on normal exit and handled termination; forced kills or node failure can leave private files for system cleanup. Keys do not appear in command-line arguments or the parent interactive shell.

Site-managed agent policy still takes precedence. These profiles cover direct foreground launches. Saved enterprise gateway sign-in, managed routing, spawned agents, and background sessions require separate site checks; an edited file does not establish gateway compatibility. The [research note](research/agent-gateway-configuration.md) records Claude precedence and bundled-version limits. API calls and private acceptance results stay on the cluster.

## Workspace settings

`ws configure workspace` edits extra filesystem binds and the optional scheduler default through the existing workspace configuration. Native `sbatch`/`qsub` do not require that default. Inspector import remains available through `ws init` and `ws refresh`; the form does not rerun Inspector.

This release provides these selected forms. Arbitrary YAML/JSON/TOML schemas, broader agent preferences, and automatic credential refresh remain future work.
