"""Project the development event log into one player's visible event stream."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def visible_to(record: dict, socket: int) -> bool:
    visibility = record.get("visibility")
    if visibility == "public":
        return True
    return visibility == "private" and record.get("recipient_socket") == socket


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=int, required=True, choices=range(4))
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--since-event-id", type=int, default=0)
    args = parser.parse_args()

    appdata = os.environ.get("APPDATA")
    if not appdata:
        parser.error("APPDATA is not set")
    path = Path(appdata) / "BuckshotSplitTest" / "modbucksot" / "events.jsonl"
    try:
        with path.open(encoding="utf-8") as log:
            for line in log:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict) or record.get("match_id") != args.match_id:
                    continue
                event_id = record.get("event_id")
                if not isinstance(event_id, int) or event_id <= args.since_event_id:
                    continue
                if visible_to(record, args.socket):
                    print(json.dumps(record, ensure_ascii=False))
    except OSError as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc


if __name__ == "__main__":
    main()
