"""The one local server of the page.

All projects on a computer share this server, its port and its page. The
projects come from the list in ~/.ez-cognition/projects.json, which `open`
writes. The server serves the core, the modules and the themes as static
files, the records as JSON, and the personal state. It tells the open
pages when a record or the list changes. It stops by itself when no
page has been open for a while: nothing stays resident.

An agent can be on the other side of WSL, where it cannot reach this port.
So the server also writes its state to ~/.ez-cognition/server.json every
few seconds, and it reads a stop request from ~/.ez-cognition/stop.
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
from .home import Home, key, side, to_shared, distro
from .paths import ID_RE, PLUGIN, Paths, load_json, read_json, write_json

APP = "ez-cognition"
API = 2  # 2: one server for all projects
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
# The same port on every computer, so that people and agents know where the
# page is. The system can refuse it; then the server takes one of the next.
DEFAULT_PORT = 27180
BEAT = 3.0    # seconds between two writes of server.json
FRESH = 15.0  # a server.json older than this belongs to a server that stopped
LOOK_DEFAULTS = {"theme": "auto", "motion": True, "language": "zh"}
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
SCHEME_RE = re.compile(r"color-scheme:\s*(dark|light)")


# ---------- finding the server ----------

_direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never send 127.0.0.1 to a proxy


def ping(port: int, timeout: float = 0.6) -> Optional[Dict[str, Any]]:
    """The answer of an ez-cognition server on this port, or None."""
    try:
        with _direct.open("http://127.0.0.1:%d/api/ping" % port, timeout=timeout) as reply:
            info = json.loads(reply.read().decode("utf-8"))
    except Exception:
        return None
    if isinstance(info, dict) and info.get("app") == APP:
        info["port"] = port
        return info
    return None


def running(home: Home) -> Optional[Dict[str, Any]]:
    """The running server, or None. `reach` is False when this side cannot connect to it."""
    record = read_json(home.server)
    if not isinstance(record, dict) or not isinstance(record.get("port"), int):
        return None
    info = ping(record["port"])
    if info and info.get("api") == API and key(info.get("home", "")) == home_key(home):
        info["reach"] = True
        return info
    beat = record.get("beat")
    if record.get("side") != side() and isinstance(beat, (int, float)) and abs(time.time() - beat) < FRESH:
        out = dict(record)
        out["reach"] = False
        return out
    return None


def home_key(home: Home) -> str:
    """The same for one home folder, seen from Windows or from WSL."""
    return key(to_shared(str(home.dir), side(), distro()))


# ---------- what the page can show ----------

def themes() -> List[Dict[str, str]]:
    """The theme files, and whether each one is dark or light."""
    base = PLUGIN / "themes"
    out = []
    for file in sorted(base.glob("*.css")) if base.is_dir() else []:
        try:
            found = SCHEME_RE.search(file.read_text(encoding="utf-8"))
        except OSError:
            continue
        out.append({"name": file.stem, "scheme": found.group(1) if found else "dark"})
    return out


def locales() -> List[str]:
    base = PLUGIN / "locales"
    return sorted(p.stem for p in base.glob("*.json")) if base.is_dir() else []


def clean_name(raw: Any, old: Any) -> Dict[str, Any]:
    """The name of the user in one project. Branch names use it."""
    user = {k: v for k, v in old.items() if k == "name"} if isinstance(old, dict) else {}
    name = raw.get("name") if isinstance(raw, dict) else None
    if isinstance(name, str) and (name == "" or ID_RE.match(name)):
        user["name"] = name
    return user


def clean_look(raw: Any, old: Any) -> Dict[str, Any]:
    """The look of the page. It is the same in all projects."""
    look = {k: v for k, v in old.items() if k in LOOK_DEFAULTS} if isinstance(old, dict) else {}
    if not isinstance(raw, dict):
        return look
    if raw.get("theme") == "auto" or raw.get("theme") in [t["name"] for t in themes()]:
        look["theme"] = raw["theme"]
    if isinstance(raw.get("motion"), bool):
        look["motion"] = raw["motion"]
    language = raw.get("language")
    if isinstance(language, str) and LANGUAGE_RE.match(language):
        look["language"] = language
    return look


def slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30].strip("-")
    return out or "project"


class Project:
    def __init__(self, pid: str, root: Path) -> None:
        self.id = pid
        self.paths = Paths(root)
        self.name = self.paths.root.name
        self.shared = to_shared(str(self.paths.root), side(), distro())


class App:
    """The state that the request threads share."""

    def __init__(self, home: Home, idle_seconds: float = IDLE_SECONDS, tick: float = 1.0) -> None:
        self.home = home
        self.idle_seconds = idle_seconds
        self.tick = tick
        self.heartbeat = 5.0  # seconds between two lines to a page; a closed page is found then
        self.version = 0
        self.pages = 0
        self.closing = False
        self.left = 0  # the pages that were open when the server stopped
        self.record: Optional[Dict[str, Any]] = None  # what serve() writes to server.json
        self.changed = threading.Condition()
        self.first = self.stamp()  # taken now, so a change before watch() starts is not lost

    # ---------- projects ----------

    def projects(self) -> List[Project]:
        roots = self.home.roots()
        names = [slug(root.name) for root in roots]
        out = []
        for root, name in zip(roots, names):
            if names.count(name) > 1:
                code = "%04x" % (zlib.crc32(key(to_shared(str(root), side(), distro())).encode("utf-8")) & 0xFFFF)
                name = "%s-%s" % (name[:25], code)
            out.append(Project(name, root))
        return out

    def project(self, pid: Any) -> Optional[Project]:
        for project in self.projects():
            if project.id == pid:
                return project
        return None

    def stamp(self) -> List[Any]:
        """A value that changes when the list of projects or a record changes."""
        out: List[Any] = []
        for file in [self.home.projects] + [f for p in self.projects() for f in p.paths.task_files()]:
            try:
                stat = file.stat()
            except OSError:
                continue
            out.append((str(file), stat.st_mtime_ns, stat.st_size))
        return out

    # ---------- answers ----------

    def look(self) -> Dict[str, Any]:
        look = dict(LOOK_DEFAULTS)
        look.update(clean_look(read_json(self.home.user), {}))
        return look

    def user(self, project: Optional[Project]) -> Dict[str, Any]:
        user = self.look()
        stored = read_json(project.paths.user) if project else None
        user["name"] = clean_name(stored, {}).get("name", "")
        return user

    def manifest(self) -> Dict[str, Any]:
        projects = []
        for project in self.projects():
            tasks = []
            for file in project.paths.task_files():
                if not ID_RE.match(file.stem):
                    continue
                task = read_json(file)
                title = task.get("title") if isinstance(task, dict) else None
                tasks.append({"id": file.stem, "title": title if isinstance(title, str) and title.strip() else file.stem})
            projects.append({"id": project.id, "name": project.name, "tasks": tasks})
        focus = None
        asked = self.home.registry().get("focus") or {}
        for project in self.projects():
            if isinstance(asked.get("project"), str) and key(asked["project"]) == key(project.shared):
                focus = {"project": project.id, "at": asked.get("at", 0)}
        return {
            "app": APP,
            "version": __version__,
            "projects": projects,
            "focus": focus,
            "modules": [{"name": d.name, "css": (d / "module.css").is_file()} for d in module_dirs()],
            "themes": themes(),
            "locales": locales(),
        }

    def task(self, pid: str, task_id: str) -> Dict[str, Any]:
        project = self.project(pid)
        if project is None:
            return {"ok": False, "error": "no project with this id"}
        file = project.paths.task_file(task_id)
        if file is None:
            return {"ok": False, "error": "no record with this id"}
        try:
            task = load_json(file)
        except ValueError as err:
            return {"ok": False, "error": "%s: %s" % (file.name, err)}
        return {"ok": isinstance(task, dict), "task": task, "problems": check_task(task), "file": file.name}

    # ---------- life ----------

    def write_record(self) -> None:
        if self.record is None:
            return
        self.record.update(pages=self.pages, beat=time.time())
        try:
            write_json(self.home.server, self.record)
        except OSError:
            pass

    def asked_to_stop(self) -> bool:
        try:
            target = self.home.stop.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        if target not in ("", str(os.getpid())):
            return False
        try:
            self.home.stop.unlink()
        except OSError:
            pass
        return True

    def watch(self, httpd: ThreadingHTTPServer) -> None:
        """Tell the pages about changes. Stop the server when no page is open.

        The idle time is counted in ticks, not read from a clock. When the
        computer sleeps, the count stops too, so an open page has time to
        connect again after the computer wakes.
        """
        last = self.first
        idle = 0.0
        beat_at = time.time()
        pages = self.pages
        while not self.closing:
            time.sleep(self.tick)
            if self.asked_to_stop():
                break
            now = self.stamp()
            if now != last:
                last = now
                with self.changed:
                    self.version += 1
                    self.changed.notify_all()
            if self.pages != pages or time.time() - beat_at >= BEAT:
                pages, beat_at = self.pages, time.time()
                self.write_record()
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
        query = parse_qs(url.query)
        path = url.path
        if path == "/":
            return self._static("core/index.html")
        if path == "/api/ping":
            return self._json({"app": APP, "api": API, "version": __version__, "pid": os.getpid(),
                               "pages": self.app.pages, "side": side(), "plugin": str(PLUGIN),
                               "home": to_shared(str(self.app.home.dir), side(), distro())})
        if path == "/api/manifest":
            return self._json(self.app.manifest())
        if path == "/api/task":
            return self._json(self.app.task((query.get("project") or [""])[0], (query.get("id") or [""])[0]))
        if path == "/api/state":
            project = self.app.project((query.get("project") or [""])[0])
            view = read_json(project.paths.view) if project else None
            return self._json({"user": self.app.user(project), "view": view if isinstance(view, dict) else {}})
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
        project = self.app.project(body.get("project"))
        if "view" in body and (project is None or not isinstance(body["view"], dict)):
            return self._no(400, "view needs a project, and it must be an object")
        if "user" in body:
            home = self.app.home
            write_json(home.user, clean_look(body["user"], read_json(home.user)))
            if project and isinstance(body["user"], dict) and "name" in body["user"]:
                write_json(project.paths.user, clean_name(body["user"], read_json(project.paths.user)))
        if "view" in body:
            write_json(project.paths.view, body["view"])
        self._json({"ok": True, "user": self.app.user(project)})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, "reuse address" lets two servers take the same port.
    allow_reuse_address = os.name != "nt"


def bind(port: Optional[int] = None, home: Optional[Home] = None) -> Optional[Server]:
    """A server on the default port or one of the next. None: the server of this home runs.

    A server of another home (a test, another user) keeps its port; this one takes the next.

    The system can refuse a whole range of ports (Windows reserves ranges for
    Hyper-V and WSL). The last candidate is 0: a port that the system chooses.
    """
    first = DEFAULT_PORT if port is None else port
    last_error: Optional[OSError] = None
    for candidate in ([0] if port == 0 else [*range(first, first + 20), 0]):
        try:
            return Server(("127.0.0.1", candidate), Handler)
        except OSError as err:
            last_error = err
            other = ping(candidate)
            if other and other.get("api") == API and (home is None or key(other.get("home", "")) == home_key(home)):
                return None
    raise OSError("no free port near %d: %s" % (first, last_error))


def serve(home: Home, idle_seconds: float = IDLE_SECONDS, port: Optional[int] = None) -> int:
    """Run the server until no page has been open for `idle_seconds`."""
    other = running(home)
    if other:
        print("a server runs already: http://127.0.0.1:%d/ (%s)" % (other["port"], other.get("side")), flush=True)
        return 0
    httpd = bind(port, home)
    if httpd is None:
        return 0
    app = App(home, idle_seconds)
    httpd.app = app  # type: ignore[attr-defined]
    app.record = {"app": APP, "api": API, "version": __version__, "port": httpd.server_address[1],
                  "pid": os.getpid(), "side": side(), "plugin": str(PLUGIN)}
    try:
        home.stop.unlink()  # an old request is not for this server
    except OSError:
        pass
    app.write_record()
    print("http://127.0.0.1:%d/ (%s, ez-cognition %s)" % (app.record["port"], side(), __version__), flush=True)
    threading.Thread(target=app.watch, args=(httpd,), daemon=True).start()
    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        httpd.server_close()
        # A page that was open tries to connect again. The record stays for
        # it (with an old beat), so the next `open` does not make a second tab.
        record = read_json(home.server)
        if isinstance(record, dict) and record.get("pid") == os.getpid():
            try:
                if app.left == 0:
                    home.server.unlink()
                else:
                    record["beat"] = 0
                    write_json(home.server, record)
            except OSError:
                pass
    return 0
