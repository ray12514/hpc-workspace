#!/usr/bin/env python3
"""Exercise persistent state and tmux against real Linux tools in the image."""
import os
from pathlib import Path
import subprocess
import sys
import time


def run(*command, **options):
    return subprocess.run(command, check=True, text=True, timeout=120, **options)


state = Path(os.environ["XDG_STATE_HOME"])
home = Path.home()
phase = sys.argv[1]
assert (home / ".agents/skills/research/SKILL.md").read_text() == "keep my custom skill\n"
assert (home / ".claude/skills/research/SKILL.md").is_file()
assert (home / ".agents/skills/codebase-design").is_symlink()

if phase == "save":
    run("container-smoke")
    Path("first.txt").write_text("persistent first file\n")
    Path("second.txt").write_text("persistent second file\n")
    run("nvim", "--headless", "first.txt", "+vsplit second.txt", "+WorkspaceSave", "+qa")
    (state / "replacement-marker").write_text("survived replacement")
    run("bash", "--noprofile", "--rcfile", "/opt/workspace/config/bashrc", "-ic",
        "history -s history-survives-container-replacement; history -a")
elif phase == "restore":
    assert (state / "replacement-marker").read_text() == "survived replacement"
    assert "history-survives-container-replacement" in (state / "bash-history").read_text()
    run("nvim", "--headless", "+WorkspaceRestore",
        "+lua if #vim.api.nvim_list_wins() ~= 2 then vim.cmd('cquit 1') end", "+qa")
    assert Path("first.txt").read_text() == "persistent first file\n"
    print("Replacement preserved files, history, editor layout, and custom skills.")

    environment = dict(os.environ, WS_ROOT="/opt/workspace", WS_SESSION_STATE=str(state / "tmux-check"))
    Path(environment["WS_SESSION_STATE"]).mkdir(exist_ok=True)
    tmux = ["tmux", "-L", "workspace-smoke", "-f", "/opt/workspace/config/tmux/tmux.conf"]

    def tm(*args):
        return subprocess.run(tmux + list(args), check=True, text=True, env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30).stdout.strip()

    try:
        tm("new-session", "-d", "-s", "saved", "-n", "editor")
        tm("new-window", "-t", "saved", "-n", "host")
        assert tm("show-option", "-gv", "@resurrect-processes") == "false"
        assert tm("show-option", "-gv", "@resurrect-dir") == environment["WS_SESSION_STATE"]
        assert "continuum_save.sh" in tm("show-option", "-gv", "status-right")
        assert "save.sh" in tm("show-hooks", "-g", "client-detached")
        tm("run-shell", '"$WS_ROOT/share/tmux-resurrect/scripts/save.sh" quiet')
        saved = Path(environment["WS_SESSION_STATE"]) / "last"
        assert saved.is_file(), "tmux snapshot was not written"
        snapshot = saved.read_text()
        assert "editor" in snapshot and "host" in snapshot
        tm("kill-server")
        # A second server models a login host/session restart. No process replay.
        time.sleep(0.2)
        tm("new-session", "-d", "-s", "empty")
        tm("run-shell", '"$WS_ROOT/share/tmux-resurrect/scripts/restore.sh"')
        names = tm("list-windows", "-t", "saved", "-F", "#{window_name}").splitlines()
        assert "editor" in names and "host" in names, names
        assert set(tm("list-panes", "-a", "-F", "#{pane_current_command}").splitlines()) <= {"bash", "sh"}
        print("tmux saved and restored window layout with process replay disabled.")
    finally:
        subprocess.run(tmux + ["kill-server"], env=environment, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
else:
    raise SystemExit("Unknown phase: " + phase)
