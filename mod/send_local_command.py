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
    parser.add_argument("--player", type=int, choices=range(1, 5), default=1,
                        help="local seat to control (1-4; default: 1)")
    parser.add_argument("action", choices=("status", "use_item", "pickup_shotgun", "aim", "shoot", "jammer_target", "steal_item"))
    parser.add_argument("number", nargs="?", type=int, help="item slot (1-8) or player number (1-4)")
    parser.add_argument("item_slot", nargs="?", type=int, help="opponent item slot for steal_item (1-8)")
    args = parser.parse_args()
    if args.action in ("aim", "jammer_target", "steal_item") and args.number is None:
        parser.error(f"{args.action} requires a player number (1-4)")
    if args.action == "use_item" and args.number is None:
        parser.error("use_item requires an item slot (1-8)")
    if args.action in ("status", "pickup_shotgun") and args.number is not None:
        parser.error(f"{args.action} does not take a player number")
    if args.action in ("aim", "shoot", "jammer_target", "steal_item") and args.number is not None and args.number not in range(1, 5):
        parser.error("player number must be 1, 2, 3, or 4")
    if args.action == "use_item" and args.number not in range(1, 9):
        parser.error("item slot must be 1 through 8")
    if args.action == "steal_item" and args.item_slot not in range(1, 9):
        parser.error("steal_item requires an opponent item slot (1-8)")
    if args.action != "steal_item" and args.item_slot is not None:
        parser.error(f"{args.action} does not take a second number")

    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("APPDATA is not set")
    directory = Path(appdata) / "BuckshotSplitTest" / "modbucksot"
    state_path = directory / f"control-state-player-{args.player}.json"
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
    if state.get("player_number") != args.player:
        raise SystemExit("State belongs to a different local player")

    if args.action == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    target_socket = None
    if args.action in ("aim", "shoot", "jammer_target", "steal_item") and args.number is not None:
        target_name = f"PLAYER {args.number}"
        target_socket = next(
            (player["socket"] for player in state["players"] if player["name"] == target_name),
            None,
        )
        if target_socket is None:
            raise SystemExit(f"{target_name} is not in the current match")
    elif args.action == "shoot":
        target_socket = state.get("aimed_socket", -1)
        if target_socket not in range(4):
            raise SystemExit("No confirmed aim; run 'aim <player number>' first")
    if args.action == "shoot" and state.get("aimed_socket") != target_socket:
        raise SystemExit("Target differs from the last confirmed aim; aim again or run 'shoot' without a number")

    command_id = str(uuid.uuid4())
    command = {
        "command_id": command_id,
        "match_id": state["match_id"],
        "expected_event_id": state["event_id"],
        "player_socket": state["player_socket"],
        "player_number": args.player,
        "action": args.action,
    }
    if target_socket is not None:
        command["target_socket"] = target_socket
    if args.action == "use_item":
        command["item_slot"] = args.number
    if args.action == "steal_item":
        command["item_slot"] = args.item_slot
    temporary = directory / f"control-command-player-{args.player}.{command_id}.tmp"
    temporary.write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")
    temporary.replace(directory / f"control-command-player-{args.player}.json")

    results = directory / f"control-results-player-{args.player}.jsonl"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if results.exists():
            for line in reversed(results.read_text(encoding="utf-8").splitlines()):
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("command_id") == command_id:
                    if target_socket is not None:
                        player_name = next((p["name"] for p in state["players"] if p["socket"] == target_socket), "unknown")
                        print(f"Target: {player_name} (internal socket {target_socket})")
                    print(json.dumps(response, ensure_ascii=False))
                    return
        time.sleep(0.2)
    raise SystemExit(f"No response for command {command_id} within 10 seconds")


if __name__ == "__main__":
    main()
