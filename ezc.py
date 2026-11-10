"""Run ez-cognition without an install: python ez-cognition/ezc.py <command>"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ez_cognition.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
