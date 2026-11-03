"""Derive only shell counts justified by events visible to one player."""
from __future__ import annotations


def summarize_shells(events: list[dict]) -> dict:
    load_index = next((i for i in range(len(events) - 1, -1, -1)
                       if events[i].get("type") == "shotgun_loaded"), None)
    if load_index is None:
        return {"available": False, "reason": "No public shell load observed in this match"}
    loaded = events[load_index]
    live = loaded["data"]["live"]
    blank = loaded["data"]["blank"]
    total = live + blank
    possible_live = {live}
    current_shell = None
    for event in events[load_index + 1:]:
        kind = event.get("type")
        data = event.get("data") or {}
        if kind == "item_private_result" and data.get("item_id") == 2:
            if data.get("shell") in ("live", "blank"):
                current_shell = data["shell"]
        elif kind == "item_used" and data.get("item_id") == 9:
            next_possible = set()
            for count in possible_live:
                if current_shell in (None, "live") and count > 0:
                    next_possible.add(count - 1)
                if current_shell in (None, "blank") and count < total:
                    next_possible.add(count + 1)
            possible_live = next_possible
            if current_shell == "live":
                current_shell = "blank"
            elif current_shell == "blank":
                current_shell = "live"
        elif kind in ("shot_resolved", "shell_ejected") and data.get("shell") in ("live", "blank"):
            shell = data["shell"]
            possible_live = {count - (shell == "live") for count in possible_live
                             if (count > 0 if shell == "live" else count < total)}
            total -= 1
            current_shell = None
    if total < 0 or not possible_live:
        return {"available": False, "reason": "Shell events are inconsistent"}
    counts = sorted(possible_live)
    return {
        "available": True,
        "load_event_id": loaded["event_id"],
        "initial_live": live,
        "initial_blank": blank,
        "remaining_total": total,
        "possible_remaining_live": counts,
        "possible_remaining_blank": sorted({total - count for count in counts}),
        "live_probability_range": [round(counts[0] / total, 3), round(counts[-1] / total, 3)] if total else None,
        "known_current_shell_private": current_shell,
    }
