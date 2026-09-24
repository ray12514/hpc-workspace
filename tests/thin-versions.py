"""Fast packaged-runtime check, before exporting a SIF; no host tools required."""
import json
from pathlib import Path
import subprocess

tools = json.loads(Path('/workspace-tools/manifests/tools.json').read_text())
failed = []
for name in tools:
    if name in ('infocmp', 'tput', 'nvim'):
        continue
    flag = '-V' if name in ('tmux', 'lnav') else '--version'
    try:
        result = subprocess.run([name, flag], capture_output=True, text=True, timeout=30)
        output = (result.stdout + result.stderr).strip()
        if result.returncode or not output:
            failed.append((name, result.returncode, output[-1000:]))
        else:
            print(name + ': ' + output.splitlines()[0], flush=True)
    except Exception as exc:
        failed.append((name, str(exc)))
assert not failed, failed
