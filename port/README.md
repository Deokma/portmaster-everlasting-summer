## Notes

Everlasting Summer is free on [Steam](https://store.steampowered.com/app/331470/). The Steam build targets Ren'Py 7.4.11 (Python 2); this port runs it on PortMaster's Ren'Py 8.3.4 runtime with a small compatibility layer (`patches/zz_portmaster.rpy`).

## Installation

Recommended (needs a PC with Python 3 + Pillow, and ffmpeg for the video):

```
python tools/prepare_gamefiles.py "<Steam>/steamapps/common/Everlasting Summer"
```

This fills `everlastingsummer/game/` with the game files, images shrunk 3x to the handheld's native 640x360 and the opening video re-encoded at 360p (about 450 MB instead of 1.1 GB, and far less RAM). Then copy `Everlasting Summer.sh` and `everlastingsummer/` to your ports folder.

Without the tool: copy everything inside the install's `game/` folder except `mods/`, `cache/` and `saves/` into `ports/everlastingsummer/game/`. It runs, but full 1080p assets are slow on 1 GB devices.

## Controls

| Button | Action |
|--|--|
| A | Advance / select |
| B, Start, Select | Game menu / back |
| X | Hide text box |
| Y | Toggle skip |
| L1 / R1 | Rollback / roll forward |
| R2 (hold) | Skip |
| D-pad, right stick | Move between choices |
| Left stick | Mouse cursor (camp map, card game) |
| L2 or L3 | Mouse click |
| R3 | Right click |

## Thanks

Soviet Games for the game, Tom "PyTom" Rothamel for Ren'Py, and the PortMaster team.
