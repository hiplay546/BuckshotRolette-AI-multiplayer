"""Show one player's thoughts, table speech, and actions in its own console."""
from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path


def render(record: dict, player: int) -> bool:
    kind = record.get("kind")
    if kind == "model_response" and record.get("seat") == player:
        print(f"\n[{record.get('phase', '?')}]", flush=True)
        print(f"МЫСЛЬ: {record.get('private_thought') or '—'}", flush=True)
        print(f"МАНЕРА: {record.get('delivery_style') or '—'}", flush=True)
        print(f"РЕПЛИКА: {record.get('public_speech') or '— (молчит)'}", flush=True)
        print(f"РЕШЕНИЕ: {record.get('action') or '—'}", flush=True)
    elif kind == "command_result" and record.get("seat") == player:
        action = record.get("action") or {}
        response = record.get("response") or {}
        print(f"КОМАНДА: {action.get('label', action.get('action', '?'))} | {response.get('status', '?')}", flush=True)
    elif kind == "shot_result" and record.get("seat") == player:
        result = (record.get("result") or {}).get("data") or {}
        print(f"ВЫСТРЕЛ: {result.get('shell', '?')} | урон {result.get('damage', '?')}", flush=True)
    elif kind == "repeated_speech_suppressed" and record.get("seat") == player:
        print("ПОВТОРНАЯ РЕПЛИКА СКРЫТА", flush=True)
    elif kind in ("show_finished", "technical_pause"):
        print(f"\nПРОГОН ЗАВЕРШЁН: {record.get('reason') or kind}", flush=True)
        return True
    return False


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", type=int, required=True, choices=range(1, 5))
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--offset", type=int, required=True)
    args = parser.parse_args()
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(f"Buckshot | PLAYER {args.player}")
    print(f"PLAYER {args.player} | мысли, реплики, действия\nОжидание прогона...", flush=True)
    while not args.log.exists():
        time.sleep(0.2)
    with args.log.open(encoding="utf-8") as file:
        file.seek(args.offset)
        while True:
            line = file.readline()
            if not line:
                time.sleep(0.2)
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if render(record, args.player):
                break
    try:
        input("\nНажми Enter, чтобы закрыть это окно...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
