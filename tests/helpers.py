"""Shared test data."""

import copy
import json
import tempfile
from pathlib import Path

from ez_cognition.paths import Paths

TASK = {
    "title": "Talk",
    "goal": "Say one thing in ten minutes.",
    "sources": ["docs/syllabus.md"],
    "logistics": {
        "summary": "2026-12-07, 10 minutes",
        "items": [{"label": "Date", "value": "2026-12-07", "from": "docs/syllabus.md"}],
    },
    "steps": [
        {"id": "risk", "title": "Show the risk", "ask": "Explain the risk.", "detail": ["ILO1"]},
        {"id": "defense", "title": "Compare the defenses", "ask": "Compare the defenses."},
    ],
    "answers": {
        "risk": {
            "answer": "Start with one instruction.",
            "detail": ["Then give the claim."],
            "directions": [{"id": "review-layer", "who": "blank", "explores": "A review layer.", "found": "Not yet."}],
        }
    },
}


def task():
    return copy.deepcopy(TASK)


def project(tasks=None):
    """A temporary project. Returns (TemporaryDirectory, Paths)."""
    folder = tempfile.TemporaryDirectory()
    paths = Paths(folder.name)
    paths.data.mkdir()
    for name, value in (tasks if tasks is not None else {"talk": task()}).items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        (paths.data / (name + ".json")).write_text(text, encoding="utf-8", newline="\n")
    return folder, paths


def home():
    """A temporary ~/.ez-cognition. Returns (TemporaryDirectory, Home)."""
    from ez_cognition.home import Home

    folder = tempfile.TemporaryDirectory()
    return folder, Home(Path(folder.name) / ".ez-cognition")
