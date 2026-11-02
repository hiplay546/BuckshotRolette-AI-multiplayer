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
node tools/build.js "C:\Users\Daniil\Desktop\modbucksot\work\game-v2.2.0\Buckshot Roulette.exe"
```

Copy `mod/loader.gd` and `mod/splitscreen.pck` from the MoreRollers checkout into `work/splitscreen-test/splitscreen_mod/`. The game copy needs `override.cfg` with the `SplitMod` autoload as described in MoreRollers' README.

## Verified

A headless smoke test loaded the mod, filled the lobby through its F4 handler with devices `[-1, -2, -3, -4]`, started a match, and observed `split_session` with four views and `started=true` in `%APPDATA%/BuckshotSplitTest/logs/godot.log`.

A full four-player match, keyboard switching during graphical play, and interaction with the separate telemetry patch still require manual verification.
