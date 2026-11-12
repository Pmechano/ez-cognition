import http.client
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from ez_cognition import launch, server
from ez_cognition.home import side
from ez_cognition.paths import Paths, read_json, write_json, write_text
from ez_cognition.server import (API, APP, App, Server, bind, clean_look, clean_name, ping, running, slug)

from .helpers import home, project, task


class ServerCase(unittest.TestCase):
    def start(self, idle=60.0, tasks=None, more=0):
        """A server with one project (and `more` projects without tasks) in a temporary home."""
        folder, self.home = home()
        self.addCleanup(folder.cleanup)
        folder, self.paths = project(tasks)
        self.addCleanup(folder.cleanup)
        self.others = []
        for _ in range(more):
            folder, other = project({})
            self.addCleanup(folder.cleanup)
            self.home.add(other.root, focus=False)
            self.others.append(other)
        self.home.add(self.paths.root)
        httpd = bind(port=0)
        app = App(self.home, idle_seconds=idle, tick=0.05)
        app.heartbeat = 0.1
        httpd.app = app
        watcher = threading.Thread(target=app.watch, args=(httpd,), daemon=True)
        runner = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        runner.start()
        watcher.start()

        def stop():
            app.close()
            watcher.join(5)
            runner.join(5)
            httpd.server_close()

        self.addCleanup(stop)
        self.app, self.runner = app, runner
        self.port = httpd.server_address[1]
        self.pid = slug(self.paths.root.name)

    def request(self, method, path, body=None, headers=None):
        link = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            data = None if body is None else json.dumps(body).encode("utf-8")
            link.request(method, path, body=data, headers=headers or {})
            reply = link.getresponse()
            raw = reply.read()
            kind = reply.getheader("Content-Type") or ""
            return reply.status, (json.loads(raw) if kind.startswith("application/json") else raw)
        finally:
            link.close()

    def get(self, path, headers=None):
        return self.request("GET", path, headers=headers)

    def post(self, path, body, key=True):
        return self.request("POST", path, body, {"X-EZC": "1"} if key else {})

    def events(self):
        link = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        self.addCleanup(link.close)
        link.sendall(b"GET /api/events HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        return link

    def read_until(self, link, mark, seconds=5.0):
        got = b""
        end = time.time() + seconds
        while mark not in got and time.time() < end:
            try:
                part = link.recv(4096)
            except socket.timeout:
                break
            if not part:
                break
            got += part
        return got

    def wait(self, test, seconds=5.0):
        end = time.time() + seconds
        while time.time() < end:
            if test():
                return True
            time.sleep(0.05)
        return False


class ReadTest(ServerCase):
    def test_ping(self):
        self.start()
        info = ping(self.port)
        self.assertEqual((info["app"], info["api"], info["pages"], info["side"]), (APP, API, 0, side()))

    def test_page_and_static_files(self):
        self.start()
        code, page = self.get("/")
        self.assertEqual(code, 200)
        self.assertIn(b"/core/core.js", page)
        self.assertEqual(self.get("/core/core.js")[0], 200)
        self.assertEqual(self.get("/themes/amber.css")[0], 200)
        self.assertEqual(self.get("/themes/paper.css")[0], 200)
        self.assertEqual(self.get("/modules/steps/module.js")[0], 200)

    def test_only_the_page_files_are_served(self):
        self.start()
        for path in ("/ezc.py", "/ez_cognition/server.py", "/core/../ezc.py", "/core/%2e%2e/ezc.py",
                     "/modules/steps/check.py", "/core/..%5cezc.py", "/AGENTS.md", "/cognition-data/talk.json"):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_manifest(self):
        self.start(more=1)
        code, manifest = self.get("/api/manifest")
        self.assertEqual(code, 200)
        mine = [p for p in manifest["projects"] if p["id"] == self.pid]
        self.assertEqual(mine, [{"id": self.pid, "name": self.paths.root.name, "tasks": [{"id": "talk", "title": "Talk"}]}])
        self.assertEqual(len(manifest["projects"]), 2)
        self.assertEqual(manifest["focus"]["project"], self.pid)
        self.assertIn({"name": "steps", "css": True}, manifest["modules"])
        self.assertIn({"name": "amber", "scheme": "dark"}, manifest["themes"])
        self.assertIn({"name": "paper", "scheme": "light"}, manifest["themes"])

    def test_two_projects_with_one_name(self):
        self.start()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for base in (a, b):
                (Path(base) / "course" / "cognition-data").mkdir(parents=True)
                self.home.add(Path(base) / "course", focus=False)
            ids = [p["id"] for p in self.get("/api/manifest")[1]["projects"]]
            self.assertEqual(len(ids), 3)
            self.assertEqual(len(set(ids)), 3)
            self.assertTrue(all(i.startswith("course-") for i in ids if i != self.pid))

    def test_task(self):
        record = task()
        record["stages"] = []
        self.start(tasks={"talk": task(), "bad": record, "broken": "{"})
        code, reply = self.get("/api/task?project=%s&id=talk" % self.pid)
        self.assertEqual((code, reply["ok"], reply["problems"]), (200, True, []))
        self.assertEqual(reply["task"]["title"], "Talk")
        bad = self.get("/api/task?project=%s&id=bad" % self.pid)[1]
        self.assertEqual(bad["problems"], ["stages: no installed module uses this key"])
        self.assertFalse(self.get("/api/task?project=%s&id=broken" % self.pid)[1]["ok"])
        self.assertFalse(self.get("/api/task?project=%s&id=none" % self.pid)[1]["ok"])
        self.assertFalse(self.get("/api/task?project=%s&id=../talk" % self.pid)[1]["ok"])
        self.assertFalse(self.get("/api/task?project=none&id=talk")[1]["ok"])

    def test_media(self):
        self.start()
        code, body = self.get("/files/%s/media/robot.png" % self.pid)
        self.assertEqual((code, body[:4]), (200, b"\x89PNG"))
        link = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        link.request("GET", "/files/%s/media/robot.png" % self.pid)
        reply = link.getresponse()
        reply.read()
        link.close()
        self.assertIn("sandbox", reply.getheader("Content-Security-Policy"))
        (self.paths.data / "media" / "x.txt").write_text("x", encoding="utf-8")
        for path in ("/files/%s/media/none.png" % self.pid, "/files/%s/talk.json" % self.pid,
                     "/files/%s/media/x.txt" % self.pid, "/files/%s/media/../talk.json" % self.pid,
                     "/files/%s/media/%%2e%%2e/talk.json" % self.pid, "/files/none/media/robot.png", "/files/"):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_project_files(self):
        self.start()
        root = self.paths.root
        (root / "src").mkdir()
        (root / "src" / "risk.py").write_bytes(b"print(1)\n")
        (root / "docs").mkdir()
        (root / "docs" / "task.pdf").write_bytes(b"%PDF-1.4\n")
        (root / "page.html").write_text("<script>alert(1)</script>", encoding="utf-8")
        (root / "handbook.local.md").write_text("private", encoding="utf-8")
        (root / ".env").write_text("KEY=1", encoding="utf-8")
        (root / ".git").mkdir()
        (root / ".git" / "config").write_text("x", encoding="utf-8")

        link = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        for path, kind, sandbox in (("src/risk.py", "text/plain; charset=utf-8", True),
                                    ("page.html", "text/plain; charset=utf-8", True),
                                    ("docs/task.pdf", "application/pdf", False)):
            link.request("GET", "/raw/%s/%s" % (self.pid, path))
            reply = link.getresponse()
            reply.read()
            self.assertEqual((reply.status, reply.getheader("Content-Type")), (200, kind), path)
            self.assertEqual("sandbox" in (reply.getheader("Content-Security-Policy") or ""), sandbox, path)
        link.close()
        self.assertEqual(self.get("/raw/%s/src/risk.py" % self.pid)[1], b"print(1)\n")
        for path in ("handbook.local.md", ".env", ".git/config", "src/none.py", "../x", "%2e%2e/x", "src", ""):
            self.assertEqual(self.get("/raw/%s/%s" % (self.pid, path))[0], 404, path)
        self.assertEqual(self.get("/raw/none/src/risk.py")[0], 404)

        code, body = self.get("/api/dir?project=%s&path=" % self.pid)
        names = [(e["name"], e["dir"]) for e in body["entries"]]
        self.assertEqual(names[:3], [("cognition-data", True), ("docs", True), ("src", True)])
        self.assertIn(("page.html", False), names)
        self.assertFalse({"handbook.local.md", ".env", ".git"} & {n for n, _ in names})
        self.assertEqual(self.get("/api/dir?project=%s&path=src/" % self.pid)[1]["entries"],
                         [{"name": "risk.py", "dir": False, "size": 9}])
        for path in ("../", ".git", "src/risk.py", "none/"):
            self.assertFalse(self.get("/api/dir?project=%s&path=%s" % (self.pid, path))[1]["ok"], path)

    def test_the_file_viewer_is_a_page_file(self):
        self.start()
        for path in ("/core/view.html", "/core/view.js", "/core/view.css"):
            self.assertEqual(self.get(path)[0], 200, path)

    def test_another_host_is_refused(self):
        self.start()
        self.assertEqual(self.get("/api/manifest", {"Host": "evil.example:%d" % self.port})[0], 403)
        self.assertEqual(self.get("/api/manifest", {"Host": "localhost:%d" % self.port})[0], 200)


class StateTest(ServerCase):
    def test_defaults(self):
        self.start()
        code, state = self.get("/api/state?project=%s" % self.pid)
        self.assertEqual(code, 200)
        self.assertEqual(state, {"user": {"name": "", "theme": "auto", "motion": True, "language": "zh", "notes": False}, "view": {}})
        self.assertEqual(self.get("/api/state")[1]["user"]["name"], "")

    def test_write_needs_the_header(self):
        self.start()
        self.assertEqual(self.post("/api/state", {"project": self.pid, "user": {"name": "blank"}}, key=False)[0], 403)
        self.assertFalse(self.paths.user.exists())
        self.assertEqual(self.post("/api/stop", {}, key=False)[0], 403)

    def test_write(self):
        self.start()
        view = {"talk": {"open": {"step:risk": True}, "seen": {"risk": "abc"}}}
        body = {"project": self.pid, "user": {"name": "blank", "theme": "paper", "motion": False}, "view": view}
        code, reply = self.post("/api/state", body)
        self.assertEqual((code, reply["user"]["name"], reply["user"]["theme"]), (200, "blank", "paper"))
        state = self.get("/api/state?project=%s" % self.pid)[1]
        self.assertEqual(state["user"]["motion"], False)
        self.assertEqual(state["view"], view)
        self.assertEqual(read_json(self.paths.user), {"name": "blank"})
        self.assertEqual(read_json(self.home.user), {"theme": "paper", "motion": False})
        self.assertNotIn(b"\r", self.paths.view.read_bytes())

    def test_the_name_belongs_to_a_project_and_the_look_to_all(self):
        self.start(more=1)
        self.post("/api/state", {"project": self.pid, "user": {"name": "blank", "theme": "paper"}})
        other = slug(self.others[0].root.name)
        user = self.get("/api/state?project=%s" % other)[1]["user"]
        self.assertEqual((user["name"], user["theme"]), ("", "paper"))

    def test_the_notes_switch_is_part_of_the_look(self):
        self.start()
        self.post("/api/state", {"project": self.pid, "user": {"notes": True}})
        self.assertEqual(read_json(self.home.user), {"notes": True})
        self.assertTrue(self.get("/api/state?project=%s" % self.pid)[1]["user"]["notes"])

    def test_bad_values_are_not_stored(self):
        self.start()
        self.post("/api/state", {"project": self.pid, "user": {"name": "blank"}})
        self.post("/api/state", {"project": self.pid, "user": {"name": "../x", "theme": "none", "motion": "yes", "extra": 1}})
        self.assertEqual(read_json(self.paths.user), {"name": "blank"})
        self.assertEqual(read_json(self.home.user), {})
        self.assertEqual(self.post("/api/state", {"project": self.pid, "view": []})[0], 400)
        self.assertEqual(self.post("/api/state", {"view": {}})[0], 400)
        self.assertEqual(self.post("/api/none", {})[0], 404)

    def test_clean(self):
        self.assertEqual(clean_name({"name": ""}, {"name": "blank"}), {"name": ""})
        self.assertEqual(clean_name("x", {"name": "blank", "theme": "amber"}), {"name": "blank"})
        self.assertEqual(clean_look({"language": "en", "theme": "auto"}, None), {"language": "en", "theme": "auto"})
        self.assertEqual(clean_look({"theme": "none"}, {"theme": "amber", "name": "x"}), {"theme": "amber"})


class LifeTest(ServerCase):
    def test_bind_when_the_system_refuses_the_ports(self):
        def picky(address, handler):
            if address[1] != 0:
                raise OSError("refused")
            return Server(address, handler)

        with mock.patch.object(server, "Server", picky), mock.patch.object(server, "ping", return_value=None):
            httpd = bind()
        self.addCleanup(httpd.server_close)
        self.assertGreater(httpd.server_address[1], 0)

    def test_the_default_port_and_its_override(self):
        self.assertEqual(server.DEFAULT_PORT, 22267)
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        with mock.patch.dict(os.environ, {server.PORT_ENV: str(port)}):
            other = bind()
        self.addCleanup(other.server_close)
        self.assertEqual(other.server_address[1], port)

    def test_bind_when_a_server_runs(self):
        self.start()
        with mock.patch.object(server, "DEFAULT_PORT", self.port):
            self.assertIsNone(bind())

    def test_bind_passes_the_server_of_another_home(self):
        self.start()
        folder, other = home()
        self.addCleanup(folder.cleanup)
        with mock.patch.object(server, "DEFAULT_PORT", self.port):
            self.assertIsNone(bind(home=self.home))
            httpd = bind(home=other)
        self.addCleanup(httpd.server_close)
        self.assertNotEqual(httpd.server_address[1], self.port)

    def test_bind_passes_a_server_of_version_one(self):
        self.start()
        with mock.patch.object(server, "DEFAULT_PORT", self.port), \
                mock.patch.object(server, "ping", return_value={"app": APP, "root": "x"}):
            httpd = bind()
        self.addCleanup(httpd.server_close)
        self.assertNotEqual(httpd.server_address[1], self.port)

    def test_a_page_is_told_about_a_change(self):
        self.start()
        link = self.events()
        self.assertIn(b"retry: 2000", self.read_until(link, b"retry: 2000"))
        self.assertTrue(self.wait(lambda: self.app.pages == 1))
        record = task()
        record["goal"] = "A new goal."
        (self.paths.data / "talk.json").write_text(json.dumps(record), encoding="utf-8")
        self.assertIn(b"event: change", self.read_until(link, b"event: change"))

    def test_a_page_is_told_about_a_new_project(self):
        self.start()
        link = self.events()
        self.read_until(link, b"retry: 2000")
        folder, other = project({})
        self.addCleanup(folder.cleanup)
        self.home.add(other.root)
        self.assertIn(b"event: change", self.read_until(link, b"event: change"))

    def test_a_closed_page_is_found(self):
        self.start()
        link = self.events()
        self.assertTrue(self.wait(lambda: self.app.pages == 1))
        link.close()
        self.assertTrue(self.wait(lambda: self.app.pages == 0))

    def test_stops_when_no_page_is_open(self):
        self.start(idle=0.3)
        self.assertTrue(self.wait(lambda: not self.runner.is_alive()))
        self.assertIsNone(ping(self.port, timeout=0.3))

    def test_stays_without_an_idle_limit(self):
        self.start(idle=None)
        time.sleep(0.5)
        self.assertTrue(self.runner.is_alive())
        self.assertEqual(server.IDLE_SECONDS, None)

    def test_stays_while_a_page_is_open(self):
        self.start(idle=0.3)
        link = self.events()
        self.read_until(link, b"retry: 2000")
        time.sleep(0.8)
        self.assertTrue(self.runner.is_alive())
        link.close()
        self.assertTrue(self.wait(lambda: not self.runner.is_alive()))

    def test_stop(self):
        self.start()
        link = self.events()
        self.assertTrue(self.wait(lambda: self.app.pages == 1))
        self.assertEqual(self.post("/api/stop", {}), (200, {"ok": True}))
        self.assertTrue(self.wait(lambda: not self.runner.is_alive()))
        self.assertEqual(self.app.left, 1)

    def test_stops_when_its_plugin_folder_is_gone(self):
        self.start()
        gone = tempfile.TemporaryDirectory()
        self.addCleanup(gone.cleanup)
        plugin = Path(gone.name) / "ez-cognition"
        plugin.mkdir()
        (plugin / "ezc.py").write_text("", encoding="utf-8")
        self.app.plugin = plugin
        time.sleep(0.3)
        self.assertTrue(self.runner.is_alive())
        (plugin / "ezc.py").unlink()
        plugin.rmdir()
        self.assertTrue(self.wait(lambda: not self.runner.is_alive()))

    def test_stop_from_the_other_side(self):
        self.start()
        write_text(self.home.stop, "%d\n" % (os.getpid() + 1))  # another server
        time.sleep(0.3)
        self.assertTrue(self.runner.is_alive())
        write_text(self.home.stop, "%d\n" % os.getpid())
        self.assertTrue(self.wait(lambda: not self.runner.is_alive()))
        self.assertFalse(self.home.stop.exists())

    def test_the_record_beats(self):
        self.start()
        self.app.record = {"app": APP, "api": API, "port": self.port, "pid": os.getpid(), "side": side()}
        self.app.write_record()
        first = read_json(self.home.server)
        self.assertEqual(first["pages"], 0)
        self.events()
        self.assertTrue(self.wait(lambda: read_json(self.home.server, {}).get("pages") == 1))


class RunningTest(ServerCase):
    def record(self, **fields):
        value = {"app": APP, "api": API, "version": "9.9.9", "port": 1, "pid": 1, "side": side(), "beat": time.time()}
        value.update(fields)
        write_json(self.home.server, value)

    def test_a_server_that_answers(self):
        self.start()
        self.record(port=self.port)
        info = running(self.home)
        self.assertTrue(info["reach"])
        self.assertEqual(info["port"], self.port)
        folder, other = home()
        self.addCleanup(folder.cleanup)
        write_json(other.server, read_json(self.home.server))
        self.assertIsNone(running(other))

    def test_a_server_on_the_other_side(self):
        folder, self.home = home()
        self.addCleanup(folder.cleanup)
        self.record(side="elsewhere")
        self.assertFalse(running(self.home)["reach"])
        self.record(side="elsewhere", beat=time.time() - 60)
        self.assertIsNone(running(self.home))

    def test_a_record_without_a_server(self):
        folder, self.home = home()
        self.addCleanup(folder.cleanup)
        self.assertIsNone(running(self.home))
        self.record()
        self.assertIsNone(running(self.home))


class OpenTest(unittest.TestCase):
    def setUp(self):
        folder, self.home = home()
        self.addCleanup(folder.cleanup)
        folder, self.paths = project()
        self.addCleanup(folder.cleanup)
        patch = mock.patch.dict(os.environ, {launch.NO_WINDOW: "1"})
        patch.start()
        self.addCleanup(patch.stop)

    def test_version_key(self):
        self.assertLess(launch.version_key("0.2.0"), launch.version_key("0.10.0"))
        self.assertEqual(launch.version_key("x"), ())

    def test_open_uses_the_running_server(self):
        info = {"port": 22267, "version": launch.__version__, "side": side(), "pages": 1, "reach": True}
        with mock.patch.object(launch, "running", return_value=info), mock.patch.object(launch, "start") as start:
            url, what = launch.open_page(self.paths, self.home)
        start.assert_not_called()
        self.assertEqual(url, "http://127.0.0.1:22267/")
        self.assertIn("already open", what)
        self.assertEqual(len(self.home.registry()["projects"]), 1)

    def test_open_replaces_an_older_server(self):
        old = {"port": 22267, "version": "0.1.9", "side": side(), "pages": 0, "reach": True}
        new = {"port": 27181, "version": launch.__version__, "side": side(), "pages": 0, "reach": True}
        with mock.patch.object(launch, "running", return_value=old), \
                mock.patch.object(launch, "stop", return_value=True) as stop, \
                mock.patch.object(launch, "start", return_value=new):
            url, what = launch.open_page(self.paths, self.home)
        stop.assert_called_once()
        self.assertEqual(url, "http://127.0.0.1:27181/")

    def test_open_tells_where_the_server_runs(self):
        info = {"port": 22267, "version": launch.__version__, "side": "elsewhere", "pages": 0, "reach": False}
        with mock.patch.object(launch, "running", return_value=info):
            url, what = launch.open_page(self.paths, self.home)
        self.assertIn("elsewhere", what)

    def test_a_second_open_does_not_open_a_second_tab(self):
        info = {"port": 22267, "version": launch.__version__, "side": side(), "pages": 0, "reach": True}
        with mock.patch.dict(os.environ, {launch.NO_WINDOW: ""}), \
                mock.patch.object(launch, "running", return_value=info), \
                mock.patch.object(launch, "open_browser", return_value=True) as browser:
            self.assertIn("opened", launch.open_page(self.paths, self.home)[1])
            self.assertIn("is opening", launch.open_page(self.paths, self.home)[1])
            write_text(self.home.opened, "%f\n" % (time.time() - 60))
            self.assertIn("opened", launch.open_page(self.paths, self.home)[1])
        self.assertEqual(browser.call_count, 2)

    def test_stop_on_the_other_side_writes_the_request(self):
        info = {"port": 22267, "pid": 42, "reach": False}
        with mock.patch.object(launch, "running", return_value=None):
            self.assertTrue(launch.stop(self.home, info, wait=0.5))
        self.assertEqual(self.home.stop.read_text().strip(), "42")


if __name__ == "__main__":
    unittest.main()
