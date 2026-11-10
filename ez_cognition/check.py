"""Validate the task records.

The core knows only `core.schema.json`. Each module in `modules/` can add:

- `schema.json`: a JSON Schema for the top-level keys that the module uses.
- `check.py`: `check(task) -> list of messages`, for rules that a schema
  cannot express. It runs only when the module's schema passed.

The validator supports the small part of JSON Schema that these files use:
type, enum, minLength, pattern, minItems, items, required, properties and
additionalProperties.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .paths import ID_RE, PLUGIN, Paths, load_json, read_json

TYPES = {
    "string": (str,),
    "array": (list,),
    "object": (dict,),
    "boolean": (bool,),
    "integer": (int,),
    "number": (int, float),
}
NAMES = {
    "string": "text",
    "array": "a list",
    "object": "an object",
    "boolean": "true or false",
    "integer": "a whole number",
    "number": "a number",
}


def _at(where: str, key: Any) -> str:
    if isinstance(key, int):
        return "%s[%d]" % (where, key)
    return "%s.%s" % (where, key) if where else str(key)


def _say(where: str, message: str) -> str:
    return "%s: %s" % (where, message) if where else message


def validate(value: Any, schema: Dict[str, Any], where: str, out: List[str]) -> None:
    kind = schema.get("type")
    if kind:
        ok = isinstance(value, TYPES[kind])
        if isinstance(value, bool) and kind != "boolean":
            ok = False
        if not ok:
            out.append(_say(where, "must be %s" % NAMES[kind]))
            return
    if "enum" in schema and value not in schema["enum"]:
        out.append(_say(where, "must be one of: %s" % ", ".join(map(str, schema["enum"]))))
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            out.append(_say(where, "must not be empty"))
        elif "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(_say(where, schema.get("patternHint") or "must match %s" % schema["pattern"]))
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(_say(where, "must have at least %d item(s)" % schema["minItems"]))
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], _at(where, index), out)
    elif isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                out.append(_say(where, 'missing "%s"' % key))
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                validate(item, props[key], _at(where, key), out)
            elif extra is False:
                out.append(_say(_at(where, key), "unknown key"))
            elif isinstance(extra, dict):
                validate(item, extra, _at(where, key), out)


def module_dirs() -> List[Path]:
    """The installed modules: the folders in modules/ that have a module.js."""
    base = PLUGIN / "modules"
    if not base.is_dir():
        return []
    return sorted(d for d in base.iterdir() if d.is_dir() and (d / "module.js").is_file())


def _schemas() -> List[Tuple[str, Dict[str, Any], Any]]:
    """(name, schema, hook) for the core and for each module."""
    found: List[Tuple[str, Dict[str, Any], Any]] = [
        ("core", load_json(Path(__file__).with_name("core.schema.json")), None)
    ]
    for folder in module_dirs():
        schema = read_json(folder / "schema.json")
        hook = None
        hook_file = folder / "check.py"
        if hook_file.is_file():
            spec = importlib.util.spec_from_file_location("ezc_module_%s" % folder.name, hook_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            hook = getattr(module, "check", None)
        if isinstance(schema, dict) or hook:
            found.append((folder.name, schema if isinstance(schema, dict) else {}, hook))
    return found


def check_task(task: Any) -> List[str]:
    """The problems in one task record. An empty list means that it is correct."""
    if not isinstance(task, dict):
        return ["the task record must be an object"]
    problems: List[str] = []
    known = set()
    for name, schema, hook in _schemas():
        known.update(schema.get("properties", {}))
        mine: List[str] = []
        validate(task, dict(schema, additionalProperties=True), "", mine)
        if not mine and hook:
            try:
                mine.extend(hook(task))
            except Exception as err:  # a hook must not stop the check
                mine.append("the check of module %s failed: %r" % (name, err))
        problems.extend(mine)
    for key in task:
        if key not in known:
            problems.append("%s: no installed module uses this key" % key)
    return problems


def check_project(paths: Paths) -> Dict[str, List[str]]:
    """Problems for each file name. A file with no problems has an empty list."""
    report: Dict[str, List[str]] = {}
    if not paths.data.is_dir():
        report[paths.data.name] = ["this directory does not exist. The leader's agent runs `init`."]
        return report
    for file in paths.task_files():
        problems: List[str] = []
        if not ID_RE.match(file.stem):
            problems.append("the file name must be lowercase ASCII letters, digits and '-', for example talk.json")
        try:
            problems.extend(check_task(load_json(file)))
        except ValueError as err:
            problems.append(str(err))
        report[file.name] = problems
    if paths.user.is_file():
        user = read_json(paths.user)
        problems = []
        if not isinstance(user, dict):
            problems.append("must be an object")
        elif user.get("name") and not (isinstance(user["name"], str) and ID_RE.match(user["name"])):
            problems.append("name: must be lowercase ASCII letters, digits and '-'")
        if problems:
            report[".local/user.json"] = problems
    return report
