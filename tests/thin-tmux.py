import json,os,shlex,subprocess,sys,time
from pathlib import Path
name=sys.argv[1]; base=['tmux','-L',name]; project=Path.cwd()
try:
    panes=subprocess.check_output(base+['list-panes','-a','-F','#{window_name}|#{pane_dead}'],text=True)
    assert set(panes.splitlines()) == {'workspace|0','editor|0','agents|0'}, panes
    subprocess.run(base+['send-keys','-t',name+':workspace','printf ready > '+shlex.quote(str(project/'shell-ready')),'Enter'],check=True)
    subprocess.run(base+['send-keys','-t',name+':editor',':lua vim.fn.writefile({"ready"}, "editor-ready")','Enter'],check=True)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline and not all((project/f).exists() for f in ('shell-ready','editor-ready')): time.sleep(.1)
    assert all((project/f).exists() for f in ('shell-ready','editor-ready')), panes
    subprocess.run(base+['send-keys','-t',name+':workspace',
        "ws job-env -- /usr/bin/python3 -c 'import os; assert not os.environ.get(\"SHELL\", \"\").startswith(\"/workspace-tools\"); assert \"TMUX\" not in os.environ; assert os.environ.get(\"GIT_PAGER\") != \"delta --paging=auto\"' && touch job-env-ready",
        'Enter'],check=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and not (project/'job-env-ready').exists(): time.sleep(.1)
    assert (project/'job-env-ready').exists()
    # Run the actual terminal applications with plain-font defaults.
    subprocess.run(['git','init','-q',str(project)],check=True)
    subprocess.run(base+['select-window','-t',name+':agents'],check=True)
    for tool in ('spf', 'lazygit', 'btop'):
        marker=project/('tui-'+tool+'-exit')
        command=tool+(' .' if tool == 'spf' else '')+'; printf "%s\\n" "$?" > '+shlex.quote(str(marker))
        subprocess.run(base+['send-keys','-t',name+':agents',command,'Enter'],check=True)
        time.sleep(1)
        screen=subprocess.check_output(base+['capture-pane','-p','-t',name+':agents'],text=True)
        welcome = {'spf': 'Thanks for using superfile', 'lazygit': 'Thanks for using lazygit!'}
        if tool in welcome and welcome[tool] in screen:
            # Dismiss first-use help before inspecting the working file view.
            subprocess.run(base+['send-keys','-t',name+':agents','Enter'],check=True)
            time.sleep(.5)
            screen=subprocess.check_output(base+['capture-pane','-p','-t',name+':agents'],text=True)
            assert welcome[tool] not in screen, screen
        assert not any(0xe000 <= ord(c) <= 0xf8ff for c in screen), (tool,screen)
        subprocess.run(base+['send-keys','-t',name+':agents','q'],check=True)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline and not marker.exists(): time.sleep(.1)
        assert marker.exists() and marker.read_text().strip() == '0', (tool,screen)
    subprocess.run(base+['select-window','-t',name+':editor'],check=True)
    subprocess.run(base+['send-keys','-t',name+':editor','Space','f','f'],check=True)
    time.sleep(1)
    subprocess.run(base+['send-keys','-t',name+':editor','sample.txt'],check=True)
    time.sleep(.5)
    subprocess.run(base+['send-keys','-t',name+':editor','Enter'],check=True)
    time.sleep(.5)
    subprocess.run(base+['send-keys','-t',name+':editor',':lua vim.fn.writefile({vim.fn.expand("%:t")}, "picker-result")','Enter'],check=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and not (project/'picker-result').exists(): time.sleep(.1)
    assert (project/'picker-result').read_text().strip() == 'sample.txt'
    editor_pane=subprocess.check_output(base+['display-message','-p','-t',name+':editor','#{pane_id}'],text=True).strip()
    adjacent=subprocess.check_output(base+['split-window','-h','-P','-F','#{pane_id}','-t',editor_pane,'-c',str(project)],text=True).strip()
    subprocess.run(base+['select-pane','-t',editor_pane],check=True)
    subprocess.run(base+['send-keys','-t',editor_pane,'Space','w','l'],check=True)
    time.sleep(.5)
    assert subprocess.check_output(base+['display-message','-p','-t',adjacent,'#{pane_active}'],text=True).strip() == '1', subprocess.check_output(base+['capture-pane','-p','-t',editor_pane],text=True)
    subprocess.run(base+['kill-pane','-t',adjacent],check=True)
    subprocess.run(base+['select-window','-t',name+':workspace'],check=True)
    subprocess.run(base+['send-keys','-t',name+':workspace',
        '{ command -v fzf; fzf --version; } > fzf-resolution; : > fzf-done','Enter'],check=True)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and not (project/'fzf-done').exists(): time.sleep(.1)
    assert (project/'fzf-resolution').read_text().splitlines()[0] == '/workspace-tools/bin/fzf', 'Packaged executables disappeared after detaching the runtime'
    (project/'shell-ready').unlink()
    subprocess.run(base+['send-keys','-t',name+':workspace','C-r'],check=True)
    time.sleep(.3)
    subprocess.run(base+['send-keys','-t',name+':workspace','shell-ready'],check=True)
    time.sleep(.3)
    subprocess.run(base+['send-keys','-t',name+':workspace','Enter'],check=True)
    time.sleep(.2)
    subprocess.run(base+['send-keys','-t',name+':workspace','Enter'],check=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and not (project/'shell-ready').exists(): time.sleep(.1)
    assert (project/'shell-ready').exists(), subprocess.check_output(base+['capture-pane','-p','-S','-40','-t',name+':workspace'],text=True)
    subprocess.run(base+['send-keys','-t',name+':workspace','sleep 60','Enter'],check=True)
    time.sleep(.3)
    subprocess.run(base+['send-keys','-t',name+':workspace','C-c'],check=True)
    subprocess.run(base+['send-keys','-t',name+':workspace','printf interrupted > '+shlex.quote(str(project/'interrupt-ready')),'Enter'],check=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and not (project/'interrupt-ready').exists(): time.sleep(.1)
    assert (project/'interrupt-ready').exists()
finally:
    subprocess.run(base+['kill-server'],check=False)
