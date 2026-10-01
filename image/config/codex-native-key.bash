# Loaded by the shared workspace Bashrc for a custom-header Codex gateway.
# Keep this file free of credentials. The actual key is stored outside the image.

_ws_codex_key_file() {
    printf '%s' "$HOME/.config/hpc-workspace/credentials/native-codex.key"
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
