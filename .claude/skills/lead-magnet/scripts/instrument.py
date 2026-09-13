#!/usr/bin/env python3
"""Tiny, fail-open runtime metrics for the hosted proposal fast path."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
from typing import Iterator


ENV_NAME = "POCKET_CEO_METRICS_DIR"
METRIC_FILES = ("timing.jsonl", "api-calls.jsonl", "api-costs.jsonl")


def _root(outdir: str | Path | None) -> Path | None:
    value = str(outdir or os.environ.get(ENV_NAME, "")).strip()
    return Path(value) if value else None


def _append(filename: str, payload: dict, outdir: str | Path | None = None) -> None:
    """Append one complete line. Metrics must never become a production gate."""
    try:
        root = _root(outdir)
        if root is None:
            return
        root.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
        descriptor = os.open(root / filename, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, encoded)
        finally:
            os.close(descriptor)
    except (OSError, TypeError, ValueError):
        return


@contextmanager
def step(name: str, outdir: str | Path | None = None) -> Iterator[None]:
    started = time.monotonic()
    try:
        yield
    finally:
        _append("timing.jsonl", {"step": name, "ms": round((time.monotonic() - started) * 1000)}, outdir)


def count_call(endpoint: str, outdir: str | Path | None = None, *, tasks: int = 1) -> None:
    _append("api-calls.jsonl", {"endpoint": endpoint, "calls": 1, "tasks": max(0, int(tasks))}, outdir)


def record_cost(endpoint: str, usd: float, outdir: str | Path | None = None) -> None:
    """Persist reported provider cost as soon as its response arrives."""
    try:
        value = max(0.0, float(usd or 0))
    except (TypeError, ValueError):
        return
    _append("api-costs.jsonl", {"endpoint": endpoint, "usd": value}, outdir)


def reset(outdir: str | Path | None = None) -> None:
    """Start one measurement window without touching evidence caches."""
    try:
        root = _root(outdir)
        if root is None:
            return
        for filename in METRIC_FILES:
            (root / filename).unlink(missing_ok=True)
    except (OSError, TypeError, ValueError):
        return


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return rows


def summarise(outdir: str | Path | None = None) -> dict:
    try:
        root = _root(outdir)
        if root is None or not root.is_dir():
            return {}
        timing: dict[str, int] = {}
        for row in _lines(root / "timing.jsonl"):
            name = str(row.get("step") or "unknown")
            timing[name] = timing.get(name, 0) + int(row.get("ms") or 0)
        calls: dict[str, int] = {}
        tasks: dict[str, int] = {}
        for row in _lines(root / "api-calls.jsonl"):
            endpoint = str(row.get("endpoint") or "unknown")
            calls[endpoint] = calls.get(endpoint, 0) + int(row.get("calls") or 0)
            tasks[endpoint] = tasks.get(endpoint, 0) + int(row.get("tasks") or 0)
        costs: dict[str, float] = {}
        for row in _lines(root / "api-costs.jsonl"):
            endpoint = str(row.get("endpoint") or "unknown")
            costs[endpoint] = costs.get(endpoint, 0.0) + float(row.get("usd") or 0)
        if not timing and not calls and not costs:
            return {}
        return {
            "timing_ms": dict(sorted(timing.items())),
            "api_calls": dict(sorted(calls.items())),
            "api_tasks": dict(sorted(tasks.items())),
            "api_cost_usd": {
                endpoint: round(value, 4) for endpoint, value in sorted(costs.items())
            },
            "api_cost_usd_total": round(sum(costs.values()), 4),
        }
    except (OSError, TypeError, ValueError):
        return {}
