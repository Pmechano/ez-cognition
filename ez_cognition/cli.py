"""Commands: open, check, init, stop, serve."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import __version__
from .check import check_project
from .home import Home
from .launch import open_page, stop
from .paths import DATA_DIR, PLUGIN, Paths, find_root, read_json, write_text
from .server import IDLE_SECONDS, running, serve

ENTRY_MARK = "ez-cognition"
BEGIN = "<!-- ez-cognition: begin. `init` writes this part; change it there, not here. -->"
END = "<!-- ez-cognition: end -->"


def notes_block(plugin: str) -> str:
    """The part of AGENTS.md that ez-cognition keeps: the project notes and the entry line."""
    return "\n".join([
        BEGIN,
        "## Project notes",
        "",
        "The agents of all members keep their notes in three files. Read them before you work.",
        "",
        "| File | In git | What it is | How to write it |",
        "|---|---|---|---|",
        "| `handbook.md` | yes | The current notes for the agents of all members: the setup, the rules of the group, "
        "the decisions, the traps. It says how things are now. It does not repeat the record in `cognition-data/`. "
        "| Before each push, bring it up to date from the journal. Replace text that is out of date. "
        "No dated entries. Nothing personal. |",
        "| `handbook.local.md` | no | The same, for your user only: their preferences, their local paths, "
        "personal remarks. | At any time. |",
        "| `journal.md` | yes | The log of the agents: what you did, found and decided, and what is not finished. "
        "| Add entries at the end while you work. Nothing personal. |",
        "",
        "- At the start of a session, read all three: `handbook.md`, `handbook.local.md` and `journal.md`. "
        "The handbook is the current state; where the journal is older than the handbook, the handbook is right.",
        "- A git conflict in `journal.md`: keep the entries of both sides. In `handbook.md`: keep both sides, "
        "then rewrite the part so that it says the current state once.",
        "",
        "## ez-cognition",
        "",
        "This project uses ez-cognition. Before you work, read `%s/agent-guide.md` and follow it. "
        "If that folder is empty, run `git submodule update --init` first." % plugin,
        END,
        "",
    ])


def with_block(text: str, block: str) -> str:
    """`text` with the ez-cognition part replaced, or added at the end."""
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        tail = rest.split(END, 1)[1].lstrip("\n")
        return head + block + (("\n" + tail) if tail else "")
    gap = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    return text + gap + block


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
        print("no record in %s/. See agent-guide.md, \"The record\"." % DATA_DIR)
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
        print("records: none. If the user is the leader, write the record. "
              "If not, tell the user to ask the leader.")
    for name, problems in tasks.items():
        state = "OK" if not problems else "%d problem(s), run `check`" % len(problems)
        print("record: %s (%s)" % (Path(name).stem, state))
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
    plugin = _plugin_dir(paths)
    agents = paths.root / "AGENTS.md"
    old = agents.read_text(encoding="utf-8").replace("\r\n", "\n") if agents.is_file() else ""
    new = with_block(old, notes_block(plugin))
    if new != old:
        write_text(agents, new)
        print("wrote the ez-cognition part of AGENTS.md")
    # The project notes: see agent-guide.md, "Project notes".
    for name, text in (
        ("handbook.md", "# Handbook\n\nThe current notes for the agents of all members. "
                        "See `%s/agent-guide.md`, \"Project notes\".\n" % plugin),
        ("journal.md", "# Journal\n\nWrite here while you work. Add new entries at the end.\n"),
    ):
        file = paths.root / name
        if not file.exists():
            write_text(file, text)
            print("created %s" % name)
    gitignore = paths.root / ".gitignore"
    rules = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if "handbook.local.md" not in rules.split():
        gap = "" if not rules or rules.endswith("\n") else "\n"
        write_text(gitignore, rules.replace("\r\n", "\n") + gap + "handbook.local.md\n")
        print("added handbook.local.md to .gitignore")
    claude = paths.root / "CLAUDE.md"
    if not claude.is_file():
        write_text(claude, "@AGENTS.md\n")
        print("created CLAUDE.md")
    print("next: write the record in %s/ (see agent-guide.md), then run `check`." % DATA_DIR)
    return 0


def cmd_stop() -> int:
    home = Home()
    info = running(home)
    if info is None:
        print("the server does not run")
        return 0
    if not stop(home, info):
        print("could not stop the server. Read %s" % home.log)
        return 1
    print("stopped. It served all projects; the next `open` starts it again.")
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
    commands.add_parser("check", help="validate the records")
    commands.add_parser("init", help="leader setup: create %s/" % DATA_DIR)
    commands.add_parser("stop", help="stop the server (it serves all projects and stays running until then)")
    run = commands.add_parser("serve", help="run the server in this terminal (all projects)")
    run.add_argument("--idle", type=float, default=IDLE_SECONDS,
                     help="stop after this many seconds without an open page (default: never)")
    run.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    if args.command == "stop":
        return cmd_stop()
    if args.command == "serve":
        return serve(Home(), idle_seconds=args.idle, port=args.port)
    paths = Paths(args.root) if args.root else Paths(find_root())
    if args.command == "open":
        return cmd_open(paths)
    if args.command == "check":
        return cmd_check(paths)
    return cmd_init(paths)
