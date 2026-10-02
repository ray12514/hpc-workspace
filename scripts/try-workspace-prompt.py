#!/usr/bin/env python3
"""Try the repository prompt startup in one fresh workspace without installing it.

Run from a native shell in this checkout. Only safe prompt status flags are
printed; site output and hook contents are captured privately and discarded.
"""
import importlib.util
import os
from pathlib import Path
import shlex
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def candidate_shell(source, rcfile):
    anchor = 'export WS_PROMPT_RC=${WS_PROMPT_RC:-/workspace-tools/config/bashrc}'
    if source.count(anchor) != 1 or not source.startswith('#!'):
        raise ValueError('thin shell bootstrap changed')
    first, rest = source.split('\n', 1)
    return first + '\nexport WS_PROMPT_RC=' + shlex.quote(str(rcfile)) + '\n' + rest


def main():
    if os.environ.get('WS_CONTAINER') == '1' or os.environ.get('WS_LAYOUT') == 'thin-v1':
        print('error=run_from_native_shell', file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location('workspace_entry_diagnostic',
                                                  str(ROOT / 'scripts/diagnose-workspace-entry.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actual, error = module.workspace_facts(None)
    if error:
        print('actual_entry=failed')
        print('actual_error=' + error.replace(' ', '_'))
        return 1
    print('actual_release=' + actual.get('release', 'unavailable'))
    print('actual_label=' + actual.get('visible_label', 'unavailable'))
    if actual.get('release') != '0.7.3-preview5':
        print('candidate_entry=skipped_release_mismatch')
        return 1
    with tempfile.TemporaryDirectory(prefix='.ws-prompt-candidate.', dir=Path.cwd()) as temp:
        directory = Path(temp)
        directory.chmod(0o700)
        rcfile = directory / 'bashrc'
        thin_shell = directory / 'thin-shell'
        rcfile.write_text((ROOT / 'image/config/bashrc').read_text())
        thin_shell.write_text(candidate_shell((ROOT / 'scripts/thin-shell').read_text(), rcfile))
        candidate, error = module.workspace_facts(None, entry_argv=[
            'enter', '--', '/workspace-tools/bin/bash', str(thin_shell)])
    if error:
        print('candidate_entry=failed')
        print('candidate_error=' + error.replace(' ', '_'))
        return 1
    print('candidate_entry=ok')
    for key in ('visible_label', 'prompt_hook', 'prompt_template',
                'prompt_command', 'prompt_storage', 'prompt_element_count',
                'prompt_element_shapes'):
        if key in candidate:
            print('candidate_' + key + '=' + candidate[key])
    return 0


if __name__ == '__main__':
    sys.exit(main())
