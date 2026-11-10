"""`open`: start the server if it does not run, then show the page in the default browser.

Supported: Windows, macOS, Ubuntu, and WSL (the browser opens on the Windows side).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .paths import PLUGIN, Paths, read_json
from .server import default_port, ping, same_root

NO_WINDOW = "EZC_NO_WINDOW"


def find_running(paths: Paths) -> Optional[Dict[str, Any]]:
    """The answer of the server of this project, if it runs."""
    ports = []
    record = read_json(paths.server)
    if isinstance(record, dict) and isinstance(record.get("port"), int):
        ports.append(record["port"])
    first = default_port(paths.root)
    ports.extend(p for p in range(first, first + 3) if p not in ports)
    for port in ports:
        info = ping(port, timeout=0.4)
        if info and same_root(info.get("root", ""), paths.root):
            return info
    return None


def spawn(paths: Paths) -> None:
    """Start the server as a separate process that outlives this command."""
    paths.local.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, str(PLUGIN / "ezc.py"), "--root", str(paths.root), "serve"]
    with open(paths.log, "ab") as log:
        common = dict(stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=str(paths.root), close_fds=True)
        if os.name != "nt":
            subprocess.Popen(argv, start_new_session=True, **common)
            return
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            # An agent's shell can run in a job that ends its children with it.
            subprocess.Popen(argv, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **common)
        except OSError:
            subprocess.Popen(argv, creationflags=flags, **common)


def start(paths: Paths, wait: float = 10.0) -> Optional[Dict[str, Any]]:
    spawn(paths)
    end = time.time() + wait
    while time.time() < end:
        info = find_running(paths)
        if info:
            return info
        time.sleep(0.2)
    return None


def is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        return False


def open_browser(url: str) -> bool:
    try:
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        if is_wsl():
            cwd = "/mnt/c" if Path("/mnt/c").is_dir() else None  # cmd.exe complains about a Linux working dir
            for argv in (["cmd.exe", "/c", "start", "", url], ["wslview", url], ["explorer.exe", url]):
                if shutil.which(argv[0]):
                    subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
            return False
        if sys.platform == "darwin":
            subprocess.Popen(["open", url])
            return True
        return bool(webbrowser.open(url))
    except Exception:
        return False


def wait_for_page(info: Dict[str, Any], wait: float = 4.0) -> Dict[str, Any]:
    """Give a page that is already in the browser the time to connect again."""
    end = time.time() + wait
    while time.time() < end and info.get("pages", 0) == 0:
        time.sleep(0.3)
        info = ping(info["port"]) or info
    return info


def open_page(paths: Paths) -> Tuple[Optional[str], str]:
    """(url, what happened). The url is None when the server did not start."""
    info = find_running(paths)
    if info is None:
        # A server that stopped while a page was open leaves its record.
        page_waits = paths.server.is_file()
        info = start(paths)
        if info is None:
            return None, "the server did not start. Read %s" % paths.log
        if page_waits:
            info = wait_for_page(info)
    url = "http://127.0.0.1:%d/" % info["port"]
    if info.get("pages", 0) > 0:
        return url, "already open in the browser"
    if os.environ.get(NO_WINDOW):
        return url, "not opened, because %s is set" % NO_WINDOW
    if open_browser(url):
        return url, "opened in the browser"
    return url, "could not open the browser. Give this URL to the user"
