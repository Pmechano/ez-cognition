import http.client
import json
import socket
import threading
import time
import unittest
from unittest import mock

from ez_cognition.paths import read_json
from ez_cognition import server
from ez_cognition.server import App, Server, bind, clean_user, default_port, ping, same_root

from .helpers import project, task


class ServerCase(unittest.TestCase):
    def start(self, idle=60.0, tasks=None):
        folder, paths = project(tasks)
        httpd = bind(paths, port=0)
        app = App(paths, idle_seconds=idle, tick=0.05)
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
            folder.cleanup()

        self.addCleanup(stop)
        self.paths, self.app, self.runner = paths, app, runner
        self.port = httpd.server_address[1]

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
        self.assertEqual(info["app"], "ez-cognition")
        self.assertTrue(same_root(info["root"], self.paths.root))
        self.assertEqual(info["pages"], 0)

    def test_page_and_static_files(self):
        self.start()
        code, page = self.get("/")
        self.assertEqual(code, 200)
        self.assertIn(b"/core/core.js", page)
        self.assertEqual(self.get("/core/core.js")[0], 200)
        self.assertEqual(self.get("/themes/amber.css")[0], 200)
        self.assertEqual(self.get("/modules/steps/module.js")[0], 200)

    def test_only_the_page_files_are_served(self):
        self.start()
        for path in ("/ezc.py", "/ez_cognition/server.py", "/core/../ezc.py", "/core/%2e%2e/ezc.py",
                     "/modules/steps/check.py", "/core/..%5cezc.py", "/AGENTS.md", "/cognition-data/talk.json"):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_manifest(self):
        self.start()
        code, manifest = self.get("/api/manifest")
        self.assertEqual(code, 200)
        self.assertEqual(manifest["tasks"], [{"id": "talk", "title": "Talk"}])
        self.assertIn({"name": "steps", "css": True}, manifest["modules"])
        self.assertIn("amber", manifest["themes"])

    def test_task(self):
        record = task()
        record["stages"] = []
        self.start(tasks={"talk": task(), "bad": record, "broken": "{"})
        code, reply = self.get("/api/task?id=talk")
        self.assertEqual((code, reply["ok"], reply["problems"]), (200, True, []))
        self.assertEqual(reply["task"]["title"], "Talk")
        self.assertEqual(self.get("/api/task?id=bad")[1]["problems"], ["stages: no installed module uses this key"])
        self.assertFalse(self.get("/api/task?id=broken")[1]["ok"])
        self.assertFalse(self.get("/api/task?id=none")[1]["ok"])
        self.assertFalse(self.get("/api/task?id=../talk")[1]["ok"])

    def test_another_host_is_refused(self):
        self.start()
        self.assertEqual(self.get("/api/manifest", {"Host": "evil.example:%d" % self.port})[0], 403)
        self.assertEqual(self.get("/api/manifest", {"Host": "localhost:%d" % self.port})[0], 200)


class StateTest(ServerCase):
    def test_defaults(self):
        self.start()
        code, state = self.get("/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(state, {"user": {"name": "", "theme": "amber", "motion": True, "language": "zh"}, "view": {}})

    def test_write_needs_the_header(self):
        self.start()
        self.assertEqual(self.post("/api/state", {"user": {"name": "blank"}}, key=False)[0], 403)
        self.assertFalse(self.paths.user.exists())
        self.assertEqual(self.post("/api/stop", {}, key=False)[0], 403)

    def test_write(self):
        self.start()
        view = {"talk": {"open": {"step:risk": True}, "seen": {"risk": "abc"}}}
        code, reply = self.post("/api/state", {"user": {"name": "blank", "motion": False}, "view": view})
        self.assertEqual(code, 200)
        self.assertEqual(reply["user"]["name"], "blank")
        state = self.get("/api/state")[1]
        self.assertEqual(state["user"]["motion"], False)
        self.assertEqual(state["view"], view)
        self.assertNotIn(b"\r", self.paths.view.read_bytes())

    def test_bad_values_are_not_stored(self):
        self.start()
        self.post("/api/state", {"user": {"name": "blank"}})
        self.post("/api/state", {"user": {"name": "../x", "theme": "none", "motion": "yes", "extra": 1}})
        self.assertEqual(read_json(self.paths.user), {"name": "blank"})
        self.assertEqual(self.post("/api/state", {"view": []})[0], 400)
        self.assertEqual(self.post("/api/none", {})[0], 404)

    def test_clean_user(self):
        self.assertEqual(clean_user({"name": ""}, {"name": "blank"}), {"name": ""})
        self.assertEqual(clean_user("x", {"name": "blank"}), {"name": "blank"})
        self.assertEqual(clean_user({"language": "en"}, None), {"language": "en"})


class LifeTest(ServerCase):
    def test_port_is_stable(self):
        self.start()
        port = default_port(self.paths.root)
        self.assertEqual(port, default_port(str(self.paths.root)))
        self.assertTrue(20000 <= port < 40000)

    def test_bind_when_the_system_refuses_the_ports(self):
        folder, paths = project()
        self.addCleanup(folder.cleanup)

        def picky(address, handler):
            if address[1] != 0:
                raise OSError("refused")
            return Server(address, handler)

        with mock.patch.object(server, "Server", picky), mock.patch.object(server, "ping", return_value=None):
            httpd = bind(paths)
        self.addCleanup(httpd.server_close)
        self.assertGreater(httpd.server_address[1], 0)

    def test_bind_when_this_project_has_a_server(self):
        self.start()
        with mock.patch.object(server, "default_port", return_value=self.port):
            self.assertIsNone(bind(self.paths))

    def test_a_page_is_told_about_a_change(self):
        self.start()
        link = self.events()
        self.assertIn(b"retry: 2000", self.read_until(link, b"retry: 2000"))
        self.assertTrue(self.wait(lambda: self.app.pages == 1))
        record = task()
        record["goal"] = "A new goal."
        (self.paths.data / "talk.json").write_text(json.dumps(record), encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
