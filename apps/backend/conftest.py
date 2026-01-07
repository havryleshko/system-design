from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    """
    Ensure local packages are importable regardless of pytest rootdir selection.

    - `import app...` expects `/apps/backend` on sys.path
    - `import apps.backend...` expects repo root on sys.path
    """
    backend_root = Path(__file__).resolve().parent
    repo_root = backend_root.parent.parent

    for p in (str(repo_root), str(backend_root)):
        if p not in sys.path:
            sys.path.insert(0, p)


