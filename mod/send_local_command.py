"""Send one manual command to the isolated four-seat Buckshot test build."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "pickup_shotgun", "aim", "shoot"))
    parser.add_argument("target_socket", nargs="?", type=int)
    args = parser.parse_args()
    if (args.action in ("aim", "shoot")) != (args.target_socket is not None):
        parser.error("aim and shoot require a target socket; pickup_shotgun does not")
    if args.target_socket is not None and args.target_socket not in range(4):
        parser.error("target_socket must be 0, 1, 2, or 3")

    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("APPDATA is not set")
    directory = Path(appdata) / "BuckshotSplitTest" / "modbucksot"
    state_path = directory / "control-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"No live match state at {state_path}: {exc}") from exc

    updated = state.get("updated_utc")
    if not isinstance(updated, str):
        raise SystemExit("Match state is from an older build; start a new match")
    age = datetime.now(timezone.utc) - datetime.fromisoformat(updated).replace(tzinfo=timezone.utc)
    if age.total_seconds() > 10:
        raise SystemExit("Match state is stale; start or resume the game")

    if args.action == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    command_id = str(uuid.uuid4())
    command = {
        "command_id": command_id,
        "match_id": state["match_id"],
        "expected_event_id": state["event_id"],
        "player_socket": state["player_socket"],
        "action": args.action,
    }
    if args.target_socket is not None:
        command["target_socket"] = args.target_socket
    temporary = directory / f"control-command.{command_id}.tmp"
    temporary.write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")
    temporary.replace(directory / "control-command.json")

    results = directory / "control-results.jsonl"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if results.exists():
            for line in reversed(results.read_text(encoding="utf-8").splitlines()):
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("command_id") == command_id:
                    print(json.dumps(response, ensure_ascii=False))
                    return
        time.sleep(0.2)
    raise SystemExit(f"No response for command {command_id} within 10 seconds")


if __name__ == "__main__":
    main()
