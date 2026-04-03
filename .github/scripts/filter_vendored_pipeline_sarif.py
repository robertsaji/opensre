#!/usr/bin/env python3
"""Remove CodeQL findings under vendored e2e pipeline_code fixtures from SARIF output.

Glob-based filter actions can miss some URI forms; this script resolves artifactLocation
(uri, uriBaseId, index) and drops any result whose path lies under upstream_*/pipeline_code/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

# Substrings of normalized paths for vendored bundles checked into tests/e2e.
_VENDORED_MARKERS: tuple[str, ...] = (
    "tests/e2e/upstream_lambda/pipeline_code/",
    "tests/e2e/upstream_apache_flink_ecs/pipeline_code/",
    "tests/e2e/upstream_prefect_ecs_fargate/pipeline_code/",
    "/upstream_lambda/pipeline_code/",
    "/upstream_apache_flink_ecs/pipeline_code/",
    "/upstream_prefect_ecs_fargate/pipeline_code/",
)


def _normalize_path(raw: str) -> str:
    s = raw.replace("\\", "/")
    if s.startswith("file:"):
        return unquote(urlparse(s).path)
    return unquote(s)


def _join_uri_base(uri: str, uri_base_id: str | None, bases: dict[str, str] | None) -> str:
    if not uri_base_id or not bases:
        return uri
    base = bases.get(uri_base_id)
    if not base:
        return uri
    base = base.rstrip("/") + "/"
    if uri.startswith("/"):
        return base.rstrip("/") + uri
    return base + uri


def _artifact_uri(
    art_loc: dict[str, Any],
    artifacts: list[dict[str, Any]] | None,
    original_uri_base_ids: dict[str, str] | None,
) -> str | None:
    idx = art_loc.get("index")
    if idx is not None and artifacts is not None and isinstance(idx, int) and 0 <= idx < len(artifacts):
        loc = artifacts[idx].get("location") or {}
        uri = loc.get("uri")
        if isinstance(uri, str):
            return _normalize_path(_join_uri_base(uri, loc.get("uriBaseId"), original_uri_base_ids))
    uri = art_loc.get("uri")
    if not isinstance(uri, str):
        return None
    joined = _join_uri_base(uri, art_loc.get("uriBaseId"), original_uri_base_ids)
    return _normalize_path(joined)


def _is_vendored(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(m in p for m in _VENDORED_MARKERS)


def _filter_run(run: dict[str, Any]) -> None:
    artifacts = run.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = None
    base_ids = run.get("originalUriBaseIds")
    if not isinstance(base_ids, dict):
        base_ids = None

    results = run.get("results")
    if not isinstance(results, list):
        return

    kept: list[dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        locs = r.get("locations")
        if not isinstance(locs, list) or not locs:
            kept.append(r)
            continue
        drop = False
        for loc in locs:
            if not isinstance(loc, dict):
                continue
            pl = loc.get("physicalLocation")
            if not isinstance(pl, dict):
                continue
            art_loc = pl.get("artifactLocation")
            if not isinstance(art_loc, dict):
                continue
            path = _artifact_uri(art_loc, artifacts, base_ids)
            if path is not None and _is_vendored(path):
                drop = True
                break
        if not drop:
            kept.append(r)
    run["results"] = kept


def _process_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    for run in data.get("runs", []):
        if isinstance(run, dict):
            _filter_run(run)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "sarif-results")
    if not root.is_dir():
        print(f"filter_vendored_pipeline_sarif: not a directory: {root}", file=sys.stderr)
        sys.exit(1)
    for path in sorted(root.rglob("*.sarif")):
        if path.is_file():
            _process_file(path)


if __name__ == "__main__":
    main()
