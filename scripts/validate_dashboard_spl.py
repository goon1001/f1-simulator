#!/usr/bin/env python3
"""Execute every generated dashboard search against the local Splunk instance."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "splunk/f1_driver_telemetry/default/data/ui/views"
SEARCH = ROOT / "scripts/splunk_search.sh"


def main() -> None:
    failures: list[str] = []
    count = 0
    for view in sorted(VIEWS.glob("*.xml")):
        root = ET.fromstring(view.read_text())
        definition = json.loads(root.findtext("definition") or "{}")
        for name, spec in definition["dataSources"].items():
            query = spec["options"]["query"].replace("$tok_mode$", "playback")
            completed = subprocess.run(
                [str(SEARCH), query],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            count += 1
            if completed.returncode:
                failures.append(
                    f"{view.stem}/{name}: HTTP failure: {completed.stderr.strip()}"
                )
                continue
            try:
                messages = [json.loads(line) for line in completed.stdout.splitlines() if line]
            except json.JSONDecodeError as exc:
                failures.append(f"{view.stem}/{name}: invalid response: {exc}")
                continue
            errors = [
                message
                for row in messages
                for message in row.get("messages", [])
                if message.get("type") == "ERROR"
            ]
            if errors:
                failures.append(f"{view.stem}/{name}: {errors}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        raise SystemExit(1)
    print(f"PASS: {count} dashboard searches executed without SPL errors")


if __name__ == "__main__":
    main()
