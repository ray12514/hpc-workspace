#!/usr/bin/env python3
"""Compare a native shell with a fresh interactive workspace without printing secrets."""
import argparse
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import sys
import termios
import time


ANSI = re.compile(rb'\x1b\[[0-9;]*[A-Za-z]')
ALLOWED = re.compile(r'^[A-Za-z0-9._/,\-]+$')
START_LINE = re.compile(rb'(?m)^__WS_DIAG_START__$')
END_LINE = re.compile(rb'(?m)^__WS_DIAG_END__$')


def safe(value):
    return value if value and ALLOWED.match(value) else 'unavailable'


def file_details(path):
    try:
        info = path.stat()
    except OSError:
        return 'unavailable'
    return '{},{},{:o}'.format(info.st_uid, info.st_gid, info.st_mode & 0o777)


def config_path(explicit):
    if explicit:
        return Path(explicit)
    root = Path('/etc/ssh')
    choices = [root / 'config.d/50-redhat.conf',
               root / 'ssh_config.d/50-redhat.conf',
               root / 'ssh_config.d/05-redhat.conf']
    if root.is_dir():
        choices.extend(sorted(root.glob('*/*.conf')))
    for path in choices:
        if path.name.lower().endswith('redhat.conf') and path.exists():
            return path
    return None


def workspace_command(path):
    # No hook, key, full prompt, SSH config content, or general environment is printed.
    commands = [
        "printf '\\n__WS_DIAG_START__\\n'",
        "printf 'release=%s\\n' \"${WS_RELEASE:-unset}\"",
        "printf 'layout=%s\\n' \"${WS_LAYOUT:-unset}\"",
        "printf 'container=%s\\n' \"${WS_CONTAINER:-unset}\"",
        "printf 'uid=%s\\n' \"$(id -u)\"",
        "printf 'interactive=%s\\n' \"$([[ $- == *i* ]] && echo yes || echo no)\"",
        "declare -F _ws_prompt >/dev/null && echo prompt_function=present || echo prompt_function=missing",
        "[[ ${PROMPT_COMMAND[*]:-} == *'_ws_prompt'* ]] && echo prompt_hook=present || echo prompt_hook=missing",
        "[[ ${PS1:-} == *'${_ws_label}'* ]] && echo prompt_template=workspace || echo prompt_template=other",
        "[[ ${_ws_label+x} == x ]] && echo prompt_label_value=set || echo prompt_label_value=unset",
        "readonly -p | grep -Eq '^declare -[[:alpha:]]*r[[:alpha:]]* PROMPT_COMMAND(=|$)' && echo prompt_command=readonly || echo prompt_command=writable",
        "[[ -f ${HOME}/.config/hpc-workspace/bashrc ]] && echo personal_bashrc=present || echo personal_bashrc=missing",
        "[[ ${NO_COLOR+x} == x || ${WS_COLOR:-auto} == never || ${TERM:-dumb} == dumb ]] && echo prompt_color=disabled || echo prompt_color=eligible",
        "printf 'ssh_kind=%s\\n' \"$(type -t ssh 2>/dev/null || echo missing)\"",
        "printf 'ssh_path=%s\\n' \"$(type -P ssh 2>/dev/null || echo missing)\"",
        "printf 'scp_kind=%s\\n' \"$(type -t scp 2>/dev/null || echo missing)\"",
        "printf 'scp_path=%s\\n' \"$(type -P scp 2>/dev/null || echo missing)\"",
    ]
    if path is not None:
        # Quoting a path is the only dynamic shell input. Do not read its content.
        import shlex
        quoted = shlex.quote(str(path))
        commands.append("printf 'ssh_config_owner=%s\\n' \"$(stat -Lc '%u,%g,%a' -- " + quoted + " 2>/dev/null || echo unavailable)\"")
    commands.extend(["printf '__WS_DIAG_END__\\n'", 'exit'])
    return '; '.join(commands) + '\n'


def workspace_facts(path, timeout=50):
    executable = shutil.which('ws')
    if not executable:
        return None, 'ws unavailable in the native shell'
    child, master = pty.fork()
    if child == 0:
        options = termios.tcgetattr(0)
        options[3] &= ~(termios.ECHO | termios.ECHONL)
        termios.tcsetattr(0, termios.TCSANOW, options)
        os.execv(executable, [executable, 'enter'])
    output = bytearray()
    started = time.monotonic()
    sent = False
    try:
        while time.monotonic() - started < timeout:
            if not sent and time.monotonic() - started >= 1:
                os.write(master, workspace_command(path).encode('utf-8'))
                sent = True
            if select.select([master], [], [], .2)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
                if END_LINE.search(bytes(output).replace(b'\r', b'')):
                    break
                if len(output) > 1024 * 1024:
                    return None, 'workspace output exceeded diagnostic limit'
        normalized = bytes(output).replace(b'\r', b'')
        start = START_LINE.search(normalized)
        end = END_LINE.search(normalized)
        if start is None or end is None or end.start() <= start.end():
            return None, 'workspace did not reach diagnostic marker within {} seconds'.format(timeout)
        before = normalized[:start.start()]
        body = normalized[start.end():end.start()]
        # The final prompt line can be on a second line after the context line.
        tail = ANSI.sub(b'', before).rstrip(b'\r\n')[-400:]
        visible = 'yes' if b'ws:' in tail else 'no'
        facts = {'visible_label': visible}
        for raw in body.replace(b'\r', b'').split(b'\n'):
            if b'=' not in raw:
                continue
            key, value = raw.split(b'=', 1)
            key = key.decode('ascii', 'ignore')
            if key in ('release', 'layout', 'container', 'uid', 'interactive',
                       'prompt_function', 'prompt_hook', 'prompt_template',
                       'prompt_label_value', 'prompt_command', 'personal_bashrc',
                       'prompt_color', 'ssh_kind', 'ssh_path', 'scp_kind',
                       'scp_path', 'ssh_config_owner'):
                facts[key] = safe(value.decode('utf-8', 'replace').strip())
        return facts, None
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
            # A site process stuck in uninterruptible I/O must not hang this report.
            try:
                os.waitpid(child, os.WNOHANG)
            except OSError:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-config', help='Exact config file named by the SSH error, if auto-detection misses it')
    args = parser.parse_args(argv)
    if os.environ.get('WS_CONTAINER') == '1' or os.environ.get('WS_LAYOUT') == 'thin-v1':
        parser.error('run from a native shell outside the workspace')
    path = config_path(args.ssh_config)
    print('native_uid={}'.format(os.getuid()), flush=True)
    print('native_ssh_path={}'.format(safe(shutil.which('ssh'))), flush=True)
    print('native_scp_path={}'.format(safe(shutil.which('scp'))), flush=True)
    print('ssh_config_path={}'.format(str(path) if path else 'not_found'), flush=True)
    if path:
        print('native_ssh_config_owner={}'.format(file_details(path)), flush=True)
    facts, error = workspace_facts(path)
    if error:
        print('workspace_entry=failed', flush=True)
        print('workspace_error={}'.format(error), flush=True)
        return 1
    print('workspace_entry=ok', flush=True)
    for name in ('visible_label', 'release', 'layout', 'container', 'uid',
                 'interactive', 'prompt_function', 'prompt_hook', 'prompt_template',
                 'prompt_label_value', 'prompt_command', 'personal_bashrc',
                 'prompt_color', 'ssh_kind', 'ssh_path', 'scp_kind', 'scp_path',
                 'ssh_config_owner'):
        if name in facts:
            print('workspace_{}={}'.format(name, facts[name]), flush=True)
    if not path:
        print('hint=rerun_with_--ssh-config_and_exact_path_from_error', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
