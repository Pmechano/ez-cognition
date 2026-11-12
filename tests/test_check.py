import shutil
import json
import unittest
from unittest import mock

from ez_cognition import check
from ez_cognition.check import check_project, check_task, validate
from ez_cognition.paths import write_json

from .helpers import project, task


class ValidateTest(unittest.TestCase):
    def problems(self, value, schema):
        out = []
        validate(value, schema, "", out)
        return out

    def test_type(self):
        self.assertEqual(self.problems(3, {"type": "string"}), ["must be text"])
        self.assertEqual(self.problems(True, {"type": "integer"}), ["must be a whole number"])
        self.assertEqual(self.problems("x", {"type": "string"}), [])

    def test_empty_text(self):
        self.assertEqual(self.problems("  ", {"type": "string", "minLength": 1}), ["must not be empty"])

    def test_pattern_uses_the_hint(self):
        schema = {"type": "string", "pattern": "^[a-z]+$", "patternHint": "must be lowercase"}
        self.assertEqual(self.problems("A", schema), ["must be lowercase"])

    def test_object(self):
        schema = {
            "type": "object",
            "required": ["a"],
            "additionalProperties": False,
            "properties": {"a": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
        }
        self.assertEqual(self.problems({}, schema), ['missing "a"'])
        self.assertEqual(self.problems({"a": []}, schema), ["a: must have at least 1 item(s)"])
        self.assertEqual(self.problems({"a": ["x", 1]}, schema), ["a[1]: must be text"])
        self.assertEqual(self.problems({"a": ["x"], "b": 1}, schema), ["b: unknown key"])


class CheckTaskTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(check_task(task()), [])

    def test_only_the_core_keys(self):
        self.assertEqual(check_task({"title": "T", "goal": "G"}), [])

    def test_not_an_object(self):
        self.assertEqual(check_task([]), ["the record must be an object"])

    def test_missing_title(self):
        record = task()
        del record["title"]
        self.assertIn('missing "title"', check_task(record))

    def test_step_without_id(self):
        record = task()
        del record["steps"][0]["id"]
        self.assertIn('steps[0]: missing "id"', check_task(record))

    def test_bad_step_id(self):
        record = task()
        record["steps"][0]["id"] = "Risk One"
        self.assertTrue(any(p.startswith("steps[0].id: must be lowercase") for p in check_task(record)))

    def test_duplicate_step_id(self):
        record = task()
        record["steps"][1]["id"] = "risk"
        self.assertTrue(any("steps[1].id" in p and "risk" in p for p in check_task(record)), check_task(record))

    def test_answer_for_no_step(self):
        record = task()
        record["answers"]["nothing"] = {"answer": "x"}
        self.assertIn('answers.nothing: no step has the id "nothing"', check_task(record))

    def test_answer_needs_text(self):
        record = task()
        record["answers"]["defense"] = {"detail": ["x"]}
        self.assertIn('answers.defense: missing "answer"', check_task(record))

    def test_direction(self):
        record = task()
        record["answers"]["risk"]["directions"][0]["who"] = "Blank A"
        self.assertTrue(any(p.startswith("answers.risk.directions[0].who:") for p in check_task(record)))
        record = task()
        record["answers"]["risk"]["directions"].append(dict(record["answers"]["risk"]["directions"][0]))
        self.assertTrue(any("already in this step" in p for p in check_task(record)))

    def test_unknown_key(self):
        record = task()
        record["stages"] = []
        self.assertEqual(check_task(record), ["stages: no installed module uses this key"])

    def test_unknown_key_inside_a_module(self):
        record = task()
        record["steps"][0]["owner"] = "blank"
        self.assertEqual(check_task(record), ["steps[0].owner: unknown key"])

    def test_the_core_runs_with_no_module(self):
        with mock.patch.object(check, "module_dirs", return_value=[]):
            self.assertEqual(check_task({"title": "T", "goal": "G"}), [])
            self.assertEqual(check_task({"title": "T", "goal": "G", "steps": []}),
                             ["steps: no installed module uses this key"])


class ModuleRulesTest(unittest.TestCase):
    def test_deliverables(self):
        record = task()
        items = record["submit"]["deliverables"]
        items.append(dict(items[0]))
        self.assertEqual(check_task(record), ['submit.deliverables[2].id: "talk" is used by an earlier deliverable'])

    def test_the_keys_that_were_removed(self):
        record = task()
        record["steps"][0]["rubric"] = "Excellent."
        record["steps"][0]["for"] = ["talk"]
        record["submit"]["deliverables"][1]["uses"] = ["talk"]
        self.assertEqual(sorted(check_task(record)), [
            "steps[0].for: unknown key",
            "steps[0].rubric: unknown key",
            "submit.deliverables[1].uses: unknown key",
        ])

    def test_links_to_the_source(self):
        record = task()
        for good in ("https://example.org/a", "docs/a b.pdf#page=3", "src/"):
            record["steps"][0]["link"] = good
            self.assertEqual(check_task(record), [], good)
        for bad in ("/etc/passwd", "../x.pdf", "docs/../../x", ".git/config", "C:\\x.pdf", "javascript:alert(1)"):
            record["steps"][0]["link"] = bad
            self.assertEqual(len(check_task(record)), 1, bad)
            self.assertIn("steps[0].link", check_task(record)[0])

    def test_files(self):
        record = task()
        record["files"].append({"path": "docs/", "what": "Again."})
        record["files"].append({"path": "out.csv", "what": "A table.", "step": "none"})
        record["files"].append({"path": "../x", "what": "Outside."})
        record["files"].append({"path": "a.py#L3", "what": "A line."})
        problems = check_task(record)
        self.assertEqual(len(problems), 2)
        self.assertTrue(all(p.startswith("files[") and "path" in p for p in problems))
        del record["files"][4:]
        self.assertEqual(check_task(record), [
            'files[2].path: "docs/" is already in the list',
            'files[3].step: no step has the id "none"',
        ])

    def test_task_needs_questions(self):
        record = task()
        record["task"] = {"summary": "x", "questions": []}
        self.assertTrue(check_task(record))


class MediaTest(unittest.TestCase):
    def test_images_are_found(self):
        record = task()
        record["task"]["cards"][0]["text"] = "See ![a plot](media/plot.svg) and ![b](https://x.example/b.png)."
        self.assertEqual(check.images(record), [
            ("task.cards[0].text", "media/plot.svg"),
            ("task.cards[0].text", "https://x.example/b.png"),
            ("task.cards[1].image.src", "media/robot.png"),
        ])

    def test_media_problems(self):
        folder, paths = project()
        self.addCleanup(folder.cleanup)
        record = task()
        self.assertEqual(check_task(record, paths.data), [])
        record["task"]["cards"][1]["image"]["src"] = "media/none.png"
        record["answers"]["risk"]["detail"] = "![x](../secret.png) ![y](media/a/../../x.png)"
        problems = check_task(record, paths.data)
        self.assertEqual(len(problems), 3)
        self.assertIn("does not exist", problems[2] if "none" in problems[2] else " ".join(problems))
        self.assertTrue(all("media" in p for p in problems))


class CheckProjectTest(unittest.TestCase):
    def test_valid(self):
        folder, paths = project()
        with folder:
            self.assertEqual(check_project(paths), {"talk.json": []})

    def test_no_data_directory(self):
        folder, paths = project()
        with folder:
            (paths.data / "talk.json").unlink()
            shutil.rmtree(paths.data)
            self.assertEqual(list(check_project(paths)), ["cognition-data"])

    def test_file_name_and_json(self):
        folder, paths = project({"Talk One": task(), "broken": "{"})
        with folder:
            report = check_project(paths)
            self.assertTrue(report["Talk One.json"][0].startswith("the file name must be"))
            self.assertTrue(report["broken.json"][0].startswith("not valid JSON: line 1"))

    def test_user_name(self):
        folder, paths = project()
        with folder:
            write_json(paths.user, {"name": "Blank!"})
            self.assertIn(".local/user.json", check_project(paths))
            write_json(paths.user, {"name": "blank"})
            self.assertNotIn(".local/user.json", check_project(paths))

    def test_bom_is_accepted(self):
        folder, paths = project()
        with folder:
            (paths.data / "talk.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(task()).encode("utf-8"))
            self.assertEqual(check_project(paths), {"talk.json": []})


if __name__ == "__main__":
    unittest.main()
