# Four local seats without controllers

This is an experimental patch for [MoreRollers](https://github.com/MashiroW/MoreRollers), tested against upstream commit `63d08453bb7f2659389b6462feb5fc5dbab3920f` and Buckshot Roulette `v2.2.0.6`.

The test game is `work/splitscreen-test/Buckshot Roulette.exe`. It has its own user data directory (`%APPDATA%/BuckshotSplitTest`) and does not modify the Steam installation.

## Controls

1. Run the test EXE and select **LOCAL SPLITSCREEN**.
2. Press **F4** to fill all four seats, without controllers.
3. Select **START** and press Enter.
4. During a match, press **F1**, **F2**, **F3**, or **F4** to give the keyboard and mouse to that seat. The game logs the selected player as `[splitscreen] keyboard controls player N`.

The four seats are local copies of the game's multiplayer scene. Switching input is a manual testing aid; API agents and action validation have not been connected.

## Rebuild

Clone the upstream commit into `tools/MoreRollers`, then from that directory:

```powershell
git apply ..\..\mod\morerollers-local-telemetry.patch
node tools/build.js "C:\Users\Daniil\Desktop\modbucksot\work\game-v2.2.0\Buckshot Roulette.exe"
```

Copy `mod/loader.gd` and `mod/splitscreen.pck` from the MoreRollers checkout into `work/splitscreen-test/splitscreen_mod/`. The game copy needs `override.cfg` with the `SplitMod` autoload as described in MoreRollers' README.

## Verified

A headless smoke test loaded the mod, filled the lobby through its F4 handler with devices `[-1, -2, -3, -4]`, started a match, and observed `split_session` with four views and `started=true` in `%APPDATA%/BuckshotSplitTest/logs/godot.log`.

A full four-player match and keyboard switching during graphical play were confirmed by the user. Host-only turn telemetry was verified during that match.

## Passive event log

The test build has a host-only JSONL logger at `%APPDATA%/BuckshotSplitTest/modbucksot/events.jsonl`. It records `round_started`, `turn_changed`, `item_used`, `shotgun_picked_up`, `aim_changed`, `shot_target_confirmed`, `shot_resolved`, `health_changed`, `player_spectating`, `player_revived`, and `game_concluded`. Each row has `match_id`, `event_id`, and UTC time. `aim_changed` is the observed look direction while holding the shotgun; `shot_target_confirmed` is the target accepted with the shot packet, not a separate pre-shot commitment. A zero health value is recorded as such, without assuming permanent elimination across rounds.

The magnifying glass also creates `item_private_result` with `visibility: private` and `recipient_socket` set to its owner. The orchestrator must filter that row from every other player's observation. The JSONL file itself is a viewer/development log and is not a player-facing feed.

The user verified a four-player manual match, and the resulting JSONL had unique host-only `turn_changed`, `item_used`, and `shot_resolved` rows with sequential event IDs. A four-view headless smoke test also wrote one `round_started` row without script errors. The other newly added event types still need a manual-match check against the screen. The manual command bridge below separates aim and shoot for one seat; the game's turn timer still runs, so the negotiation flow needs a verified pause mechanism.

## One-seat manual command bridge

The current build reads one JSON command at a time from `%APPDATA%/BuckshotSplitTest/modbucksot/control-command.json`. It writes current state to `control-state.json` and responses to `control-results.jsonl`. `mod/send_local_command.py` writes commands atomically and supplies the current match ID, event ID, and player socket. It controls only the first joined player's local copy; that player's socket can change between matches.

From the project root, while that player has the turn:

```powershell
py mod/send_local_command.py status
py mod/send_local_command.py pickup_shotgun
py mod/send_local_command.py aim 2
py mod/send_local_command.py shoot 2
```

`status` shows the current player-to-socket mapping. The target is a socket number from 0 to 3. `shoot` requires a prior `aim` for the same target. The bridge checks the game phase, turn, health, target, match ID, and event ID before calling the game's request methods. Reused command IDs are ignored. A `request_sent` response means the command was submitted; confirm the effect in `events.jsonl` and on screen. No LLM is connected.

A four-view headless smoke test loaded the bridge and produced `control-state.json`. An `aim` request during item distribution was rejected as `shotgun_not_ready`, with no shot. Pickup, aim, and shoot still require a manual in-game command test.
