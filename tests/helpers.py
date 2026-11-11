"""Shared test data."""

import copy
import json
import tempfile
from pathlib import Path

from ez_cognition.paths import Paths

TASK = {
    "title": "Talk",
    "goal": "Say **one** thing in ten minutes.",
    "sources": ["docs/syllabus.md"],
    "terms": [{"term": "Refusal", "means": "The model says no."}],
    "task": {
        "summary": "Show that a model refuses in chat but obeys a robot.",
        "cards": [
            {"title": "What the course asks", "text": "- Pick a risk\n- Explain it with $x^2$"},
            {"title": "One example", "text": "A robot gets one instruction.", "image": {"src": "media/robot.png", "alt": "A robot"}},
        ],
    },
    "steps": [
        {"id": "risk", "title": "Show the risk", "ask": "Explain the risk.", "rubric": "Excellent: clear and cited.", "for": ["talk"]},
        {"id": "defense", "title": "Compare the defenses", "ask": "Compare the defenses."},
    ],
    "answers": {
        "risk": {
            "answer": "Start with one instruction.",
            "detail": "Then give the claim.",
            "state": "doing",
            "directions": [{"id": "review-layer", "who": "blank", "explores": "A review layer.", "found": "Not yet.", "state": "done"}],
        }
    },
    "submit": {
        "summary": "2026-12-07, 10 minutes",
        "deliverables": [
            {"id": "talk", "title": "Talk", "what": "Ten minutes.", "due": "2026-12-07"},
            {"id": "report", "title": "Report", "what": "Eight pages.", "uses": ["talk"], "done": False},
        ],
        "items": [{"label": "Grading", "value": "Talk 25%", "from": "docs/syllabus.md"}],
    },
}

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


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
    (paths.data / "media").mkdir()
    (paths.data / "media" / "robot.png").write_bytes(PNG)
    return folder, paths


def home():
    """A temporary ~/.ez-cognition. Returns (TemporaryDirectory, Home)."""
    from ez_cognition.home import Home

    folder = tempfile.TemporaryDirectory()
    return folder, Home(Path(folder.name) / ".ez-cognition")
