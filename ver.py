import os
import subprocess
import sys

major = 1
minor = 2
strng = f"{major}.{minor}"


def _runtime_git_describe():
    if getattr(sys, "frozen", False):
        return None
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


try:
    from _build_info import COMMIT as _BUILT_COMMIT
except Exception:
    _BUILT_COMMIT = None

commit = _runtime_git_describe() or _BUILT_COMMIT or "unknown"
full = f"{strng} ({commit})"
