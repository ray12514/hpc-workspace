# Configure and switch API gateways

The workspace provides named gateway profiles for Codex and Pi. Create one with `ws configure codex` or `ws configure pi`, then use `ws agent codex NAME` or `ws agent pi NAME`. Each connection form accepts a base URL, model ID, optional absolute PEM CA bundle path, and a key entered with hidden input or supplied through an environment variable. It previews changes before saving; cancellation leaves the files untouched. `--plain` uses basic prompts when the terminal cannot run Gum.

## Choose the protocol

Codex profiles use an OpenAI Responses endpoint and a Bearer key. Pi profiles ask for an API protocol: OpenAI Responses, OpenAI Chat Completions, or Anthropic Messages. Choose the protocol implemented by the gateway, not the model's brand. Pi's credential header can be `Authorization: Bearer` or `x-api-key`. A URL change alone cannot translate between protocols. [Pi model configuration](https://pi.dev/docs/latest/models), [Pi custom providers](https://pi.dev/docs/latest/custom-provider)

The managed Codex form does not yet support custom HTTP headers. For a site configuration that requires one, use `ws-codex-native` and the [native Codex guide](restricted-codex.md). Pi's own `~/.pi/agent/models.json` can also define custom headers; use `ws agent pi --native` for a configuration outside the managed form. Pi can use `$HPC_GATEWAY_KEY` from `ws-codex-key-on` in a header value without copying the key into JSON.

## Launch and switch

```bash
ws configure codex team-a
ws configure pi team-a
ws agent codex team-a
ws agent pi team-a
ws agent codex --list
ws agent pi --list
```

Use **Use by default** in a profile's form to select it for new launches of that agent. For one launch with ordinary agent settings, use `ws agent codex --native` or `ws agent pi --native`. Pi also supports its own `/login` and `/model` commands for built-in providers, including OpenAI and Anthropic; those accounts remain independent from Codex. [Pi authentication](https://pi.dev/docs/latest/providers)

A managed profile owns its route and model. Pass unrelated native arguments after `--`; select `--native` before using native provider, model, or credential options. Start a fresh agent process after changing a connection or rotating a key.

For a gateway that needs a private or site CA, enter that gateway's readable PEM file path in **Edit connection**. The workspace stores the path with the profile and sets `CODEX_CA_CERTIFICATE` only for that Codex launch, or `NODE_EXTRA_CA_CERTS` only for that Pi launch. Leave it blank to use workspace defaults; an edited profile with a blank path clears an inherited agent-specific CA setting for that launch before the Pi wrapper applies its usual workspace CA fallback. Older profiles that have not been edited retain their previous inherited behavior until reviewed. Changing vendors or endpoints is a good time to review both the key and CA path. This does not set `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, or `REQUESTS_CA_BUNDLE` in your login shell. The CA file itself stays at its local path and must be readable on the node where the agent runs.

## Credentials and files

| Contents | Default location |
| --- | --- |
| Profile names and defaults | `~/.config/hpc-workspace/agents.json` |
| Private credential source | `~/.config/hpc-workspace/credentials/TOOL-NAME.json` |
| Gateway CA path | Same private credential source, selected per gateway |
| Codex native profile | `~/.codex/ws-NAME.config.toml` |
| Pi provider entries | `~/.pi/agent/models.json`, under `ws-NAME` |
| Private backups of replaced files | `~/.config/hpc-workspace/backups/` |

`WS_CONFIG_DIR`, `CODEX_HOME`, and `PI_CODING_AGENT_DIR` select alternate locations. New files and backups use mode 600. A stored key is a private plaintext file, not encryption or an OS keychain. Stored keys enter only the selected agent's child environment and do not appear in command arguments or the parent shell. An environment-backed profile stores only the variable name; that variable must already be available to the launching shell. Keep real keys out of the repository, chat, project templates, and shell history.

The Pi provider entry references `$WS_SELECTED_PI_KEY`; the workspace supplies that variable only to the selected Pi process. If Pi has a stored credential for the same `ws-NAME` provider, remove it before using the workspace profile so it cannot take precedence. Pi's native `auth.json` may contain other provider credentials and remains untouched.

Choose **Rotate key** to replace a stored key without changing the endpoint or model. Choose **Edit connection** to change the protocol, credential source, or other managed fields. Direct changes to a managed provider require a review through the form before launch. Saved user and project agent settings otherwise remain in place. API calls and private acceptance results stay on the cluster.

Pi runs generated commands with the launching user's permissions. Its project trust prompt controls project resources but is not a command sandbox. Review the files and credentials exposed to a Pi session. [Pi security guide](https://pi.dev/docs/latest/security)

`ws configure workspace` edits extra filesystem binds and the optional scheduler default. Native `sbatch` and `qsub` do not require that default.
