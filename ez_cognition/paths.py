"""Where things are, and how files are read and written."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, List, Optional

DATA_DIR = "cognition-data"
PLUGIN = Path(__file__).resolve().parent.parent

# Task ids, step ids, direction ids and user names. Branch names use them.
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")


class Paths:
    def __init__(self, root) -> None:
        self.root = Path(root).resolve()
        self.data = self.root / DATA_DIR
        self.local = self.data / ".local"
        self.user = self.local / "user.json"
        self.view = self.local / "view.json"
        self.server = self.local / "server.json"
        self.log = self.local / "server.log"

    def task_files(self) -> List[Path]:
        if not self.data.is_dir():
            return []
        return sorted(p for p in self.data.glob("*.json") if p.is_file())

    def task_file(self, task_id: str) -> Optional[Path]:
        if not isinstance(task_id, str) or not ID_RE.match(task_id):
            return None
        path = self.data / (task_id + ".json")
        return path if path.is_file() else None


def find_root(start=None) -> Path:
    """The nearest directory, from `start` upwards, that has the data directory."""
    here = Path(start or os.getcwd()).resolve()
    for folder in [here, *here.parents]:
        if (folder / DATA_DIR).is_dir():
            return folder
    return here


def load_json(path: Path) -> Any:
    """Read a JSON file. Raise ValueError with a message for an agent."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as err:
        raise ValueError("cannot read the file: %s" % err)
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise ValueError("not valid JSON: line %d, column %d: %s" % (err.lineno, err.colno, err.msg))


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return load_json(path)
    except ValueError:
        return default


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with LF line endings, on every platform."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)


def write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    write_text(temp, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)
