"""Ask one OpenRouter model for one legal local Buckshot action."""
from __future__ import annotations

import argparse
import json
import os
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
    if state.get("can_aim"):
        result.extend(
            {"action": "aim", "target_socket": socket, "label": f"Aim at {p['name']}"}
            for socket, p in players.items() if p["health"] > 0
        )
    aimed = state.get("aimed_socket", -1)
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
                "A blank shot at yourself can retain the turn; a live shot deals damage. "
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--preview", action="store_true", help="show observation and choices without an API request")
    args = parser.parse_args()

    appdata = os.environ.get("APPDATA")
    if not appdata:
        parser.error("APPDATA is not set")
    directory = Path(appdata) / "BuckshotSplitTest" / "modbucksot"
    try:
        state = json.loads((directory / f"control-state-player-{args.player}.json").read_text(encoding="utf-8"))
        updated = datetime.fromisoformat(state["updated_utc"]).replace(tzinfo=timezone.utc)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"No valid live state for player {args.player}: {exc}") from exc
    if (datetime.now(timezone.utc) - updated).total_seconds() > 10:
        raise SystemExit("Match state is stale; start or resume the game")
    if state.get("player_number") != args.player:
        raise SystemExit("State belongs to a different local player")
    options = candidates(state)
    if not options:
        raise SystemExit("No action available for this player now")
    observation = {
        "seat": args.player,
        "state": state,
        "recent_events": recent_events(directory / "events.jsonl", state["match_id"], state["player_socket"]),
        "choices": [{"index": i, "label": option["label"]} for i, option in enumerate(options)],
    }
    if args.preview:
        print(json.dumps(observation, ensure_ascii=False, indent=2))
        return
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("Set OPENROUTER_API_KEY in this PowerShell session; do not paste it into chat")
    decision, usage = ask_model(key, args.model, observation)
    index = decision.get("choice") if isinstance(decision, dict) else None
    if type(index) is not int or index not in range(len(options)):
        raise SystemExit(f"Model selected an invalid choice: {decision!r}")
    selected = options[index]
    print(json.dumps({"model": args.model, "choice": selected["label"],
                      "reason": decision.get("reason", ""), "usage": usage}, ensure_ascii=False))
    response = submit_command(directory, state, args.player, selected["action"],
                              selected.get("target_socket"), selected.get("item_slot"))
    print(json.dumps(response, ensure_ascii=False))


if __name__ == "__main__":
    main()
