# EverPort: Everlasting Summer for PortMaster

Plays the Steam release of [Everlasting Summer](https://store.steampowered.com/app/331470/) (Бесконечное лето, Soviet Games) on Linux handhelds through [PortMaster](https://portmaster.games/), including Steam Workshop mods. Built and tested on an Anbernic RG40XX H (640x480, 1 GB RAM, Knulli).

![Everlasting Summer](port/everlastingsummer/cover.jpg)

The game is not included. You add your own copy, which is free on Steam.

## Install

1. Install PortMaster on the handheld and open it once.
2. Download `everlastingsummer.zip` from [Releases](../../releases) and unzip it into your ports folder (Knulli: `/userdata/roms/ports/`, ROCKNIX: `/roms/ports/`).
3. Copy everything inside the Steam install's `game` folder, except `mods`, `cache` and `saves`, into `ports/everlastingsummer/game/`.
4. Start "Everlasting Summer" from Ports. PortMaster fetches the Ren'Py 8.3.4 runtime the first time.

Full player instructions, settings, controls and mod support: [port/everlastingsummer/README.md](port/everlastingsummer/README.md).

## Features

- Runs the Ren'Py 7.4 / Python 2 game unchanged on PortMaster's shared Ren'Py 8.3.4 runtime.
- GPU rendering (the runtime defaults to software), full-screen or letterboxed, text scaled for 3.5" screens.
- Both sticks move a mouse cursor the game draws itself; L1 / R1 page through scrolling lists.
- Loads only the translations you choose, so it fits in 1 GB of RAM.
- Steam Workshop mods: drop a mod folder in and it works, Ren'Py 7 code included; an on-device mod manager switches mods off or deletes them.
- Optional PC tools shrink the game and mods to the handheld's resolution.

## Repository layout

`port/` is exactly what goes into the release zip and onto the handheld.

| Path | What it is |
|--|--|
| `port/Everlasting Summer.sh` | Launcher: settings, language and mod setup, mounts the runtime, starts gptokeyb and Ren'Py |
| `port/Everlasting Summer - Mod manager.sh` | Starts the mod manager (`ES_APP=mods`) |
| `port/everlastingsummer/patches/zz_portmaster.rpy` | Compatibility and handheld layer, copied into `game/` on every start |
| `port/everlastingsummer/patches/fix_mods.py` | Fixes Ren'Py 7 syntax in mod scripts; the launcher runs it with the runtime's Python |
| `port/everlastingsummer/modmanager/script.rpy` | The mod manager, a small Ren'Py app on the same runtime |
| `port/everlastingsummer/everlastingsummer.gptk` | gptokeyb button mapping |
| `port/everlastingsummer/tools/` | `prepare_gamefiles.py` and `prepare_mods.py`, the optional PC tools |
| `port/everlastingsummer/port.json`, `gameinfo.xml`, `cover.jpg`, `screenshot.png` | PortMaster metadata |
| `port/everlastingsummer/game/`, `workshop/` | The player's game files and mods (ignored by git) |
| `scripts/build_release.py` | Builds `dist/everlastingsummer.zip` from `port/`, without game files |

Build the release zip:

```bash
python scripts/build_release.py
```

## How it works

### Running a Ren'Py 7 game on Ren'Py 8

PortMaster ships Ren'Py 8 runtimes only. Ren'Py 8.3.4 loads the game's Ren'Py 7 `.rpyc` files and rewrites most Python 2 syntax itself; `zz_portmaster.rpy` covers the rest:

- `im.Map` ramps built with `chr()` (bytes in Python 2) crashed the ending credits.
- The colour filters walked Ren'Py's image table with `dict.iteritems()`.
- Dicts made by game code return lists from `keys()` / `values()` / `items()` again, and `xrange`, `unichr`, `long`, `reduce` exist, for Python 2 code in mods.
- Developer mode is forced off (some mods ship with it on, and the runtime lacks Ren'Py's developer tools).
- `DejaVuSans.ttf`, which Ren'Py 7 bundled and mods name directly, falls back to the game's Calibri.
- Every patch block imports the builtins its functions use: those functions run with the store as their globals, and the game overwrites names there (its main menu does `hour, min, sec = t.split(":")`, which broke any later `min()`).

### The PortMaster runtime

- `renpy_8.3.4` ships with `config.gl_enable = False`, so it draws in software. The patch turns GL back on and the launcher selects `gles2`, which runs on the RG40XX H's Mali-G31.
- Its compiled GL code reads `config.mipmap`, which its Python side never defines; the patch defines it.
- Ren'Py's base folder is the read-only squashfs, so `RENPY_LOG_BASE` sends `log.txt` / `traceback.txt` to `logs/`.

### Handheld

- 16:9 on 4:3: `ES_ASPECT` sets `config.adjust_view_size` to stretch, letterbox or zoom.
- Text: 1080p text is about 7px tall at 640x360; Ren'Py's `font_size` preference scales it by `ES_TEXT_SCALE`.
- Cursor: the Mali framebuffer driver has no hardware cursor, so `config.mouse_displayable` draws the game's cursor.
- Lists: the settings, history and mod screens scroll only with a mouse wheel and their hidden rows can't take D-pad focus, so every wheel-scrolled viewport also gets page keys (L1 / R1).
- Memory: Ren'Py loads every language's dialogue at startup (38 of the 44 MB of compiled script). The launcher moves translations not in `ES_LANGUAGES` to `tl_parked/`. On the RG40XX H, Russian only takes 368 MB and 11 s to load; all eight take 699 MB and 54 s.
- The game asks for a 1000-step rollback and desktop cache sizes; the port uses Ren'Py's defaults and a smaller image cache.

### Shrunk assets (optional)

`prepare_gamefiles.py` rebuilds `archive.rpa` with every image downscaled 3x (437 MB to 45 MB) and writes `portmaster_shrink.txt`. The patch gives the listed images a fractional oversample, so they keep their 1920x1080-layout size on screen, and rounds Ren'Py's `im.Composite`, `im.Crop`, `im.Scale` and the game's own `VerticalCrop`, which assume whole-number oversample. It also re-encodes the opening video at 360p and can drop translations (`--languages`).

### Workshop mods

The Steam build patches Ren'Py's `main.py` to add every `steamapps/workshop/content/331470/<id>` folder to the search path, so each mod is an extra game root. The launcher does the same with Ren'Py's `RENPY_SEARCHPATH` for every folder in `workshop/` not listed in `workshop/disabled.txt`. Before Ren'Py starts, `fix_mods.py` removes the colon from `show x:` lines with no block under them (Ren'Py 7 accepted them, 8 doesn't) in new or changed `.rpy` files.

The mod manager runs on the same runtime with `ES_APP=mods`. It reads a mod's title from the `mods["label"] = "Title"` line in its scripts (or `.rpyc` source) and estimates RAM at about 9 MB per MB of compiled script. Its Play button leaves a flag; the launcher then restarts itself as the game, after restoring the environment PortMaster's own scripts check (`XDG_DATA_HOME`, `PM_FUNCS_VERSION`, `DEVICE_INFO_VERSION`).

`prepare_mods.py` shrinks mods like the game (each with its own manifest), re-encodes videos at 360p with their own codec, drops Windows-only files and looks titles up with Steam's public Workshop API.

## Testing

On PC with the Ren'Py 8.3.4 SDK: all compiled scripts load; every defined image loads, and the shrunk build's on-screen sizes match the originals within 2px across 2,592 surfaces; menus, dialogue, the opening video and PC saves work. 14 of 16 Workshop mods tried start and play their opening; "7 Дней Лета: Lost Alpha" needs more RAM than 1 GB and compares `None >= 1`, which Python 3 rejects.

On the RG40XX H (Knulli gladiator-ii): GL rendering, full screen, cursor on both sticks, list paging, drop-in mods from a raw Steam folder, the mod manager and its hand-off to the game.

Install paths compared on the RG40XX H, English kept:

| Game folder | First start | Later starts | RAM in play (peak) |
|--|--|--|--|
| Copied straight from Steam | 75 s | 42 s | about 590 MB (650 MB) |
| Built with `prepare_gamefiles.py` | | 39 s | about 455 MB with two small mods |

## License

The port's own code (launchers, patches, tools, mod manager) is MIT licensed, see [LICENSE](LICENSE). Everlasting Summer and its art belong to Soviet Games; mods belong to their authors. This project is not affiliated with Soviet Games.
