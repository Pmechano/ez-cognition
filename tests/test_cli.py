import shutil
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
            shutil.rmtree(paths.data)
            (paths.root / "AGENTS.md").write_bytes(b"# Notes\r\n\r\nKeep this.\r\n")
            code, out = run("--root", str(paths.root), "init")
            self.assertEqual(code, 0)
            self.assertIn("wrote the ez-cognition part", out)
            first = (paths.root / "AGENTS.md").read_bytes()
            self.assertNotIn(b"\r", first)
            self.assertTrue(first.startswith(b"# Notes\n\nKeep this.\n\n<!-- ez-cognition: begin."))
            self.assertIn(b"| `journal.md` | yes |", first)
            self.assertIn(b"This project uses ez-cognition.", first)
            self.assertEqual((paths.data / ".gitignore").read_bytes(), b".local/\n")
            self.assertEqual((paths.root / "CLAUDE.md").read_bytes(), b"@AGENTS.md\n")
            self.assertTrue((paths.root / "handbook.md").read_text(encoding="utf-8").startswith("# Handbook"))
            self.assertTrue((paths.root / "journal.md").read_text(encoding="utf-8").startswith("# Journal"))
            self.assertTrue((paths.root / "human.md").read_text(encoding="utf-8").startswith("# Human notes"))
            self.assertIn(b"| `human.md` | yes |", first)
            self.assertEqual((paths.root / ".gitignore").read_bytes(), b"handbook.local.md\n")
            handbook = (paths.root / "handbook.md").read_bytes()

            code, out = run("--root", str(paths.root), "init")
            self.assertEqual(code, 0)
            self.assertNotIn("added", out)
            self.assertNotIn("created", out)
            self.assertEqual((paths.root / "AGENTS.md").read_bytes(), first)
            self.assertEqual((paths.root / "handbook.md").read_bytes(), handbook)
            self.assertEqual((paths.root / ".gitignore").read_bytes(), b"handbook.local.md\n")

    def test_init_replaces_its_own_part_only(self):
        folder, paths = project({})
        with folder:
            from ez_cognition.cli import BEGIN, END
            (paths.root / "AGENTS.md").write_text("# Mine\n\n%s\nold rules\n%s\n\n## After\nkeep\n" % (BEGIN, END), encoding="utf-8")
            run("--root", str(paths.root), "init")
            text = (paths.root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertNotIn("old rules", text)
            self.assertEqual(text.count(BEGIN), 1)
            self.assertTrue(text.startswith("# Mine\n\n" + BEGIN))
            self.assertTrue(text.endswith("## After\nkeep\n"))
            self.assertIn("## Project notes", text)

    def test_init_adds_to_an_existing_gitignore(self):
        folder, paths = project({})
        with folder:
            (paths.root / ".gitignore").write_bytes(b"data/")
            run("--root", str(paths.root), "init")
            self.assertEqual((paths.root / ".gitignore").read_bytes(), b"data/\nhandbook.local.md\n")

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
            self.assertIn("no record", out)

    def test_open_without_the_data_directory(self):
        folder, paths = project({})
        with folder:
            shutil.rmtree(paths.data)
            code, out = run("--root", str(paths.root), "open")
            self.assertEqual(code, 1)
            self.assertIn("does not exist", out)


if __name__ == "__main__":
    unittest.main()
