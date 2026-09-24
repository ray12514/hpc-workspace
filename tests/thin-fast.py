from pathlib import Path
import runpy
import subprocess
import sys
import json
import time

(Path.home() / '.config/hpc-workspace/nvim.lua').write_text('vim.g.fixture_custom = 123\n')
if sys.argv[1] == 'editor':
    sys.exit(subprocess.call(['nvim', '--headless', '-c', 'luafile /src/tests/thin-editor.lua']))
if sys.argv[1] == 'tmux':
    Path('sample.txt').write_text('a needle in shared data\n')
    ready = Path('/tmp/tmux-ready.json')
    server = subprocess.Popen(['/workspace-tools/thin-session', '--serve', str(ready)])
    try:
        deadline = time.monotonic() + 30
        while not ready.exists() and time.monotonic() < deadline:
            if server.poll() is not None: raise RuntimeError('tmux server exited')
            time.sleep(.1)
        name = json.loads(ready.read_text())['session']
        result = subprocess.call([sys.executable, '-I', '/src/tests/thin-tmux.py', name])
        server.wait(timeout=15)
        if result == 0:
            print('PASS: tmux windows, job environment, plain-font terminal apps, editor picker/navigation, Ctrl-R and Ctrl-C.')
        sys.exit(result)
    finally:
        if server.poll() is None: server.terminate()
runpy.run_path('/src/tests/thin-' + sys.argv[1] + '.py')
