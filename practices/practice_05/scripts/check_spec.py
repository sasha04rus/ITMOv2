"""Run official Spec Kit prerequisites for this member project, on any checkout."""

import os
from pathlib import Path
import subprocess
import sys


def main():
    project = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "SPECIFY_INIT_DIR": str(project),
        "SPECIFY_FEATURE_DIRECTORY": str(project / "specs/001-subscriber-search"),
    }
    return subprocess.call(
        [
            sys.executable,
            ".specify/scripts/python/check_prerequisites.py",
            "--json",
            "--require-tasks",
            "--include-tasks",
        ],
        cwd=project,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
