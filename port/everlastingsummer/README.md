# Everlasting Summer for PortMaster

[Everlasting Summer](https://store.steampowered.com/app/331470/) (Бесконечное лето) on Linux handhelds through PortMaster. The game isn't included: you add your own copy (it's free on Steam). Built and tested on an Anbernic RG40XX H (640x480, 1 GB RAM) with Knulli.

The Steam release runs on Ren'Py 7.4 (Python 2). This port runs it on PortMaster's Ren'Py 8.3.4 runtime with a compatibility layer, GPU rendering, a mouse cursor for the sticks, readable text on small screens and Steam Workshop mod support.

## Install

1. Install [PortMaster](https://portmaster.games/) on the handheld and open it once.
2. Install the port: copy `everlastingsummer.zip`, still zipped, into PortMaster's `autoinstall` folder (Knulli: `/userdata/system/.local/share/PortMaster/autoinstall/`) and open PortMaster; it installs the port and adds its cover to the Ports list. (Unzipping it into your ports folder by hand works too, but then Ports shows no cover.)
3. Add the game: on your PC, open Steam, right-click Everlasting Summer > Manage > Browse local files, open its `game` folder and copy what's in it into `ports/everlastingsummer/game/` on the handheld. Leave out `mods` (a 590 MB Windows modding tool; the port would delete it anyway), `cache` and `saves`.
4. Start "Everlasting Summer" from Ports. The first time, PortMaster downloads the Ren'Py 8.3.4 runtime (Wi-Fi needed once), then the port prepares the game for your screen: it shrinks the 1080p images to the screen's size (930 MB becomes about 470 MB) and re-encodes the opening video. That takes about 8 minutes on an RG40XX H, once, with the progress on screen. Later starts take about 40 seconds.

### Optional: prepare the game on a PC

`everlastingsummer/tools/prepare_gamefiles.py` does the same preparation on a PC, faster, and shrinks the images further (to 360p, about 440 MB in all). Needs Python 3, Pillow (`pip install pillow`) and ffmpeg.

```
python everlastingsummer/tools/prepare_gamefiles.py "C:/Program Files (x86)/Steam/steamapps/common/Everlasting Summer"
```

Then copy the `everlastingsummer/game/` folder it fills onto the handheld; the handheld skips its own preparation. `--languages english` keeps only the dialogue you read (see below).

## Settings

At the top of `Everlasting Summer.sh` (any text editor that keeps Linux line endings):

| Setting | Default | What it does |
|--|--|--|
| `ES_LANGUAGES` | `english` | Translations to load besides the original Russian: `chinese english french german italian portuguese spanish turkish`, several separated by spaces, or `all`. Each one costs about 6 s of startup and 40 MB of RAM; the rest is moved to `tl_parked/` and back automatically. Pick the language itself in the game's settings. |
| `ES_ASPECT` | `stretch` | `stretch` fills a 4:3 screen (picture 33% taller), `fit` keeps the proportions with black bars, `zoom` fills the screen by cutting the sides (cuts the start of long lines). |
| `ES_TEXT_SCALE` | `1.5` | Text size. `1.0` is the PC size, too small on a 3.5" screen. |
| `ES_CURSOR_SCALE` | `1.5` | Mouse cursor size. `0` asks the display driver for a cursor (most handhelds don't draw one). |
| `ES_RENDERER` | `gles2` | `sw` for software rendering if a device shows GL problems. |
| `ES_SHRINK` | `auto` | How much the first start shrinks the images: `auto` fits the screen height (2.25 on a 480-line screen), `1` keeps them full size. Only used by the first start; to redo it, copy the game files again. |

## Controls

| Button | Action |
|--|--|
| A | Advance / select |
| B, Start, Select | Game menu / back |
| X | Hide text box |
| Y | Toggle skip |
| L1 / R1 | Rollback / roll forward; in scrolling lists (settings, history, mod list) page up / down |
| R2 (hold) | Skip |
| D-pad | Move between choices |
| Left or right stick | Mouse cursor (camp map, card game) |
| L2 or L3 | Mouse click |
| R3 | Right click |

## Mods

- **Add:** copy a Steam Workshop mod folder as is (`steamapps/workshop/content/331470/<number>` on the PC) into `ports/everlastingsummer/workshop/`. Copy the numbered folder itself. It loads on the next start and appears in the game's mod list. Mods made for the PC's `game/mods/` folder go in `ports/everlastingsummer/game/mods/`.
- **Switch off or delete:** start "Everlasting Summer - Mod manager" from Ports. A ticks / unticks a mod, Del deletes it (asks first), Play saves and starts the game, B leaves without saving.
- **Memory:** every mod that's on is loaded at startup. The manager shows an estimate; on a 1 GB handheld keep it under about 850 MB by switching off big mods you aren't playing. "7 Дней Лета: Lost Alpha" doesn't fit.
- **Optional:** `everlastingsummer/tools/prepare_mods.py` on a PC shrinks mods like the game, so they load faster and use less RAM.

## Saves

In `everlastingsummer/game/saves`. Saves from the PC version can be copied there and load. A save made in a mod only loads while that mod is on.

## Troubleshooting

- The launcher writes `everlastingsummer/log.txt`; Ren'Py writes `everlastingsummer/logs/log.txt`, and `logs/traceback.txt` if the game crashes.
- Won't start or quits during loading: probably out of memory. Load fewer languages (`ES_LANGUAGES`) or switch off mods.
- "Game files missing": `ports/everlastingsummer/game/` must contain `archive.rpa` directly, not inside another `game` folder.
- "Not enough free space to shrink the images": preparing the game needs about 650 MB free on the SD card for a moment. The game still plays, with full-size images.
- No cover in Ports: the port was unzipped by hand. Install the zip through PortMaster's `autoinstall` folder (step 2); it keeps your game files.

## Thanks

Soviet Games for Everlasting Summer, Tom "PyTom" Rothamel for Ren'Py, the PortMaster team, and the authors of the Workshop mods.
