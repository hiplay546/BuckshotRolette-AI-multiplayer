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
git apply ..\..\mod\morerollers-keyboard-seats.patch
git apply ..\..\mod\morerollers-turn-telemetry.patch
node tools/build.js "C:\Users\Daniil\Desktop\modbucksot\work\game-v2.2.0\Buckshot Roulette.exe"
```

Copy `mod/loader.gd` and `mod/splitscreen.pck` from the MoreRollers checkout into `work/splitscreen-test/splitscreen_mod/`. The game copy needs `override.cfg` with the `SplitMod` autoload as described in MoreRollers' README.

## Verified

A headless smoke test loaded the mod, filled the lobby through its F4 handler with devices `[-1, -2, -3, -4]`, started a match, and observed `split_session` with four views and `started=true` in `%APPDATA%/BuckshotSplitTest/logs/godot.log`.

A full four-player match and keyboard switching during graphical play were confirmed by the user. The host-only telemetry patch still requires a manual turn transition to verify its JSONL output.

## Passive turn log

The current test build also has a host-only `turn_changed` logger. After a real turn transition, check `%APPDATA%/BuckshotSplitTest/modbucksot/events.jsonl`. Each row has `match_id`, `event_id`, UTC time, old and new socket, and round index. The four local views must produce one row per host-confirmed transition.

The headless four-seat test did not progress through a manual turn, so no event row has been verified yet. Item, shotgun, health, and elimination telemetry remain to be added after the turn log is checked in a manual match.
