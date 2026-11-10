"""Commands: open, check, init, stop, serve."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from . import __version__
from .check import check_project
from .launch import find_running, open_page
from .paths import DATA_DIR, PLUGIN, Paths, find_root, read_json, write_text
from .server import IDLE_SECONDS, serve

ENTRY_MARK = "ez-cognition"


def _plugin_dir(paths: Paths) -> str:
    try:
        return PLUGIN.relative_to(paths.root).as_posix()
    except ValueError:
        return PLUGIN.as_posix()


def _branch(paths: Paths) -> Optional[str]:
    try:
        done = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(paths.root),
                              capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def _print_report(report: Dict[str, List[str]]) -> bool:
    bad = False
    for name, problems in report.items():
        for problem in problems:
            bad = True
            print("%s: %s" % (name, problem))
    return not bad


def cmd_check(paths: Paths) -> int:
    report = check_project(paths)
    if not _print_report(report):
        return 1
    if not any(name.endswith(".json") and not name.startswith(".local") for name in report):
        print("no task record in %s/. See agent-guide.md, \"The task record\"." % DATA_DIR)
        return 1
    print("OK")
    return 0


def cmd_open(paths: Paths) -> int:
    if not paths.data.is_dir():
        print("%s/ does not exist. If the user is the leader, run `init`. "
              "If not, tell the user to ask the leader." % DATA_DIR)
        return 1
    url, what = open_page(paths)
    if url is None:
        print("page: %s" % what)
        return 1
    print("page: %s (%s)" % (url, what))
    report = check_project(paths)
    tasks = {name: problems for name, problems in report.items() if not name.startswith(".local")}
    if not tasks:
        print("tasks: none. If the user is the leader, write the task record. "
              "If not, tell the user to ask the leader.")
    for name, problems in tasks.items():
        state = "OK" if not problems else "%d problem(s), run `check`" % len(problems)
        print("task: %s (%s)" % (Path(name).stem, state))
    user = read_json(paths.user)
    name = user.get("name") if isinstance(user, dict) else ""
    if name:
        print("user: %s" % name)
    else:
        print("user: no name yet. Ask the user to write a name in the settings panel of the page.")
    branch = _branch(paths)
    if branch:
        print("branch: %s" % branch)
    return 0


def cmd_init(paths: Paths) -> int:
    paths.local.mkdir(parents=True, exist_ok=True)
    ignore = paths.data / ".gitignore"
    if not ignore.is_file():
        write_text(ignore, ".local/\n")
        print("created %s/.gitignore" % DATA_DIR)
    line = ("This project uses ez-cognition. Before you work, read `%s/agent-guide.md` and follow it."
            % _plugin_dir(paths))
    agents = paths.root / "AGENTS.md"
    old = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    if ENTRY_MARK not in old:
        gap = "" if not old else ("\n" if old.endswith("\n") else "\n\n")
        write_text(agents, old.replace("\r\n", "\n") + gap + line + "\n")
        print("added the entry line to AGENTS.md")
    claude = paths.root / "CLAUDE.md"
    if not claude.is_file():
        write_text(claude, "@AGENTS.md\n")
        print("created CLAUDE.md")
    print("next: write a task record in %s/ (see agent-guide.md), then run `check`." % DATA_DIR)
    return 0


def cmd_stop(paths: Paths) -> int:
    info = find_running(paths)
    if info is None:
        print("the server does not run")
        return 0
    request = urllib.request.Request("http://127.0.0.1:%d/api/stop" % info["port"], data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json", "X-EZC": "1"})
    try:
        with urllib.request.urlopen(request, timeout=3) as reply:
            json.loads(reply.read().decode("utf-8"))
    except Exception as err:
        print("could not stop the server: %s" % err)
        return 1
    print("stopped")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="ezc", description="ez-cognition %s" % __version__)
    parser.add_argument("--root", help="the project root. Default: the nearest directory with %s/" % DATA_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("open", help="start the server if it does not run, and show the page")
    commands.add_parser("check", help="validate the task records")
    commands.add_parser("init", help="leader setup: create %s/" % DATA_DIR)
    commands.add_parser("stop", help="stop the server now")
    run = commands.add_parser("serve", help="run the server in this terminal")
    run.add_argument("--idle", type=float, default=IDLE_SECONDS,
                     help="seconds without an open page before the server stops")
    run.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    paths = Paths(args.root) if args.root else Paths(find_root())
    if args.command == "open":
        return cmd_open(paths)
    if args.command == "check":
        return cmd_check(paths)
    if args.command == "init":
        return cmd_init(paths)
    if args.command == "stop":
        return cmd_stop(paths)
    return serve(paths, idle_seconds=args.idle, port=args.port)
