# Codex with a site-provided gateway configuration

Keep the native configuration that already works on your system. **The 0.7 workspace form does not yet support your custom authentication header.** Its Codex adapter uses bearer authentication and rejects custom header overrides. Editing a form-managed `ws-NAME.config.toml` is therefore not a workaround for this setup.

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

### Save once, load on demand

The new workspace image includes a small [Bash helper](../image/config/codex-native-key.bash) in every workspace shell. Keep the non-secret CA path in your personal workspace Bash settings:

```bash
nvim "$HOME/.config/hpc-workspace/bashrc"
```

Add these lines to that Bash file, replacing the CA path with the actual approved PEM bundle location:

```bash
export CODEX_CA_CERTIFICATE='/actual/site/ca-bundle.pem'
```

In the current workspace shell, load the CA path and save the key through a hidden prompt **once**:

```bash
source "$HOME/.config/hpc-workspace/bashrc"
ws-codex-key-save
```

The helper stores the key in `~/.config/hpc-workspace/credentials/native-codex.key`, with file mode 600 and directory mode 700. It never writes the key into the Bash settings, the repository, a command argument, or shell history. This hides entry from the terminal; it does not isolate the key from other processes running as your account. The file is plaintext and remains readable to your account and system administrators; use the site's approved secret manager instead if it requires one.

In each **agents** shell where you want to start Codex, run one command. If that pane was already open before the CA path changed, first run `source "$HOME/.config/hpc-workspace/bashrc"` there once:

```bash
ws-codex-native
```

`ws-codex-native` loads the saved `HPC_GATEWAY_KEY` in a child shell and starts `ws agent codex --native`; the key is not left exported in the agents pane when Codex exits. Set your native Codex provider's `env_http_headers` variable name to `HPC_GATEWAY_KEY` when using this helper. The older `ws-codex-key-on`, `ws agent codex --native`, `ws-codex-key-off` sequence remains available if you need the key in that shell. A running agent and other existing tmux panes keep their own environments; opening a new pane loads the CA path automatically. Do not print the variable or enable shell tracing while working with it.

`CODEX_CA_CERTIFICATE` selects a PEM CA bundle; Codex falls back to `SSL_CERT_FILE` when it is absent. Set the path before launch. A persistent, non-secret path can go in your personal workspace Bash settings if appropriate. The certificate must be readable on both login and compute nodes. See [OpenAI authentication and custom CA bundles](https://learn.chatgpt.com/docs/auth#custom-ca-bundles).

### Keep the CA setting across workspace shells

Inside the workspace, open your personal Bash settings:

```bash
nvim ~/.config/hpc-workspace/bashrc
```

If you are not using the helper above, add this line with your actual, locally approved PEM bundle path:

```bash
export CODEX_CA_CERTIFICATE='/replace/with/local/approved-ca-bundle.pem'
```

The path is configuration, not an API key. The bundle stays on the system and must be accessible through the workspace's mounts. These personal settings survive workspace updates and load in new workspace Bash shells, including new tmux panes. To apply the edit to the current pane, then launch a new client:

```bash
source ~/.config/hpc-workspace/bashrc
ws agent codex --native
```

A running Codex process does not receive later exports; exit that client normally before relaunching it. Other existing panes keep their own environments until they source the file or start a new shell.

The ordinary Codex file is `${CODEX_HOME:-$HOME/.codex}/config.toml`, but its `[shell_environment_policy.set]` table controls **commands launched by Codex**, not Codex's own HTTPS connection. A CA export placed only in that table cannot establish the client's initial connection. The TOML `otel.*.tls.ca-certificate` fields configure telemetry exporters, not the model provider. See the [shell environment policy](https://learn.chatgpt.com/docs/config-file/config-advanced#shell-environment-policy) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

An offline HTTPS test of the packaged **Codex 0.155.1** confirmed that either `CODEX_CA_CERTIFICATE` or `SSL_CERT_FILE` in the launch environment establishes trust. `CURL_CA_BUNDLE`, `REQUESTS_CA_BUNDLE`, and `NODE_EXTRA_CA_CERTS`, tested individually, did not establish trust for Codex's own model request. Other tools or commands an agent launches may still need their own certificate settings; this is not a reason to remove working site settings. The test used a synthetic CA, not a private gateway; see [validation](validation.md#codex-ca-diagnosis-and-session-entry-clarification).

First confirm the version with `codex --version`. Then test a small approved, non-sensitive request locally on a login node and again after entering a workspace on a compute node. A version check or valid TOML alone does not establish gateway connectivity. Local security policy, proxy settings, certificates, and outbound access still govern those requests.

## Next form extension

This is a **plan**, not functionality added by the 0.7.1/0.7.2 patches:

1. Add an explicit **custom header** authentication mode with an exact header name and a stored-key or environment-variable source. Keep rotation and endpoint/credential binding; never show the key in a preview.
2. Add the required policy, model, transport, and CA controls with the values above visible. Preserve site settings and unrelated TOML instead of resetting them during a provider edit. Scope the CA choice to the launched process.
3. Support importing a working native configuration for review. Display the resolved file and changed fields; leave unsupported constructs intact and explain them. Validate against the bundled client version, including removed options.
4. Exercise save/cancel, two gateways, key rotation, existing configuration, and actual custom-header requests against a synthetic local gateway before shipping. Private site acceptance stays on the cluster.

Skill activation is included starting with preview7. It preserves personal skills and does not change the chosen sandbox or approval policy. See [skills status](skills.md).
