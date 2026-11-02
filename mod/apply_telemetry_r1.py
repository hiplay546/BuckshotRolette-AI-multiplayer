"""Applies the passive Modbucksot turn-change telemetry to Buckshot Roulette v2.2.0."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

EXPECTED_SHA256 = "6B65191E5D750ABE4D45EE150B817273E658A6401F0C550F7AF1527486089A04"
FUNCTION_MARKER = "func PassTurn(to_socket : int):\n"
TURN_MARKER = "\tvar previous_socket = game_state.MAIN_active_current_turn_socket\n"
HELPER = '''func _telemetry_write(event_type : String, payload : Dictionary):
\tvar telemetry_directory = ProjectSettings.globalize_path("user://modbucksot")
\tDirAccess.make_dir_recursive_absolute(telemetry_directory)
\tvar telemetry_path = telemetry_directory.path_join("events.jsonl")
\tvar telemetry_mode = FileAccess.READ_WRITE if FileAccess.file_exists(telemetry_path) else FileAccess.WRITE
\tvar telemetry_file = FileAccess.open(telemetry_path, telemetry_mode)
\tif telemetry_file == null:
\t\tpush_warning("Modbucksot telemetry: failed to open events.jsonl")
\t\treturn
\ttelemetry_file.seek_end()
\ttelemetry_file.store_line(JSON.stringify({
\t\t"schema_version": 1,
\t\t"timestamp_utc": Time.get_datetime_string_from_system(true, true),
\t\t"type": event_type,
\t\t"visibility": "public",
\t\t"data": payload,
\t}))
\ttelemetry_file.close()

'''
TURN_EVENT = '\t_telemetry_write("turn_changed", {"previous_socket": previous_socket, "active_socket": to_socket, "round_index": game_state.MAIN_active_round_index})\n'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path, help="Recovered MP_RoundManager.gd")
    args = parser.parse_args()
    path = args.script
    before_hash = sha256(path)
    if before_hash != EXPECTED_SHA256:
        raise SystemExit(f"Unexpected source SHA-256: {before_hash}")
    text = path.read_text(encoding="utf-8")
    if FUNCTION_MARKER not in text or TURN_MARKER not in text:
        raise SystemExit("Expected MP_RoundManager markers were not found")
    text = text.replace(FUNCTION_MARKER, HELPER + FUNCTION_MARKER, 1)
    text = text.replace(TURN_MARKER, TURN_MARKER + TURN_EVENT, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Patched {path}")
    print(f"SHA-256: {sha256(path)}")


if __name__ == "__main__":
    main()
