# Loaded by the shared workspace Bashrc for a custom-header Codex gateway.
# Keep this file free of credentials. The actual key is stored outside the image.

_ws_codex_key_file() {
    printf '%s' "$HOME/.config/hpc-workspace/credentials/native-codex.key"
}

_ws_codex_ca_file() {
    printf '%s' "$HOME/.config/hpc-workspace/credentials/native-codex.ca-path"
}

ws-codex-key-save() (
    set +x
    umask 077
    local key_file key_dir temporary secret
    key_file=$(_ws_codex_key_file)
    key_dir=${key_file%/*}
    mkdir -p -- "$key_dir" || return
    chmod 700 "$key_dir" || return
    IFS= read -r -s -p 'Codex gateway key: ' secret || return
    printf '\n' >&2
    if [[ -z $secret ]]; then
        printf 'No key saved: input was empty.\n' >&2
        return 1
    fi
    temporary=$(mktemp "$key_dir/.native-codex.XXXXXXXX") || return
    if ! printf '%s\n' "$secret" > "$temporary" || ! chmod 600 "$temporary" ||
            ! mv -f "$temporary" "$key_file"; then
        rm -f "$temporary"
        return 1
    fi
    printf 'Codex gateway key saved in a private file.\n'
)

ws-codex-key-on() {
    local key_file mode secret status=0 traced=0
    case $- in *x*) traced=1; set +x;; esac
    key_file=$(_ws_codex_key_file)
    if [[ ! -f $key_file || -L $key_file || ! -r $key_file ]]; then
        printf 'No readable private key file. Run ws-codex-key-save first.\n' >&2
        status=1
    else
        mode=$(stat -c %a "$key_file" 2>/dev/null) || mode=$(stat -f %Lp "$key_file" 2>/dev/null)
        if [[ ! $mode =~ ^[0-7]+$ ]] || (( (8#$mode & 077) != 0 )); then
            printf 'Key file permissions are too open; use chmod 600 on the file.\n' >&2
            status=1
        elif ! IFS= read -r secret < "$key_file" || [[ -z $secret ]]; then
            printf 'Key file is empty or unreadable.\n' >&2
            status=1
        else
            export HPC_GATEWAY_KEY=$secret
            printf 'Codex gateway key is available in this shell.\n'
        fi
    fi
    unset secret
    (( traced )) && set -x
    return "$status"
}

ws-codex-key-off() {
    unset HPC_GATEWAY_KEY
    printf 'Codex gateway key removed from this shell.\n'
}

ws-codex-ca-save() (
    set +x
    umask 077
    local ca_file ca_dir ca_path temporary
    ca_file=$(_ws_codex_ca_file)
    ca_dir=${ca_file%/*}
    IFS= read -r -p 'Codex CA PEM path (blank for workspace defaults): ' ca_path || return
    if [[ -n $ca_path ]]; then
        if [[ $ca_path != /* || ! -f $ca_path || ! -r $ca_path ]] ||
                ! grep -Eq -- '-----BEGIN (TRUSTED )?CERTIFICATE-----' "$ca_path"; then
            printf 'Enter an absolute, readable PEM CA file with CERTIFICATE blocks.\n' >&2
            return 1
        fi
    else
        ca_path=-
    fi
    mkdir -p -- "$ca_dir" || return
    chmod 700 "$ca_dir" || return
    temporary=$(mktemp "$ca_dir/.native-codex-ca.XXXXXXXX") || return
    if ! printf '%s\n' "$ca_path" > "$temporary" || ! chmod 600 "$temporary" ||
            ! mv -f "$temporary" "$ca_file"; then
        rm -f "$temporary"
        return 1
    fi
    printf 'Codex CA choice saved for native launches.\n'
)

ws-codex-native-setup() {
    ws-codex-key-save && ws-codex-ca-save
}

# Load the saved key only for one native Codex launch. The parent pane keeps
# its environment, so there is no cleanup step after the client exits.
ws-codex-native() (
    set +x
    local ca_file ca_path mode
    ca_file=$(_ws_codex_ca_file)
    if [[ -e $ca_file || -L $ca_file ]]; then
        if [[ ! -f $ca_file || -L $ca_file || ! -r $ca_file ]]; then
            printf 'Codex CA choice is unreadable. Run ws-codex-ca-save again.\n' >&2
            return 1
        fi
        mode=$(stat -c %a "$ca_file" 2>/dev/null) || mode=$(stat -f %Lp "$ca_file" 2>/dev/null)
        if [[ ! $mode =~ ^[0-7]+$ ]] || (( (8#$mode & 077) != 0 )); then
            printf 'Codex CA choice permissions are too open; use chmod 600 on the file.\n' >&2
            return 1
        fi
        IFS= read -r ca_path < "$ca_file" || return
        if [[ $ca_path == - ]]; then
            unset CODEX_CA_CERTIFICATE
        elif [[ $ca_path == /* && -f $ca_path && -r $ca_path ]] &&
                grep -Eq -- '-----BEGIN (TRUSTED )?CERTIFICATE-----' "$ca_path"; then
            export CODEX_CA_CERTIFICATE=$ca_path
        else
            printf 'Saved Codex CA file is unavailable here. Run ws-codex-ca-save again.\n' >&2
            return 1
        fi
    fi
    ws-codex-key-on >/dev/null || return
    ws agent codex --native "$@"
)
