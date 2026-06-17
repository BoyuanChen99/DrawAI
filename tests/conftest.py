from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def pytest_sessionstart(session):  # type: ignore[no-untyped-def]
    if str(os.getenv("DRAWAI_ENSURE_LOCAL_CODEX_GATEWAY", "")).strip().lower() not in {"1", "true", "yes", "on"}:
        return
    script = REPO_ROOT / "scripts/ensure_local_codex_gateway.py"
    subprocess.run([sys.executable, str(script), "--quiet"], cwd=REPO_ROOT, check=True)
