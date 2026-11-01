#!/bin/bash

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
launch_xdg_data_home="$XDG_DATA_HOME"

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
else
  controlfolder="/roms/ports/PortMaster"
fi

source $controlfolder/control.txt
[ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
get_controls

# Settings: edit here, or set them in the environment.

# Translated dialogue to load besides the original Russian: any of chinese english
# french german italian portuguese spanish turkish, or "all". Each one costs about 6 s
# of startup and 40 MB of RAM on a 1 GB handheld.
export ES_LANGUAGES="${ES_LANGUAGES:-english}"
# Screen shape: stretch (fills the screen, picture 33% taller), fit (black bars),
# zoom (fills the screen, sides cut off).
export ES_ASPECT="${ES_ASPECT:-stretch}"
# Text size multiplier: 1.0 is the PC size, about 7px tall on a 640x480 screen.
export ES_TEXT_SCALE="${ES_TEXT_SCALE:-1.5}"
# Mouse cursor size (1.5 = about 20px tall); 0 uses the hardware cursor.
export ES_CURSOR_SCALE="${ES_CURSOR_SCALE:-1.5}"
# gles2 renders on the GPU; sw is the runtime's own default, the software renderer.
export ES_RENDERER="${ES_RENDERER:-gles2}"

# Variables
GAMEDIR="/$directory/ports/everlastingsummer"
runtime="renpy_8.3.4"
renpydir="$GAMEDIR/renpy"
gamefiles="$GAMEDIR/game"
renpy_runtime="$controlfolder/libs/${runtime}.squashfs"
workshop="$GAMEDIR/workshop"

# ES_APP=mods (set by "Everlasting Summer - Mod manager.sh") runs the small mod
# manager in modmanager/ on the same runtime instead of the game.
[ "$ES_APP" = "mods" ] && gamefiles="$GAMEDIR/modmanager"

cd "$GAMEDIR"
> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1

if [ ! -f "$GAMEDIR/game/archive.rpa" ]; then
  pm_message "Game files missing: copy everything in Everlasting Summer's game folder (except mods, cache, saves) into ports/everlastingsummer/game. See everlastingsummer/README.md."
  sleep 5
  exit 1
fi

if [ ! -f "$renpy_runtime" ]; then
  # Check for runtime if not downloaded via PM
  if [ ! -f "$controlfolder/harbourmaster" ]; then
    pm_message "This port requires the latest PortMaster to run, please go to https://portmaster.games/ for more info."
    sleep 5
    exit 1
  fi

  $ESUDO $controlfolder/harbourmaster --quiet --no-check runtime_check "${runtime}.squashfs"
fi

mkdir -p "$workshop"

if [ "$ES_APP" = "mods" ]; then
  # The runtime ships no fonts; the manager borrows one of the game's.
  if [ ! -f "$gamefiles/font.ttf" ]; then
    for font in "$GAMEDIR/game/fonts/calibri.ttf" "$GAMEDIR/game/DejaVuSans.ttf" "$GAMEDIR"/game/fonts/*.ttf; do
      [ -f "$font" ] && cp -f "$font" "$gamefiles/font.ttf" && break
    done
  fi
  export ES_WORKSHOP="$workshop"
else
  # The game ships for Ren'Py 7.4 (Python 2); this file adapts it to the Ren'Py 8 runtime.
  cmp -s "$GAMEDIR/patches/zz_portmaster.rpy" "$gamefiles/zz_portmaster.rpy" || \
    cp -f "$GAMEDIR/patches/zz_portmaster.rpy" "$gamefiles/zz_portmaster.rpy"

  # Ren'Py loads every language's dialogue at startup. Dialogue for languages not in
  # ES_LANGUAGES moves to tl_parked/, and back once they're listed again.
  for dir in "$gamefiles"/tl/*/scenario "$GAMEDIR"/tl_parked/*/scenario; do
    [ -d "$dir" ] || continue
    lang="$(basename "$(dirname "$dir")")"
    case " $ES_LANGUAGES " in
      *" all "*|*" $lang "*) keep=1 ;;
      *) keep=0 ;;
    esac
    if [ $keep = 1 ] && [ "$dir" = "$GAMEDIR/tl_parked/$lang/scenario" ]; then
      mkdir -p "$gamefiles/tl/$lang" && mv "$dir" "$gamefiles/tl/$lang/"
    elif [ $keep = 0 ] && [ "$dir" = "$gamefiles/tl/$lang/scenario" ]; then
      mkdir -p "$GAMEDIR/tl_parked/$lang" && mv "$dir" "$GAMEDIR/tl_parked/$lang/"
    fi
  done

  # Workshop mods: every folder dropped into workshop/ (a copy of a Steam
  # steamapps/workshop/content/331470/<id> folder) becomes an extra game root, the way
  # the Steam build loads them, unless the mod manager listed it in
  # workshop/disabled.txt. ES_MODS overrides with an explicit list of folders.
  # (Mods made for game/mods/ on a PC go in game/mods/ here too and always load.)
  modroots=""
  moddirs=()
  add_mod() {
    [ -d "$workshop/$1" ] || return
    modroots="${modroots:+$modroots::}$workshop/$1"
    moddirs+=("$workshop/$1")
  }
  if [ -n "${ES_MODS+set}" ]; then
    for mod in $ES_MODS; do add_mod "$mod"; done
  else
    for dir in "$workshop"/*/; do
      mod="$(basename "$dir")"
      case "$mod" in .*|_*|"*") continue ;; esac
      [ -f "$workshop/disabled.txt" ] && tr -d '\r' < "$workshop/disabled.txt" | grep -qxF "$mod" && continue
      add_mod "$mod"
    done
  fi
  [ -n "$modroots" ] && export RENPY_SEARCHPATH="$modroots"
  [ -d "$gamefiles/mods" ] && moddirs+=("$gamefiles/mods")
fi

# Savedata setup: the game keeps saves in game/saves, Ren'Py 8 keeps save tokens in ~/.renpy
mkdir -p "$GAMEDIR/conf"
export XDG_DATA_HOME="$GAMEDIR/conf"
bind_directories ~/.renpy/ "$GAMEDIR/conf/"

# Mounting Ren'Py and gamefiles
$ESUDO mkdir -p "$renpydir"
$ESUDO umount "$renpydir/game" 2>/dev/null || true
$ESUDO umount "$renpydir" 2>/dev/null || true
$ESUDO mount "$renpy_runtime" "$renpydir"
sleep 2
$ESUDO mount --bind "$gamefiles" "$renpydir/game"

# Exports
export RENPY_RENDERER="$ES_RENDERER"
export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"
# Ren'Py's base folder is the read-only runtime, so send its log.txt / traceback.txt here.
mkdir -p "$GAMEDIR/logs"
export RENPY_LOG_BASE="$GAMEDIR/logs"
export PYTHONHOME="$renpydir"
export PYTHONPATH="$renpydir/lib/python3.9"

# Ren'Py parses mod scripts before the port's patch runs, so Ren'Py 7 syntax that 8
# rejects is fixed here, with the runtime's Python, in new or changed .rpy files.
[ ${#moddirs[@]} -gt 0 ] && "$renpydir/lib/py3-linux-aarch64/python" "$GAMEDIR/patches/fix_mods.py" "${moddirs[@]}"

# If using gl4es
if [ -f "${controlfolder}/libgl_${CFW_NAME}.txt" ]; then
  source "${controlfolder}/libgl_${CFW_NAME}.txt"
else
  source "${controlfolder}/libgl_default.txt"
fi

pm_platform_helper "$renpydir/lib/py3-linux-aarch64/startRENPY"
$GPTOKEYB "$renpydir/lib/py3-linux-aarch64/startRENPY" -c "$GAMEDIR/everlastingsummer.gptk" &
"$renpydir/startRENPY"

if [[ "$PM_CAN_MOUNT" != "N" ]]; then
  $ESUDO umount "$renpydir/game"
  $ESUDO umount "$renpydir"
fi

pm_finish

# The mod manager's "Play" leaves this flag: start the game with the new mod list.
if [ "$ES_APP" = "mods" ] && [ -f "$workshop/.play" ]; then
  rm -f "$workshop/.play"
  # Start clean: PortMaster finds its folder through XDG_DATA_HOME, and its funcs.txt and
  # device_info.txt skip loading when their *_VERSION markers are already exported.
  export XDG_DATA_HOME="$launch_xdg_data_home"
  unset RENPY_SEARCHPATH PM_FUNCS_VERSION DEVICE_INFO_VERSION
  ES_APP=game exec "$0"
fi
