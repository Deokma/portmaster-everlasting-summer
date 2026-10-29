#!/bin/bash

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

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

# Variables
GAMEDIR="/$directory/ports/everlastingsummer"
runtime="renpy_8.3.4"
renpydir="$GAMEDIR/renpy"
gamefiles="$GAMEDIR/game"
renpy_runtime="$controlfolder/libs/${runtime}.squashfs"

cd "$GAMEDIR"
> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1

if [ ! -f "$GAMEDIR/game/archive.rpa" ]; then
  pm_message "Game files missing: copy Everlasting Summer's game folder contents into ports/everlastingsummer/game."
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

# The game ships for Ren'Py 7.4 (Python 2); this file adapts it to the Ren'Py 8 runtime.
cmp -s "$GAMEDIR/patches/zz_portmaster.rpy" "$gamefiles/zz_portmaster.rpy" || \
  cp -f "$GAMEDIR/patches/zz_portmaster.rpy" "$gamefiles/zz_portmaster.rpy"

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
# Text size multiplier: 1.0 is the PC size, which is about 7px tall on a 640x480 screen.
export ES_TEXT_SCALE="${ES_TEXT_SCALE:-1.5}"
# Software mouse cursor size (1.5 = about 20px tall); 0 uses the hardware cursor.
export ES_CURSOR_SCALE="${ES_CURSOR_SCALE:-1.5}"
# gles2 renders on the GPU; sw is the runtime's default software renderer.
export ES_RENDERER="${ES_RENDERER:-gles2}"
export RENPY_RENDERER="$ES_RENDERER"
export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"
# Ren'Py's base folder is the read-only runtime, so send its log.txt / traceback.txt here.
mkdir -p "$GAMEDIR/logs"
export RENPY_LOG_BASE="$GAMEDIR/logs"
export PYTHONHOME="$renpydir"
export PYTHONPATH="$renpydir/lib/python3.9"

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
