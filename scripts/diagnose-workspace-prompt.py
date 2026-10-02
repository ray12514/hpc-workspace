#!/usr/bin/env python3
"""Trace workspace prompt startup stages without printing site commands or secrets.

Run from the native shell in the repository checkout. The script creates a
private, short-lived rcfile in the current project so the workspace can read
it, enters an instrumented copy of the normal thin shell, and removes it.
"""
import importlib.util
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import sys
import tempfile
import termios
import time


ROOT = Path(__file__).resolve().parents[1]
STAGES = ('start', 'after_site', 'after_module', 'after_hook',
          'after_zoxide', 'before_personal', 'after_personal', 'after_final')
STAGE_PATTERN = re.compile(
    rb'(?m)^__WS_STAGE__ (start|after_site|after_module|after_hook|'
    rb'after_zoxide|before_personal|after_personal|after_final) '
    rb'readonly=(yes|no) deferred=(yes|no) hook=(yes|no) '
    rb'restore=(yes|no) template=(yes|no) storage=(scalar|array|unset) '
    rb'count=([0-9]{1,3})$')
DONE = re.compile(rb'(?m)^__WS_STAGES_DONE__$')

# Each insertion is adjacent to a stable startup boundary, rather than a
# DEBUG trap that could record arbitrary site commands or their arguments.
BOUNDARIES = (
    ('after_site', 'if [[ ${WS_LAYOUT:-core} != thin-v1 ]]; then\n'),
    ('after_module', 'unset WS_SHELL_PREFLIGHT\n'),
    ('after_hook', '# shellcheck disable=SC2016\n'),
    ('after_zoxide', 'if [[ -f /workspace-tools/config/codex-native-key.bash ]]; then\n'),
    ('before_personal', 'if [[ -f "${HOME}/.config/hpc-workspace/bashrc" ]]; then\n'),
    ('after_personal', '# Restore the Bash builtin before composing the final prompt.\n'),
    ('after_final', 'unset WS_SITE_PROMPT_READONLY _ws_prompt_readonly_requested _ws_late_prompt_readonly _ws_readonly_line _ws_prompt_hook_present _ws_prompt_item\n'),
)

PROBE = r'''
_ws_diag_stage() {
    local stage=$1 decl readonly=no deferred=no hook=no restore=no template=no storage=unset count=0 item
    decl=$(declare -p PROMPT_COMMAND 2>/dev/null) || decl=''
    if [[ $decl =~ ^declare\ -[a-zA-Z]*r[a-zA-Z]*\ PROMPT_COMMAND($|=) ]]; then readonly=yes; fi
    if [[ -n $decl ]]; then
        if [[ $decl =~ ^declare\ -[a-zA-Z]*[aA] ]]; then storage=array; else storage=scalar; fi
    fi
    [[ ${_ws_prompt_readonly_requested:-} == 1 ]] && deferred=yes
    for item in "${PROMPT_COMMAND[@]}"; do
        count=$((count + 1))
        [[ $item == _ws_prompt ]] && hook=yes
        [[ $item == _ws_prompt_restore ]] && restore=yes
    done
    [[ ${PS1:-} == *'${_ws_label}'* ]] && template=yes
    printf '\n__WS_STAGE__ %s readonly=%s deferred=%s hook=%s restore=%s template=%s storage=%s count=%s\n' \
        "$stage" "$readonly" "$deferred" "$hook" "$restore" "$template" "$storage" "$count"
}
'''


def instrument_bashrc(source):
    text = PROBE + '\n_ws_diag_stage start\n' + source
    for stage, anchor in BOUNDARIES:
        if text.count(anchor) != 1:
            raise ValueError('workspace Bash configuration changed at ' + stage)
        # Trace immediately before the next startup block. The final marker
        # is placed before cleanup so the deferred flag remains observable.
        text = text.replace(anchor, '_ws_diag_stage ' + stage + '\n' + anchor, 1)
    return text


def instrument_thin_shell(source, rcfile):
    spec = importlib.util.spec_from_file_location('workspace_prompt_candidate',
                                                  str(ROOT / 'scripts/try-workspace-prompt.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.candidate_shell(source, rcfile)


def capture_stages(executable, thin_shell, timeout=65):
    child, master = pty.fork()
    if child == 0:
        options = termios.tcgetattr(0)
        options[3] &= ~(termios.ECHO | termios.ECHONL)
        termios.tcsetattr(0, termios.TCSANOW, options)
        os.execv(executable, [executable, 'enter', '--', '/workspace-tools/bin/bash', str(thin_shell)])
    output = bytearray()
    started = time.monotonic()
    sent = False
    try:
        while time.monotonic() - started < timeout:
            if not sent and time.monotonic() - started >= 2:
                os.write(master, b"printf '\\n__WS_STAGES_DONE__\\n'; exit\n")
                sent = True
            if select.select([master], [], [], .2)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
                if DONE.search(bytes(output).replace(b'\r', b'')):
                    break
                if len(output) > 1024 * 1024:
                    return {}, 'output_limit'
        normalized = bytes(output).replace(b'\r', b'')
        stages = {}
        for match in STAGE_PATTERN.finditer(normalized):
            name = match.group(1).decode('ascii')
            values = [part.decode('ascii') for part in match.groups()[1:]]
            stages[name] = values
        return stages, None if DONE.search(normalized) else 'entry_timeout'
    finally:
        os.close(master)
        try:
            os.kill(child, signal.SIGTERM)
        except OSError:
            pass
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                if os.waitpid(child, os.WNOHANG)[0]:
                    break
            except OSError:
                break
            time.sleep(.05)
        else:
            try:
                os.kill(child, signal.SIGKILL)
            except OSError:
                pass
            try:
                os.waitpid(child, os.WNOHANG)
            except OSError:
                pass


def main():
    if os.environ.get('WS_CONTAINER') == '1' or os.environ.get('WS_LAYOUT') == 'thin-v1':
        print('error=run_from_native_shell', file=sys.stderr)
        return 2
    executable = shutil.which('ws')
    if not executable:
        print('error=ws_unavailable', file=sys.stderr)
        return 1
    spec = importlib.util.spec_from_file_location('workspace_entry_diagnostic',
                                                  str(ROOT / 'scripts/diagnose-workspace-entry.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    facts, error = module.workspace_facts(None)
    if error:
        print('actual_entry=failed')
        print('actual_error=' + re.sub(r'[^A-Za-z0-9_]', '_', error))
    else:
        print('actual_entry=ok')
        for key in ('release', 'visible_label', 'prompt_hook', 'prompt_bridge',
                    'prompt_template', 'prompt_command', 'prompt_storage',
                    'prompt_element_count', 'prompt_element_shapes'):
            if key in facts:
                print('actual_' + key + '=' + facts[key])
        if facts.get('release') != '0.7.3-preview5':
            print('stage_entry=skipped_release_mismatch')
            return 1
    with tempfile.TemporaryDirectory(prefix='.ws-prompt-stage.', dir=Path.cwd()) as temp:
        directory = Path(temp)
        directory.chmod(0o700)
        rcfile = directory / 'bashrc'
        thin_shell = directory / 'thin-shell'
        rcfile.write_text(instrument_bashrc((ROOT / 'image/config/bashrc').read_text()))
        thin_shell.write_text(instrument_thin_shell(
            (ROOT / 'scripts/thin-shell').read_text(), rcfile))
        stages, stage_error = capture_stages(executable, thin_shell)
    for stage in STAGES:
        if stage in stages:
            readonly, deferred, hook, restore, template, storage, count = stages[stage]
            print('stage_{}=readonly:{},deferred:{},hook:{},restore:{},template:{},storage:{},count:{}'.format(
                stage, readonly, deferred, hook, restore, template, storage, count))
        else:
            print('stage_{}=missing'.format(stage))
    print('stage_entry=' + ('ok' if stage_error is None else stage_error))
    return 0 if error is None and stage_error is None and len(stages) == len(STAGES) else 1


if __name__ == '__main__':
    sys.exit(main())
