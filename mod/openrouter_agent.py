"""Ask one OpenRouter model for one legal local Buckshot action."""
from __future__ import annotations

import argparse
import json
import os
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from project_events import visible_to
from send_local_command import submit_command

DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
API_URL = "https://openrouter.ai/api/v1/chat/completions"


def candidates(state: dict) -> list[dict]:
    players = {p["socket"]: p for p in state["players"]}
    me = state["player_socket"]
    choice = state.get("secondary_choice")
    if choice == "jammer_target":
        return [
            {"action": "jammer_target", "target_socket": socket, "label": f"Jam {p['name']}"}
            for socket, p in players.items()
            if socket != me and p["health"] > 0 and not p.get("is_jammed", False)
        ]
    if choice == "steal_item":
        return [
            {"action": "steal_item", "target_socket": item["socket"], "item_slot": item["slot"],
             "label": f"Steal {item['name']} from {players[item['socket']]['name']} slot {item['slot']}"}
            for item in state.get("stealable_items", [])
            if item["usable"] and item["socket"] in players
        ]
    result = []
    if state.get("can_use_item"):
        result.extend(
            {"action": "use_item", "item_slot": item["slot"],
             "label": f"Use {item['name']} in own slot {item['slot']}"}
            for item in state.get("items", []) if item["usable"]
        )
    if state.get("can_pickup"):
        result.append({"action": "pickup_shotgun", "label": "Pick up shotgun"})
    aimed = state.get("aimed_socket", -1)
    if state.get("can_aim"):
        result.extend(
            {"action": "aim", "target_socket": socket, "label": f"Aim at {p['name']}"}
            for socket, p in players.items() if p["health"] > 0 and socket != aimed
        )
    if state.get("can_shoot") and aimed in players and players[aimed]["health"] > 0:
        result.append({"action": "shoot", "target_socket": aimed,
                       "label": f"Shoot at {players[aimed]['name']}"})
    return result


def recent_events(path: Path, match_id: str, socket: int, limit: int = 20) -> list[dict]:
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as log:
        for line in log:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("match_id") == match_id and visible_to(event, socket):
                events.append(event)
    return events[-limit:]


def parse_decision(reply: dict) -> dict:
    try:
        choice = reply["choices"][0]
        content = choice["message"].get("content")
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("response has no chat choice") from exc
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        usage = reply.get("usage") or {}
        reason_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        raise ValueError(
            f"empty model content (finish_reason={choice.get('finish_reason')}, "
            f"completion_tokens={usage.get('completion_tokens')}, reasoning_tokens={reason_tokens})"
        )
    try:
        decision = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model content is not JSON: {exc}") from exc
    if not isinstance(decision, dict):
        raise ValueError("model decision is not a JSON object")
    return decision


def ask_model(key: str, model: str, observation: dict) -> tuple[dict, dict]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": (
                "You are one player in a real four-player Buckshot Roulette match. "
                "Choose exactly one action from the numbered candidates. "
                "A blank shot at yourself retains your turn; a blank shot at another player passes it. "
                "A live shot deals damage. "
                "Items may reveal private information, change the shell, or affect a player. "
                "Never invent an action. Reply only as JSON: {\"choice\": integer, \"reason\": short string}."
            )},
            {"role": "user", "content": json.dumps(observation, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "reasoning": {"enabled": False},
        "max_completion_tokens": 320,
        "temperature": 0.5,
    }
    request = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            reply = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        raise SystemExit(f"OpenRouter HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"OpenRouter request failed: {exc}") from exc
    try:
        decision = parse_decision(reply)
    except ValueError as exc:
        raise SystemExit(f"OpenRouter returned no usable JSON decision: {exc}") from exc
    return decision, reply.get("usage", {})


def read_state(directory: Path, player_number: int) -> dict:
    try:
        state = json.loads((directory / f"control-state-player-{player_number}.json").read_text(encoding="utf-8"))
        updated = datetime.fromisoformat(state["updated_utc"]).replace(tzinfo=timezone.utc)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"No valid live state for player {player_number}: {exc}") from exc
    if (datetime.now(timezone.utc) - updated).total_seconds() > 10:
        raise ValueError("Match state is stale; start or resume the game")
    if state.get("player_number") != player_number:
        raise ValueError("State belongs to a different local player")
    return state


def action_settled(before: dict, after: dict, selected: dict) -> bool:
    action = selected["action"]
    if action == "pickup_shotgun":
        return after.get("holding_shotgun") and after.get("can_aim")
    if action == "aim":
        return after.get("can_shoot") and after.get("aimed_socket") == selected["target_socket"]
    if action == "shoot":
        return (after.get("event_id", 0) > before["event_id"]
                and not after.get("holding_shotgun")
                and (after.get("can_pickup") or after.get("can_use_item")))
    if action == "jammer_target":
        return after.get("secondary_choice") != "jammer_target" and (
            after.get("can_use_item") or after.get("can_pickup")
        )
    return after.get("event_id", 0) > before["event_id"] and (
        after.get("secondary_choice") or after.get("can_use_item") or after.get("can_pickup")
    )


def wait_for_next_state(directory: Path, player_number: int, before: dict, selected: dict) -> tuple[dict | None, str]:
    deadline = time.monotonic() + 90
    next_notice = time.monotonic() + 10
    while time.monotonic() < deadline:
        time.sleep(0.25)
        if time.monotonic() >= next_notice:
            print("Waiting for the game to finish this action...", flush=True)
            next_notice += 10
        try:
            after = read_state(directory, player_number)
        except ValueError:
            continue
        if after.get("match_id") != before["match_id"] or after.get("player_socket") != before["player_socket"]:
            return None, "match_or_player_changed"
        if after.get("active_socket") != before["player_socket"]:
            return None, "turn_ended"
        if action_settled(before, after, selected):
            return after, "action_settled"
    return None, "action_not_confirmed_within_90_seconds"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--preview", action="store_true", help="show observation and choices without an API request")
    parser.add_argument("--steps", type=int, default=1, help="maximum model actions in this turn (default: 1)")
    parser.add_argument("--max-cost", type=float, default=0.01, help="stop after this reported USD cost (default: 0.01)")
    args = parser.parse_args()
    if args.steps < 1 or args.steps > 20:
        parser.error("--steps must be 1 through 20")
    if not math.isfinite(args.max_cost) or args.max_cost <= 0:
        parser.error("--max-cost must be positive and finite")

    appdata = os.environ.get("APPDATA")
    if not appdata:
        parser.error("APPDATA is not set")
    directory = Path(appdata) / "BuckshotSplitTest" / "modbucksot"
    try:
        state = read_state(directory, args.player)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    key = os.environ.get("OPENROUTER_API_KEY")
    if not args.preview and not key:
        raise SystemExit("Set OPENROUTER_API_KEY in this PowerShell session; do not paste it into chat")
    total_cost = 0.0
    completed = 0
    stop_reason = "step_limit"
    for step in range(1, args.steps + 1):
        if state.get("active_socket") != state.get("player_socket"):
            stop_reason = "turn_ended"
            break
        options = candidates(state)
        if not options:
            stop_reason = "no_action_available"
            break
        observation = {
            "seat": args.player,
            "state": state,
            "recent_events": recent_events(directory / "events.jsonl", state["match_id"], state["player_socket"]),
            "choices": [{"index": i, "label": option["label"]} for i, option in enumerate(options)],
        }
        if args.preview:
            print(json.dumps(observation, ensure_ascii=False, indent=2))
            return
        if total_cost >= args.max_cost:
            stop_reason = "cost_limit"
            break
        decision, usage = ask_model(key, args.model, observation)
        index = decision.get("choice") if isinstance(decision, dict) else None
        if type(index) is not int or index not in range(len(options)):
            raise SystemExit(f"Model selected an invalid choice: {decision!r}")
        selected = options[index]
        print(json.dumps({"step": step, "model": args.model, "choice": selected["label"],
                          "reason": decision.get("reason", ""), "usage": usage}, ensure_ascii=False), flush=True)
        response = submit_command(directory, state, args.player, selected["action"],
                                  selected.get("target_socket"), selected.get("item_slot"))
        print(json.dumps(response, ensure_ascii=False), flush=True)
        if not response.get("accepted"):
            stop_reason = response.get("status", "command_rejected")
            break
        completed += 1
        cost = usage.get("cost")
        if not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
            stop_reason = "cost_unknown"
            break
        total_cost += cost
        if step == args.steps:
            stop_reason = "step_limit"
            break
        next_state, stop_reason = wait_for_next_state(directory, args.player, state, selected)
        if next_state is None:
            break
        state = next_state
    print(json.dumps({"completed_actions": completed, "reported_cost_usd": round(total_cost, 8),
                      "stopped": stop_reason}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.", file=sys.stderr)
        raise SystemExit(130)
