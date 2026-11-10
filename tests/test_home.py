import tempfile
import unittest
from pathlib import Path

from ez_cognition.home import key, to_local, to_shared
from ez_cognition.paths import write_text

from .helpers import home, project


class FormTest(unittest.TestCase):
    def test_a_wsl_path_on_a_windows_drive(self):
        shared = to_shared("/mnt/d/_NewFactory/datamining", "wsl", "Ubuntu")
        self.assertEqual(shared, "D:\\_NewFactory\\datamining")
        self.assertEqual(to_local(shared, "wsl", "Ubuntu"), "/mnt/d/_NewFactory/datamining")
        self.assertEqual(to_local(shared, "windows"), shared)
        self.assertIsNone(to_local(shared, "posix"))
        self.assertEqual(to_local("D:\\", "wsl"), "/mnt/d")

    def test_a_path_inside_wsl(self):
        shared = to_shared("/home/blank/project", "wsl", "Ubuntu")
        self.assertEqual(shared, "\\\\wsl.localhost\\Ubuntu\\home\\blank\\project")
        self.assertEqual(to_local(shared, "wsl", "Ubuntu"), "/home/blank/project")
        self.assertEqual(to_local(shared, "windows"), shared)
        self.assertIsNone(to_local(shared, "wsl", "Debian"))
        self.assertEqual(to_local("\\\\wsl$\\ubuntu\\home\\x", "wsl", "Ubuntu"), "/home/x")

    def test_other_systems_keep_the_path(self):
        self.assertEqual(to_shared("/Users/blank/p", "posix"), "/Users/blank/p")
        self.assertEqual(to_local("/Users/blank/p", "posix"), "/Users/blank/p")
        self.assertEqual(to_shared("D:\\p", "windows"), "D:\\p")

    def test_key(self):
        self.assertEqual(key("D:\\NewFactory\\X\\"), key("d:\\newfactory\\x"))
        self.assertNotEqual(key("/home/A"), key("/home/a"))


class RegistryTest(unittest.TestCase):
    def setUp(self):
        folder, self.home = home()
        self.addCleanup(folder.cleanup)
        folder, self.paths = project()
        self.addCleanup(folder.cleanup)

    def test_add_once_and_focus(self):
        first = self.home.add(self.paths.root)
        at = self.home.registry()["focus"]["at"]
        self.home.add(Path(str(self.paths.root).upper()) if Path(str(self.paths.root).upper()).exists() else self.paths.root)
        value = self.home.registry()
        self.assertEqual(value["projects"], [first])
        self.assertGreaterEqual(value["focus"]["at"], at)
        self.assertEqual(self.home.roots(), [self.paths.root])
        self.assertNotIn(b"\r", self.home.projects.read_bytes())

    def test_add_without_focus(self):
        self.home.add(self.paths.root, focus=False)
        self.assertNotIn("focus", self.home.registry())

    def test_only_reachable_projects_with_data(self):
        with tempfile.TemporaryDirectory() as empty:
            self.home.add(self.paths.root)
            self.home.add(empty)
            value = self.home.registry()
            value["projects"].append("\\\\wsl.localhost\\Nowhere\\x" if Path("/").anchor == "/" else "/nowhere/x")
            from ez_cognition.paths import write_json
            write_json(self.home.projects, value)
            self.assertEqual(self.home.roots(), [self.paths.root])

    def test_a_broken_list(self):
        write_text(self.home.projects, "{")
        self.assertEqual(self.home.registry(), {"projects": []})
        self.home.add(self.paths.root)
        self.assertEqual(self.home.roots(), [self.paths.root])


if __name__ == "__main__":
    unittest.main()
