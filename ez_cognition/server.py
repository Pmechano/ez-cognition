"""The local server of the page.

It serves the core, the modules and the themes as static files, the task
records as JSON, and the personal state. It tells the open pages when a task
record changes. It stops by itself when no page has been open for a while:
nothing stays resident.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from . import __version__
from .check import check_task, module_dirs
from .paths import ID_RE, PLUGIN, Paths, load_json, read_json, write_json

APP = "ez-cognition"
HOSTS = ("127.0.0.1", "localhost")
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
}
STATIC = ("core", "modules", "themes", "locales")
MAX_BODY = 256 * 1024
IDLE_SECONDS = 60
USER_DEFAULTS = {"name": "", "theme": "amber", "motion": True, "language": "zh"}
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


def default_port(root: Path) -> int:
    """A port that stays the same for a project, so an open page finds the server again."""
    return 20000 + zlib.crc32(str(Path(root).resolve()).lower().encode("utf-8")) % 20000


def ping(port: int, timeout: float = 0.6) -> Optional[Dict[str, Any]]:
    """The answer of an ez-cognition server on this port, or None."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=timeout) as reply:
            info = json.loads(reply.read().decode("utf-8"))
    except Exception:
        return None
    if isinstance(info, dict) and info.get("app") == APP:
        info["port"] = port
        return info
    return None


def same_root(a, b) -> bool:
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def themes() -> List[str]:
    base = PLUGIN / "themes"
    return sorted(p.stem for p in base.glob("*.css")) if base.is_dir() else []


def locales() -> List[str]:
    base = PLUGIN / "locales"
    return sorted(p.stem for p in base.glob("*.json")) if base.is_dir() else []


def clean_user(raw: Any, old: Any) -> Dict[str, Any]:
    """Merge the settings from the page into the stored ones. Keep only valid values."""
    user = dict(old) if isinstance(old, dict) else {}
    if not isinstance(raw, dict):
        return user
    name = raw.get("name")
    if isinstance(name, str) and (name == "" or ID_RE.match(name)):
        user["name"] = name
    if raw.get("theme") in themes():
        user["theme"] = raw["theme"]
    if isinstance(raw.get("motion"), bool):
        user["motion"] = raw["motion"]
    language = raw.get("language")
    if isinstance(language, str) and LANGUAGE_RE.match(language):
        user["language"] = language
    return user


class App:
    """The state that the request threads share."""

    def __init__(self, paths: Paths, idle_seconds: float = IDLE_SECONDS, tick: float = 1.0) -> None:
        self.paths = paths
        self.idle_seconds = idle_seconds
        self.tick = tick
        self.heartbeat = 5.0  # seconds between two lines to a page; a closed page is found then
        self.version = 0
        self.pages = 0
        self.closing = False
        self.left = 0  # the pages that were open when the server stopped
        self.changed = threading.Condition()

    def stamp(self) -> List[Any]:
        """A value that changes when a task record changes."""
        out = []
        for file in self.paths.task_files():
            try:
                stat = file.stat()
            except OSError:
                continue
            out.append((file.name, stat.st_mtime_ns, stat.st_size))
        return out

    def user(self) -> Dict[str, Any]:
        stored = read_json(self.paths.user)
        user = dict(USER_DEFAULTS)
        if isinstance(stored, dict):
            user.update(clean_user(stored, {}))
        if user["theme"] not in themes():
            user["theme"] = USER_DEFAULTS["theme"]
        return user

    def manifest(self) -> Dict[str, Any]:
        tasks = []
        for file in self.paths.task_files():
            if not ID_RE.match(file.stem):
                continue
            task = read_json(file)
            title = task.get("title") if isinstance(task, dict) else None
            tasks.append({"id": file.stem, "title": title if isinstance(title, str) and title.strip() else file.stem})
        return {
            "app": APP,
            "version": __version__,
            "project": self.paths.root.name,
            "tasks": tasks,
            "modules": [{"name": d.name, "css": (d / "module.css").is_file()} for d in module_dirs()],
            "themes": themes(),
            "locales": locales(),
        }

    def task(self, task_id: str) -> Dict[str, Any]:
        file = self.paths.task_file(task_id)
        if file is None:
            return {"ok": False, "error": "no task record with this id"}
        try:
            task = load_json(file)
        except ValueError as err:
            return {"ok": False, "error": "%s: %s" % (file.name, err)}
        return {"ok": isinstance(task, dict), "task": task, "problems": check_task(task), "file": file.name}

    def watch(self, httpd: ThreadingHTTPServer) -> None:
        """Tell the pages about changes. Stop the server when no page is open.

        The idle time is counted in ticks, not read from a clock. When the
        computer sleeps, the count stops too, so an open page has time to
        connect again after the computer wakes.
        """
        last = self.stamp()
        idle = 0.0
        while not self.closing:
            time.sleep(self.tick)
            now = self.stamp()
            if now != last:
                last = now
                with self.changed:
                    self.version += 1
                    self.changed.notify_all()
            idle = idle + self.tick if self.pages == 0 else 0.0
            if idle >= self.idle_seconds:
                break
        self.close()
        httpd.shutdown()

    def close(self) -> None:
        with self.changed:
            if not self.closing:
                self.left = self.pages
            self.closing = True
            self.changed.notify_all()


class Handler(BaseHTTPRequestHandler):
    server_version = APP

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, format, *args) -> None:  # noqa: A002 - the name comes from the base class
        return

    # ---------- replies ----------

    def _send(self, code: int, body: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: Any, code: int = 200) -> None:
        self._send(code, json.dumps(value, ensure_ascii=False).encode("utf-8"), MIME[".json"])

    def _no(self, code: int, message: str) -> None:
        self._json({"ok": False, "error": message}, code)

    def _local(self) -> bool:
        """Refuse a request that another site sent through the browser (DNS rebinding)."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in HOSTS

    # ---------- GET ----------

    def do_GET(self) -> None:  # noqa: N802 - the name comes from the base class
        if not self._local():
            return self._no(403, "only local requests")
        url = urlparse(self.path)
        path = url.path
        if path == "/":
            return self._static("core/index.html")
        if path == "/api/ping":
            return self._json({"app": APP, "version": __version__, "root": str(self.app.paths.root),
                               "pid": os.getpid(), "pages": self.app.pages})
        if path == "/api/manifest":
            return self._json(self.app.manifest())
        if path == "/api/task":
            return self._json(self.app.task((parse_qs(url.query).get("id") or [""])[0]))
        if path == "/api/state":
            view = read_json(self.app.paths.view)
            return self._json({"user": self.app.user(), "view": view if isinstance(view, dict) else {}})
        if path == "/api/events":
            return self._events()
        return self._static(path.lstrip("/"))

    def _static(self, relative: str) -> None:
        parts = relative.split("/")
        if parts[0] not in STATIC or any(p in ("", ".", "..") or "\\" in p or ":" in p for p in parts):
            return self._no(404, "not found")
        file = PLUGIN.joinpath(*parts)
        kind = MIME.get(file.suffix.lower())
        if kind is None or not file.is_file():
            return self._no(404, "not found")
        self._send(200, file.read_bytes(), kind)

    def _events(self) -> None:
        """Server-sent events. An open connection is an open page."""
        app = self.app
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with app.changed:
            app.pages += 1
            seen = app.version
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while True:
                with app.changed:
                    app.changed.wait_for(lambda: app.version != seen or app.closing, timeout=app.heartbeat)
                    closing, version = app.closing, app.version
                if closing:
                    break
                if version != seen:
                    seen = version
                    self.wfile.write(b"event: change\ndata: %d\n\n" % version)
                else:
                    self.wfile.write(b": still here\n\n")
                self.wfile.flush()
        except OSError:
            pass  # the page closed
        finally:
            with app.changed:
                app.pages -= 1

    # ---------- POST ----------

    def do_POST(self) -> None:  # noqa: N802
        # A page of another site cannot send this header without a preflight
        # request, and this server does not answer preflight requests.
        if not self._local() or self.headers.get("X-EZC") != "1":
            return self._no(403, "only the page of this server can write")
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            return self._no(413, "the body is too large")
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return self._no(400, "the body must be JSON")
        path = urlparse(self.path).path
        if path == "/api/state":
            return self._save_state(body)
        if path == "/api/stop":
            self._json({"ok": True})
            self.app.close()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return None
        return self._no(404, "not found")

    def _save_state(self, body: Any) -> None:
        if not isinstance(body, dict):
            return self._no(400, "the body must be an object")
        paths = self.app.paths
        if "user" in body:
            write_json(paths.user, clean_user(body["user"], read_json(paths.user)))
        if "view" in body:
            if not isinstance(body["view"], dict):
                return self._no(400, "view must be an object")
            write_json(paths.view, body["view"])
        self._json({"ok": True, "user": self.app.user()})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, "reuse address" lets two servers take the same port.
    allow_reuse_address = os.name != "nt"


def bind(paths: Paths, port: Optional[int] = None) -> Optional[Server]:
    """A server on a free port near the project's port. None: one already runs for this project.

    The system can refuse a whole range of ports (Windows reserves ranges for
    Hyper-V and WSL). The last candidate is 0: a port that the system chooses.
    """
    first = default_port(paths.root) if port is None else port
    last_error: Optional[OSError] = None
    for candidate in ([0] if port == 0 else [*range(first, first + 20), 0]):
        try:
            return Server(("127.0.0.1", candidate), Handler)
        except OSError as err:
            last_error = err
            other = ping(candidate)
            if other and same_root(other.get("root", ""), paths.root):
                return None
    raise OSError("no free port near %d: %s" % (first, last_error))


def serve(paths: Paths, idle_seconds: float = IDLE_SECONDS, port: Optional[int] = None) -> int:
    """Run the server until no page has been open for `idle_seconds`."""
    httpd = bind(paths, port)
    if httpd is None:
        return 0
    app = App(paths, idle_seconds)
    httpd.app = app  # type: ignore[attr-defined]
    me = {"port": httpd.server_address[1], "pid": os.getpid(), "root": str(paths.root)}
    write_json(paths.server, me)
    print("http://127.0.0.1:%d/ for %s" % (me["port"], paths.root), flush=True)
    threading.Thread(target=app.watch, args=(httpd,), daemon=True).start()
    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        httpd.server_close()
        # A page that was open tries to connect again. The record stays for
        # it, so the next `open` does not make a second tab.
        record = read_json(paths.server)
        if app.left == 0 and isinstance(record, dict) and record.get("pid") == os.getpid():
            try:
                paths.server.unlink()
            except OSError:
                pass
    return 0
