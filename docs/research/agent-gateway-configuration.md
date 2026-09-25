# Claude Code gateway configuration

Reviewed 25 September 2026 for the workspace's bundled **Claude Code 2.1.280**. **Status: research for the first guided implementation, not a gateway compatibility test.** Sources are current primary Anthropic documentation; those pages are not frozen to 2.1.280. No private settings or credentials were read, and no model API requests were made. Codex is outside this note's scope.

**Recommendation:** maintain named gateway profiles in workspace configuration and launch Claude with the selected endpoint, credential source, and settings overlay. Key rotation should update the profile's credential source without requiring a configuration-file swap. Claude provides the required launch controls, but the reviewed documentation does not establish a native arbitrary-gateway profile registry.

## Endpoint and credential fields

| Field | Documented meaning |
| --- | --- |
| `ANTHROPIC_BASE_URL` | Overrides the API endpoint for a proxy or gateway. |
| `ANTHROPIC_AUTH_TOKEN` | Supplies the credential for `Authorization: Bearer …`; the prefix is added by Claude. |
| `ANTHROPIC_API_KEY` | Supplies the `X-Api-Key` header. |
| `ANTHROPIC_CUSTOM_HEADERS` | Additional `Name: Value` headers, separated by newlines. |

These are environment variables, including when placed inside a settings file's `env` object. They are not top-level JSON settings keys. [Environment variables](https://code.claude.com/docs/en/env-vars)

An Anthropic-compatible gateway must implement the Messages API, including `/v1/messages`, and pass the necessary `anthropic-version` and `anthropic-beta` headers. An OpenAI-compatible endpoint alone is insufficient. Gateway operators must account for evolving request fields and streaming behavior. Anthropic's gateway documentation does not support routing Claude Code to non-Claude models. [Gateway protocol](https://code.claude.com/docs/en/llm-gateway-protocol), [supported gateways](https://code.claude.com/docs/en/llm-gateway)

Setting only `ANTHROPIC_BASE_URL` does not select new credentials: a saved subscription login can remain active while requests go through that URL. The workspace should require the chosen profile's credential to be available before launching. [Gateways and subscriptions](https://code.claude.com/docs/en/llm-gateway#subscriptions-and-gateways)

The gateway decides which credential header it accepts. In interactive Claude, an API key requires one-time approval before replacing a subscription; in `-p` mode it is used whenever present. A bearer token takes precedence immediately. [Gateway credential selection](https://code.claude.com/docs/en/llm-gateway-connect#conflicts-with-an-existing-login)

## Settings and authentication precedence

`claude --settings PROFILE.json` is an **overlay**, not an exclusive alternate configuration. Supplied keys override ordinary settings, but omitted keys keep their lower-level values. The order is managed settings, command-line settings, project-local settings, shared project settings, then user settings. Lists generally combine, with documented exceptions. [Settings precedence](https://code.claude.com/docs/en/settings#settings-precedence)

`--setting-sources` selects which ordinary sources load: `user`, `project`, and `local`. It should not be used casually to discard project permissions or policy. Neither that flag nor `--settings` establishes a complete credential-isolation boundary. [CLI reference](https://code.claude.com/docs/en/cli-reference)

Normally, settings-file `env` values replace the same variables inherited from the shell. Consequently, sanitizing only the launch environment does not prevent loaded settings from restoring an old token, endpoint, or provider selector. Settings can set variables but cannot remove them; the documented empty-string workaround applies to provider selectors such as `CLAUDE_CODE_USE_VERTEX`. Removing an `env` entry does not unset it in an already running session. Use a new process for a provider switch. [Environment precedence](https://code.claude.com/docs/en/env-vars#precedence)

The documented credential order, after selecting a provider, is cloud-provider credentials, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `apiKeyHelper`, `CLAUDE_CODE_OAUTH_TOKEN`, Anthropic profile/federation credentials, then subscription login. Profile-versus-login ranking has additional rules. A saved **Claude apps gateway** login is a separate provider selection that outranks this chain. Managed login restrictions can also prevent custom credentials. Ordinary gateway tokens must not be confused with that gateway sign-in feature. [Authentication precedence](https://code.claude.com/docs/en/authentication#authentication-precedence)

Do not generalize “empty means unset” to every credential path. Anthropic's SDK federation reference explicitly warns that an empty `ANTHROPIC_API_KEY` can still select API-key authentication. Removing unused variables and testing the exact Claude launch path is preferable to assuming empty credential values are universally safe. [Federation credential precedence](https://platform.claude.com/docs/en/manage-claude/wif-reference#credential-precedence)

## Rotation and named profiles

The top-level JSON setting `apiKeyHelper` names a shell command that prints only the current credential to stdout. Claude sends its output in both `Authorization` and `x-api-key`. The default cache lifetime is five minutes, configurable through `CLAUDE_CODE_API_KEY_HELPER_TTL_MS`. This is a documented option for vault-backed or rotating credentials; it is not an immediate-refresh guarantee. Existing static auth variables outrank it. [Rotating gateway credentials](https://code.claude.com/docs/en/llm-gateway-connect#rotate-credentials-with-apikeyhelper), [authentication](https://code.claude.com/docs/en/authentication#credential-management)

There are native **Anthropic profiles**, selected with `ANTHROPIC_PROFILE` or an active/default profile. Their documented use is Anthropic OAuth or workload identity federation. Profile files can contain `base_url`, but that does not establish support for arbitrary static gateway-token profiles. Keep workspace gateway names distinct from this native credential mechanism. [Claude profile authentication](https://code.claude.com/docs/en/authentication#anthropic-profiles-and-federation-credentials), [profile file format](https://platform.claude.com/docs/en/manage-claude/wif-reference#profile-configuration-file)

`CLAUDE_CONFIG_DIR` moves Claude's user settings, session history, and plugins; it supports accounts kept side by side. It is broader than choosing a gateway and can be set in the launch environment. [Configuration directory](https://code.claude.com/docs/en/env-vars) On Linux, saved login credentials are also stored under that directory; macOS Keychain entries are keyed to it. Do not edit `.credentials.json` to implement gateway selection. [Credential storage](https://code.claude.com/docs/en/authentication#credential-management)

## First implementation

These are workspace design recommendations derived from the behavior above:

- Save each profile's name, endpoint, explicit authentication mode, credential reference, and optional model. Resolve the credential reference in workspace code; do not assume Claude expands an environment-variable name embedded in JSON.
- Keep credential material out of shared project settings, command-line arguments, previews, and logs. If stored locally, use a private file. Rotating a stored key updates that profile's credential, leaving its endpoint and name unchanged.
- Require a nonempty selected credential and fail before launch if it is unavailable. Never fall back silently to another profile, helper, or saved login.
- Construct the selected child environment and settings together. Account for stale auth variables, cloud-provider selectors, custom headers, model overrides, and loaded settings that can reintroduce them. Preserve managed policy; report a conflicting managed route instead of claiming the profile overrides it.
- Start a fresh Claude process after switching profiles or replacing a static key. Offer `apiKeyHelper` later where automatic refresh is needed, with explicit ownership of the helper command and tests for missing or failed output.
- Show the selected endpoint and credential-source name, never the secret. Verify effective configuration through Claude's `/status` when testing the integration. Do not treat a successful settings-file write as proof of routing.

## Bundled-version limitation

Upstream **2.1.281** fixes `--setting-sources` not being forwarded to spawned teammates, `/bg`, `claude agents` sessions, and `--worktree --tmux`. The bundled 2.1.280 predates that fix. Therefore, do not advertise settings-source exclusion as isolation for child or background sessions on this release. The first implementation needs direct launch tests and an explicit scope for background-session support; a later upgrade needs its own regression checks. [Upstream 2.1.281 changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21281)
