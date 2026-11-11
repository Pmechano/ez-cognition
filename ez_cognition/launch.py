"""`open` and `stop`: start the one server if it does not run, then show the page.

Supported: Windows, macOS, Ubuntu, and WSL (the browser opens on the Windows side).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import __version__
from .home import Home, is_wsl, side
from .paths import PLUGIN, Paths, write_text
from .server import _direct, running

NO_WINDOW = "EZC_NO_WINDOW"
# A new tab needs a few seconds to connect. A second `open` in this time
# must not open a second tab.
OPENING_SECONDS = 15.0


def version_key(text: Any) -> Tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(text).split("."))
    except ValueError:
        return ()


def spawn(home: Home) -> None:
    """Start the server as a separate process that outlives this command."""
    home.dir.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, str(PLUGIN / "ezc.py"), "serve"]
    with open(home.log, "ab") as log:
        # Not the plugin folder: a running server would lock it, and an update of
        # a copied plugin could not replace it.
        common = dict(stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=str(home.dir), close_fds=True)
        if os.name != "nt":
            subprocess.Popen(argv, start_new_session=True, **common)
            return
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            # An agent's shell can run in a job that ends its children with it.
            subprocess.Popen(argv, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **common)
        except OSError:
            subprocess.Popen(argv, creationflags=flags, **common)


def start(home: Home, wait: float = 10.0) -> Optional[Dict[str, Any]]:
    spawn(home)
    end = time.time() + wait
    while time.time() < end:
        info = running(home)
        if info:
            return info
        time.sleep(0.2)
    return None


def stop(home: Home, info: Dict[str, Any], wait: float = 8.0) -> bool:
    """Ask the running server to stop. True when it stopped."""
    if info.get("reach"):
        try:
            request = urllib.request.Request("http://127.0.0.1:%d/api/stop" % info["port"], data=b"{}",
                                             method="POST", headers={"Content-Type": "application/json", "X-EZC": "1"})
            _direct.open(request, timeout=3).close()
        except Exception:
            pass
    else:
        # The server is on the other side of WSL. It reads this file.
        write_text(home.stop, "%s\n" % info.get("pid", ""))
    end = time.time() + wait
    while time.time() < end:
        if running(home) is None:
            return True
        time.sleep(0.2)
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


def opening(home: Home) -> bool:
    """True when `open` opened a tab a moment ago, and the tab did not connect yet."""
    try:
        at = float(home.opened.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return 0 <= time.time() - at < OPENING_SECONDS


def wait_for_page(home: Home, info: Dict[str, Any], wait: float = 4.0) -> Dict[str, Any]:
    """Give a page that is already in the browser the time to connect again."""
    end = time.time() + wait
    while time.time() < end and info.get("pages", 0) == 0:
        time.sleep(0.3)
        info = running(home) or info
    return info


def open_page(paths: Paths, home: Optional[Home] = None) -> Tuple[Optional[str], str]:
    """(url, what happened). The url is None when the server did not start."""
    home = home or Home()
    home.add(paths.root, focus=True)
    info = running(home)
    if info and version_key(info.get("version")) < version_key(__version__):
        # A newer copy of ez-cognition replaces the server of an older copy.
        if not stop(home, info):
            return None, "an older server (ez-cognition %s) did not stop. Read %s" % (info.get("version"), home.log)
        info = None
    if info is None:
        # A server that stopped while a page was open leaves its record.
        page_waits = home.server.is_file()
        info = start(home)
        if info is None:
            return None, "the server did not start. Read %s" % home.log
        if page_waits:
            info = wait_for_page(home, info)
    url = "http://127.0.0.1:%d/" % info["port"]
    where = "" if info.get("side") == side() else ", the server runs on the %s side" % info.get("side")
    if info.get("pages", 0) > 0:
        return url, "already open in the browser; it now shows this project%s" % where
    if os.environ.get(NO_WINDOW):
        return url, "not opened, because %s is set%s" % (NO_WINDOW, where)
    if opening(home):
        return url, "the page is opening in the browser; it will show this project%s" % where
    if open_browser(url):
        try:
            write_text(home.opened, "%f\n" % time.time())
        except OSError:
            pass
        return url, "opened in the browser%s" % where
    return url, "could not open the browser. Give this URL to the user%s" % where
