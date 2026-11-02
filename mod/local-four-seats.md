# Four local seats without controllers

This is an experimental patch for [MoreRollers](https://github.com/MashiroW/MoreRollers), tested against upstream commit `63d08453bb7f2659389b6462feb5fc5dbab3920f` and Buckshot Roulette `v2.2.0.6`.

The test game is `work/splitscreen-test/Buckshot Roulette.exe`. It has its own user data directory (`%APPDATA%/BuckshotSplitTest`) and does not modify the Steam installation.

## Controls

1. Run the test EXE and select **LOCAL SPLITSCREEN**.
2. Press **F4** to fill all four seats, without controllers.
3. Select **START** and press Enter.
4. During a match, press **F1**, **F2**, **F3**, or **F4** to give the keyboard and mouse to that seat. The game logs the selected player as `[splitscreen] keyboard controls player N`.

The four seats are local copies of the game's multiplayer scene. Switching input is a manual testing aid; AI agents have not been connected.

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

The test build has a host-only JSONL logger at `%APPDATA%/BuckshotSplitTest/modbucksot/events.jsonl`. It records `round_started`, `turn_changed`, `item_used`, `shotgun_picked_up`, `aim_changed`, `shot_target_confirmed`, `shot_resolved`, `health_changed`, `player_spectating`, `player_recovered`, and `game_concluded`. Each row has `match_id`, `event_id`, and UTC time. `aim_changed` is the observed look direction while holding the shotgun; `shot_target_confirmed` is the target accepted with the shot packet, not a separate pre-shot commitment. A zero health value is recorded as such, without assuming permanent elimination across rounds.

The magnifying glass also creates `item_private_result` with `visibility: private` and `recipient_socket` set to its owner. `mod/project_events.py` produces a player's event stream and defaults to hiding records with unknown visibility. For example, `py mod/project_events.py --socket 3 --match-id <match_id>` uses the internal socket from `status`. The JSONL file itself is a viewer/development log and is not a player-facing feed.

The user verified a four-player manual match, and the resulting JSONL had unique host-only `turn_changed`, `item_used`, and `shot_resolved` rows with sequential event IDs. A four-view headless smoke test also wrote one `round_started` row without script errors. The other newly added event types still need a manual-match check against the screen. In game version 2.2.0.6, `GlobalVariables.timeouts_enabled` defaults to `false` and has no assignment in extracted scripts; `status` now reports its live value. A future build that enables timeouts will need a separate pause mechanism.

## Four-seat manual command bridge

The current build uses separate files for each local seat: `control-state-player-N.json`, `control-command-player-N.json`, and `control-results-player-N.jsonl` in `%APPDATA%/BuckshotSplitTest/modbucksot/`, where N is 1–4. `mod/send_local_command.py` writes commands atomically and supplies the current match ID, event ID, local player number, and dynamic socket. `--player N` selects a local seat; without it, the CLI selects PLAYER 1. Each seat receives actions through its own game scene and the game's normal request path.

From the project root, while that player has the turn:

```powershell
py mod/send_local_command.py status
py mod/send_local_command.py --player 2 status
py mod/send_local_command.py use_item 1
py mod/send_local_command.py jammer_target 2
py mod/send_local_command.py steal_item 2 3
py mod/send_local_command.py pickup_shotgun
py mod/send_local_command.py aim 2
py mod/send_local_command.py shoot
```

`status` shows that seat's player-to-socket mapping, item slots, `secondary_choice`, `stealable_items`, and `timeouts_enabled`. `use_item 1` applies the item in slot 1. If it is a jammer, wait for `secondary_choice: jammer_target`, then run `jammer_target <player number>`. If it is adrenaline, wait for `secondary_choice: steal_item`, inspect `stealable_items`, then run `steal_item <player number> <opponent item slot>`. Use one item command at a time. After `item_used`, wait until `status` shows `can_use_item: true` or `can_pickup: true` before deciding again; this lets the animation and permission change finish. Numbers in `aim`, optional `shoot`, `jammer_target`, and `steal_item` mean the visible player number, 1 to 4. `shoot` without a number uses the last game-confirmed aim. The bridge checks the game phase, turn, health, target, match ID, event ID, and local seat before calling the game's request methods. Reused command IDs are ignored. A `request_sent` response means the command was submitted; confirm the effect in `events.jsonl` and on screen. No LLM is connected.

A four-view headless smoke test loaded the bridge. The user manually verified pickup, aim, shoot, one-step items, adrenaline, stolen item use, and jammer selection for the first seat. The other seats still need a manual in-game command test.
