"""Resolve Jono's central method separately from one client's working data."""

from __future__ import annotations

import os
from pathlib import Path


def method_root() -> Path:
    return Path(__file__).resolve().parent.parent


def workspace_root() -> Path:
    configured = os.environ.get("SEO_BLUEPRINT_WORKSPACE")
    if configured:
        return Path(configured).expanduser().resolve()

    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".pocket-ceo-client").is_file():
            return candidate

    return method_root()
