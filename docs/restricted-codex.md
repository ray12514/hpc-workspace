# Codex with a site-provided gateway configuration

Keep the native configuration that already works on your system. **The 0.7.1 workspace form does not yet support your custom authentication header.** Its Codex adapter uses bearer authentication and rejects custom header overrides. Editing a form-managed `ws-NAME.config.toml` is therefore not a workaround for this setup.

Inside the workspace, use:

```bash
nvim "${CODEX_HOME:-$HOME/.codex}/config.toml"
ws agent codex --native
```

`--native` still starts the packaged Codex; it uses ordinary Codex settings and authentication instead of workspace gateway management. It does not load a key from `~/.config/hpc-workspace/credentials/codex-NAME.json`. Updating the workspace preserves your native configuration.

## Map the required fields

The [example TOML](../examples/codex-restricted.config.toml) is an outline with deliberately unusable placeholders. Merge only needed fields into the working local file. Private URLs, keys, and certificate paths remain on the cluster.

| Requirement | Placement |
| --- | --- |
| Model and provider identifier | Top-level `model` and `model_provider` |
| Disable startup update check | Top-level `check_for_update_on_startup = false` |
| Request approval; read-only sandbox | Top-level `approval_policy = "on-request"` and `sandbox_mode = "read-only"` |
| Medium reasoning | Top-level `model_reasoning_effort = "medium"`, if supported by the selected model |
| Provider label, endpoint, Responses protocol | `name`, `base_url`, `wire_api = "responses"` inside `[model_providers.ID]` |
| Raw key in a custom header | Provider `env_http_headers = { "HEADER-NAME" = "ENV_VARIABLE_NAME" }` |
| Provider without OpenAI sign-in | Provider `requires_openai_auth = false`, when this matches the gateway |
| Provider WebSocket transport disabled | Provider `supports_websockets = false` |
| CA bundle | `CODEX_CA_CERTIFICATE` environment variable containing a local PEM bundle path |

These mappings follow the [official OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) and [custom-provider header examples](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers). Site-managed requirements still apply; this file does not override them.

Two dictated names still need local confirmation: **“webhooks disabled”** could mean web search or a hook setting; those are different. The example leaves `web_search` commented until that is resolved. Likewise, replace the example header with the exact required spelling; do not assume `X-Access` and `X-Access-Key` are interchangeable. No secret is needed to confirm these names.

In the bundled **Codex 0.155.1**, `codex features list` reports `responses_websockets` and `responses_websockets_v2` as **removed**. The example retains their false values for comparison with the existing site template, but they are not effective transport controls. The current provider setting is shown separately. Keep a locally approved template authoritative when comparing versions.

## Supply the key and certificate

Use the credential mechanism already approved on the system. `env_http_headers` takes the **name** of a variable whose value will become the header; it does not take a literal API key. Do not add a `Bearer ` prefix unless that header's specification requires it. `env_key` is the separate bearer-authentication path.

For a temporary manual test in Bash, these commands prompt without putting the typed key in shell history:

```bash
IFS= read -r -s -p 'Gateway key: ' HPC_GATEWAY_KEY
printf '\n'
export HPC_GATEWAY_KEY
export CODEX_CA_CERTIFICATE='/replace/with/local/approved-ca-bundle.pem'
ws agent codex --native
unset HPC_GATEWAY_KEY
```

Use a normal interactive shell with tracing disabled. The variable is available to children of that shell until unset; this is not persistent encrypted storage. Existing site credential helpers can supply it instead. Rotate through that source, then launch a new Codex process from a shell with the refreshed value. An older tmux pane or running agent does not automatically acquire the new key.

`CODEX_CA_CERTIFICATE` selects a PEM CA bundle; Codex falls back to `SSL_CERT_FILE` when it is absent. Set the path before launch. A persistent, non-secret path can go in your personal workspace Bash settings if appropriate. The certificate must be readable on both login and compute nodes. See [OpenAI authentication and custom CA bundles](https://learn.chatgpt.com/docs/auth#custom-ca-bundles).

First confirm the version with `codex --version`. Then test a small approved, non-sensitive request locally on a login node and again after entering a workspace on a compute node. A version check or valid TOML alone does not establish gateway connectivity. Local security policy, proxy settings, certificates, and outbound access still govern those requests.

## Next form extension

This is a **plan**, not additional 0.7.1 form functionality:

1. Add an explicit **custom header** authentication mode with an exact header name and a stored-key or environment-variable source. Keep rotation and endpoint/credential binding; never show the key in a preview.
2. Add the required policy, model, transport, and CA controls with the values above visible. Preserve site settings and unrelated TOML instead of resetting them during a provider edit. Scope the CA choice to the launched process.
3. Support importing a working native configuration for review. Display the resolved file and changed fields; leave unsupported constructs intact and explain them. Validate against the bundled client version, including removed options.
4. Exercise save/cancel, two gateways, key rotation, existing configuration, and actual custom-header requests against a synthetic local gateway before shipping. Private site acceptance stays on the cluster.

Skills are a separate follow-up. The thin image bundles skills but does not yet activate that bundle automatically; existing personal links may point to older snapshots. Add version visibility and persistent activation while preserving personal skills. Loading a skill must not change the chosen sandbox or approval policy. See [skills status](skills.md).
