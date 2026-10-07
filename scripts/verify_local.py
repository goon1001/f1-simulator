#!/usr/bin/env python3
"""Static verification for the local Podman integration and Splunk app."""

from __future__ import annotations

import json
import re
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "splunk/f1_driver_telemetry"
VIEWS = APP / "default/data/ui/views"
EXPECTED = {"f1_live_telemetry", "f1_lap_comparison", "f1_results_health"}
ERRORS: list[str] = []


def error(message: str) -> None:
    ERRORS.append(message)


def check_views() -> None:
    files = {path.stem: path for path in VIEWS.glob("*.xml")}
    if set(files) != EXPECTED:
        error(f"view set differs: expected={sorted(EXPECTED)} actual={sorted(files)}")
    for name, path in files.items():
        try:
            root = ET.fromstring(path.read_text())
        except ET.ParseError as exc:
            error(f"{name}: XML parse failed: {exc}")
            continue
        label = (root.findtext("label") or "").strip()
        definition_text = root.findtext("definition")
        if not definition_text:
            error(f"{name}: missing definition")
            continue
        try:
            definition = json.loads(definition_text)
        except json.JSONDecodeError as exc:
            error(f"{name}: JSON parse failed: {exc}")
            continue
        if definition.get("title") != label:
            error(f"{name}: XML label and JSON title differ")
        if set(definition.get("layout", {}).get("globalInputs", [])) != {
            "input_time",
            "input_mode",
        }:
            error(f"{name}: global inputs are incomplete")
        visualizations = definition.get("visualizations", {})
        structure = definition.get("layout", {}).get("structure", [])
        placed = {item.get("item") for item in structure}
        orphaned = set(visualizations) - placed
        if orphaned:
            error(f"{name}: orphan visualizations: {sorted(orphaned)}")
        width = definition["layout"]["options"]["width"]
        height = definition["layout"]["options"]["height"]
        for item in structure:
            position = item["position"]
            if position["x"] + position["w"] > width:
                error(f"{name}: {item['item']} exceeds canvas width")
            if position["y"] + position["h"] > height:
                error(f"{name}: {item['item']} exceeds canvas height")
        for data_source, spec in definition.get("dataSources", {}).items():
            query = spec.get("options", {}).get("query", "")
            if "makeresults" in query:
                error(f"{name}: {data_source} uses synthetic data")
            if "data_drivers_f1_2025" not in query:
                error(f"{name}: {data_source} does not target the F1 index")
            if "queryParameters" not in spec.get("options", {}):
                error(f"{name}: {data_source} lacks queryParameters")


def check_runtime() -> None:
    compose = (ROOT / "podman/compose.yaml").read_text()
    digest = "sha256:bf773b89d9380e09fd1c587f629768336bfe08e50fe79fb03c8a5c69c97d2f47"
    if digest not in compose:
        error("collector image is not pinned to the approved ARM64 digest")
    if "no-new-privileges" not in compose or "cap_drop" not in compose:
        error("collector hardening flags are missing")
    if "127.0.0.1:${F1_UI_PORT:-8501}:8501/tcp" not in compose:
        error("collector UI is not loopback-bound")


def check_secrets() -> None:
    credential_pattern = re.compile(
        r"(?i)(password|token|secret)\s*=\s*[\"']?[A-Za-z0-9_-]{20,}"
    )
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "public" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".mp4"}:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        if credential_pattern.search(text):
            error(f"possible committed credential: {path.relative_to(ROOT)}")


def check_package() -> None:
    package = ROOT / "dist/f1_driver_telemetry.tar.gz"
    if not package.exists():
        return
    with tarfile.open(package) as archive:
        for member in archive.getnames():
            if "/local/" in member or member.endswith(".env") or "/._" in member:
                error(f"forbidden package member: {member}")


def main() -> None:
    check_views()
    check_runtime()
    check_secrets()
    check_package()
    if ERRORS:
        for item in ERRORS:
            print(f"ERROR: {item}")
        raise SystemExit(1)
    print("PASS: Podman runtime, Splunk app, dashboards, package, and secret hygiene")


if __name__ == "__main__":
    main()
