"""The shared place of the one server: ~/.ez-cognition/.

All projects on a computer share one server, one port and one page. The
server learns about the projects from a list in this folder. An agent in
WSL and an agent in Windows use the same folder (in WSL it is under
/mnt/c/Users/<name>/), so they also share the server: an `open` from WSL
can use a server that runs in Windows, and the other way round.

A project path is stored in one shared form: the Windows form when the
path has one (`D:\\x`, `\\\\wsl.localhost\\Ubuntu\\home\\x`), else the
POSIX form. Each side changes it back to its own form.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import DATA_DIR, read_json, write_json

HOME_ENV = "EZC_HOME"
DRIVE_RE = re.compile(r"^([A-Za-z]):(?:[\\/](.*))?$")
MNT_RE = re.compile(r"^/mnt/([a-zA-Z])(?:/(.*))?$")
UNC_RE = re.compile(r"^\\\\(?:wsl\.localhost|wsl\$)\\([^\\]+)(\\.*)?$", re.IGNORECASE)


# ---------- where this process runs ----------

def is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        return False


def side() -> str:
    """"windows", "wsl" or "posix"."""
    if os.name == "nt":
        return "windows"
    return "wsl" if is_wsl() else "posix"


def distro() -> str:
    return os.environ.get("WSL_DISTRO_NAME", "")


# ---------- one path, two forms ----------

def to_shared(path: str, where: str, name: str = "") -> str:
    """The shared form of a local path. `where` is the side, `name` the WSL distro."""
    if where != "wsl":
        return path
    found = MNT_RE.match(path)
    if found:
        rest = (found.group(2) or "").strip("/")
        return "%s:\\%s" % (found.group(1).upper(), rest.replace("/", "\\"))
    if name and path.startswith("/"):
        return "\\\\wsl.localhost\\%s%s" % (name, path.rstrip("/").replace("/", "\\"))
    return path


def to_local(shared: str, where: str, name: str = "") -> Optional[str]:
    """The local form of a shared path, or None when this side cannot reach it."""
    if where == "windows":
        return shared if (DRIVE_RE.match(shared) or shared.startswith("\\\\")) else None
    if where == "wsl":
        found = DRIVE_RE.match(shared)
        if found:
            rest = (found.group(2) or "").replace("\\", "/").strip("/")
            return "/mnt/%s%s" % (found.group(1).lower(), "/" + rest if rest else "")
        found = UNC_RE.match(shared)
        if found:
            if not name or found.group(1).lower() != name.lower():
                return None
            return (found.group(2) or "\\").replace("\\", "/")
    return shared if shared.startswith("/") else None


def key(shared: str) -> str:
    """Two shared paths are the same project when their keys are equal."""
    windows = DRIVE_RE.match(shared) or shared.startswith("\\\\")
    text = shared.rstrip("\\/") or shared
    return text.lower() if windows else text


# ---------- the folder ----------

def _windows_profile() -> Optional[str]:
    """The Windows user folder, seen from WSL."""
    try:
        done = subprocess.run(["cmd.exe", "/c", "echo %USERPROFILE%"], cwd="/mnt/c", capture_output=True,
                              text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = done.stdout.strip().splitlines()
    value = lines[-1].strip() if lines else ""
    if done.returncode != 0 or not DRIVE_RE.match(value):
        return None
    return to_local(value, "wsl")


def home_dir() -> Path:
    if os.environ.get(HOME_ENV):
        return Path(os.environ[HOME_ENV])
    if side() == "wsl":
        profile = _windows_profile()
        if profile and Path(profile).is_dir():
            return Path(profile) / ".ez-cognition"
    return Path.home() / ".ez-cognition"


class Home:
    """The files of the one server."""

    def __init__(self, folder=None) -> None:
        self.dir = Path(folder) if folder else home_dir()
        self.server = self.dir / "server.json"      # written by the running server
        self.log = self.dir / "server.log"
        self.projects = self.dir / "projects.json"  # written by `open`
        self.user = self.dir / "user.json"          # the look of the page: theme, motion, language
        self.stop = self.dir / "stop"               # a request from `stop` when the server cannot be reached

    # ---------- the list of projects ----------

    def registry(self) -> Dict[str, Any]:
        value = read_json(self.projects)
        if not isinstance(value, dict):
            value = {}
        roots = value.get("projects")
        value["projects"] = [r for r in roots if isinstance(r, str) and r] if isinstance(roots, list) else []
        if not isinstance(value.get("focus"), dict):
            value.pop("focus", None)
        return value

    def add(self, root, focus: bool = True) -> str:
        """Put a project on the list. With `focus`, the open pages change to it."""
        shared = to_shared(str(Path(root).resolve()), side(), distro())
        value = self.registry()
        if key(shared) not in {key(r) for r in value["projects"]}:
            value["projects"].append(shared)
        if focus:
            value["focus"] = {"project": shared, "at": time.time()}
        write_json(self.projects, value)
        return shared

    def roots(self) -> List[Path]:
        """The projects on the list that this side can reach and that have the data directory."""
        out, seen = [], set()
        for shared in self.registry()["projects"]:
            local = to_local(shared, side(), distro())
            if local is None or key(shared) in seen:
                continue
            seen.add(key(shared))
            try:
                if (Path(local) / DATA_DIR).is_dir():
                    out.append(Path(local))
            except OSError:
                continue
        return out
