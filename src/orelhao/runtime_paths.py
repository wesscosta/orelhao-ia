from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Return the application root independently of the current working directory.

    ORELHAO_ROOT may override the location in packaged/appliance deployments. In
    an editable/source install this module lives in <root>/src/orelhao.
    """
    override = os.getenv("ORELHAO_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return project_root() / candidate
