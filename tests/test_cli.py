import contextlib
import io
import unittest

from ez_cognition.cli import main
from ez_cognition.paths import Paths, find_root, write_json, write_text

from .helpers import project, task


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


class PathsTest(unittest.TestCase):
    def test_files_have_lf_endings(self):
        folder, paths = project()
        with folder:
            write_text(paths.root / "a.txt", "one\ntwo\n")
            write_json(paths.user, {"name": "blank", "note": "中文"})
            self.assertEqual((paths.root / "a.txt").read_bytes(), b"one\ntwo\n")
            raw = paths.user.read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertIn("中文".encode("utf-8"), raw)

    def test_find_root_goes_up(self):
        folder, paths = project()
        with folder:
            deep = paths.root / "a" / "b"
            deep.mkdir(parents=True)
            self.assertEqual(find_root(deep), paths.root)

    def test_task_file_refuses_a_path(self):
        folder, paths = project()
        with folder:
            self.assertIsNotNone(paths.task_file("talk"))
            self.assertIsNone(paths.task_file("../talk"))
            self.assertIsNone(paths.task_file(".local/user"))
            self.assertIsNone(paths.task_file("none"))


class InitTest(unittest.TestCase):
    def test_init_is_repeatable_and_writes_lf(self):
        folder, paths = project({})
        with folder:
            paths.data.rmdir()
            (paths.root / "AGENTS.md").write_bytes(b"# Notes\r\n\r\nKeep this.\r\n")
            code, out = run("--root", str(paths.root), "init")
            self.assertEqual(code, 0)
            self.assertIn("added the entry line", out)
            first = (paths.root / "AGENTS.md").read_bytes()
            self.assertNotIn(b"\r", first)
            self.assertTrue(first.startswith(b"# Notes\n\nKeep this.\n\nThis project uses ez-cognition."))
            self.assertEqual((paths.data / ".gitignore").read_bytes(), b".local/\n")
            self.assertEqual((paths.root / "CLAUDE.md").read_bytes(), b"@AGENTS.md\n")

            code, out = run("--root", str(paths.root), "init")
            self.assertEqual(code, 0)
            self.assertNotIn("added", out)
            self.assertEqual((paths.root / "AGENTS.md").read_bytes(), first)

    def test_init_keeps_an_existing_claude_file(self):
        folder, paths = project({})
        with folder:
            (paths.root / "CLAUDE.md").write_bytes(b"mine\n")
            run("--root", str(paths.root), "init")
            self.assertEqual((paths.root / "CLAUDE.md").read_bytes(), b"mine\n")


class CheckCommandTest(unittest.TestCase):
    def test_ok(self):
        folder, paths = project()
        with folder:
            self.assertEqual(run("--root", str(paths.root), "check"), (0, "OK\n"))

    def test_problems(self):
        record = task()
        record["steps"][1]["id"] = "risk"
        folder, paths = project({"talk": record})
        with folder:
            code, out = run("--root", str(paths.root), "check")
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("talk.json: steps[1].id:"), out)

    def test_no_task_record(self):
        folder, paths = project({})
        with folder:
            code, out = run("--root", str(paths.root), "check")
            self.assertEqual(code, 1)
            self.assertIn("no task record", out)

    def test_open_without_the_data_directory(self):
        folder, paths = project({})
        with folder:
            paths.data.rmdir()
            code, out = run("--root", str(paths.root), "open")
            self.assertEqual(code, 1)
            self.assertIn("does not exist", out)


if __name__ == "__main__":
    unittest.main()
