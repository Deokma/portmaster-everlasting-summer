"""First-start build on the handheld, for a game folder copied straight from Steam.

Does on the device what tools/prepare_gamefiles.py does on a PC, with the Ren'Py
runtime's own Python and pygame_sdl2:

- shrinks every image in archive.rpa to the screen's size and writes
  portmaster_shrink.txt, so zz_portmaster.rpy draws them at their original size;
- keeps a full-size copy of the mouse cursor (portmaster_cursor.png);
- re-encodes video/opening.ogv for the screen height when ffmpeg is installed;
- removes Soviet Games' Windows mod uploader if it was copied into game/mods.

Prints one progress line at a time for the launcher to show, and writes
portmaster_build.txt when done, so it runs once.

    python build_game.py <game folder> <shrink factor> <screen height>
"""

import io
import os
import pickle
import shutil
import subprocess
import sys
import time
import zlib

GAME = sys.argv[1]
FACTOR = float(sys.argv[2])
HEIGHT = int(sys.argv[3])

STAMP = os.path.join(GAME, "portmaster_build.txt")
ARCHIVE = os.path.join(GAME, "archive.rpa")
IMAGE_EXTS = (".png", ".jpg", ".jpeg")
RPA_KEY = 0x42424242

# Soviet Games' ES Content Uploader, which lives in game/mods on Steam.
UPLOADER_FILES = ("ES_Content_Uploader.exe", "Qt5Core.dll", "Qt5Gui.dll", "Qt5Widgets.dll",
                  "steam_api.dll", "steam_appid.txt", "vc_redist.x86.exe")
UPLOADER_DIRS = ("editor", "imageformats", "platforms", "styles")


def say(text):
    print(text, flush=True)


def read_index(path):
    with open(path, "rb") as f:
        header = f.readline().decode("latin1").split()
        if not header or header[0] != "RPA-3.0":
            return None
        offset, key = int(header[1], 16), int(header[2], 16)
        f.seek(offset)
        index = pickle.loads(zlib.decompress(f.read()), encoding="bytes")

    entries = []
    for name, parts in index.items():
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        if len(parts) != 1 or (len(parts[0]) > 2 and parts[0][2]):
            return None
        entries.append((parts[0][0] ^ key, parts[0][1] ^ key, name))

    return sorted(entries)


def shrink_shard(images, shard, shards, work):
    """Child process: shrinks every `shards`-th image into work/<n>.<ext>."""

    import pygame_sdl2 as pg

    with open(ARCHIVE, "rb") as fin:
        for n in range(shard, len(images), shards):
            off, length, name = images[n]
            ext = os.path.splitext(name)[1].lower().replace(".jpeg", ".jpg")
            out = os.path.join(work, "%d%s" % (n, ext))

            try:
                fin.seek(off)
                surf = pg.image.load(io.BytesIO(fin.read(length)), name)
                w, h = surf.get_size()
                small = pg.transform.smoothscale(surf, (max(1, round(w / FACTOR)), max(1, round(h / FACTOR))))
                pg.image.save(small, out + ".tmp" + ext)
                os.replace(out + ".tmp" + ext, out)
            except Exception:
                pass  # The parent keeps the original for any image without an output.


def build_archive(entries):
    images = [e for e in entries if e[2].lower().endswith(IMAGE_EXTS)]
    others = [e for e in entries if not e[2].lower().endswith(IMAGE_EXTS)]

    # Room for the new archive: everything that isn't an image, plus shrunk images twice
    # (work files and archive).
    need = sum(e[1] for e in others) + sum(e[1] for e in images) / (FACTOR * FACTOR) * 3
    if shutil.disk_usage(GAME).free < need * 1.1:
        say("Not enough free space to shrink the images; playing them full size.")
        return

    # The runtime's Python has no multiprocessing module, so fork one child per core.
    work = os.path.join(GAME, "portmaster_build.tmp")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)

    shards = os.cpu_count() or 2
    children = []
    for shard in range(shards):
        pid = os.fork()
        if pid == 0:
            try:
                shrink_shard(images, shard, shards, work)
            finally:
                os._exit(0)
        children.append(pid)

    shown = -1
    while children:
        children = [pid for pid in children if os.waitpid(pid, os.WNOHANG) == (0, 0)]
        percent = sum(1 for f in os.listdir(work) if ".tmp" not in f) * 100 // len(images)
        if percent // 10 != shown // 10:
            shown = percent
            say("Shrinking images: %d%%" % percent)
        time.sleep(1)

    new = ARCHIVE + ".new"
    index = {}
    shrunk = []

    with open(ARCHIVE, "rb") as fin, open(new, "wb") as fout:
        fout.write(b"RPA-3.0 %016x %08x\n" % (0, RPA_KEY))

        def write(name, data):
            index[name] = [(fout.tell() ^ RPA_KEY, len(data) ^ RPA_KEY, b"")]
            fout.write(data)

        for off, length, name in others:
            fin.seek(off)
            write(name, fin.read(length))

        for n, (off, length, name) in enumerate(images):
            ext = os.path.splitext(name)[1].lower().replace(".jpeg", ".jpg")
            done = os.path.join(work, "%d%s" % (n, ext))

            if os.path.exists(done):
                with open(done, "rb") as f:
                    write(name, f.read())
                shrunk.append(name)
            else:
                fin.seek(off)
                write(name, fin.read(length))

        index_offset = fout.tell()
        fout.write(zlib.compress(pickle.dumps(index, protocol=2)))
        fout.seek(0)
        fout.write(b"RPA-3.0 %016x %08x\n" % (index_offset, RPA_KEY))

    os.replace(new, ARCHIVE)
    shutil.rmtree(work, ignore_errors=True)

    with open(os.path.join(GAME, "portmaster_shrink.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("%r\n" % (1.0 / FACTOR))
        f.write("\n".join(sorted(shrunk)) + "\n")


def keep_cursor(entries):
    out = os.path.join(GAME, "portmaster_cursor.png")
    for off, length, name in entries:
        if name == "images/misc/mouse/1.png" and not os.path.exists(out):
            with open(ARCHIVE, "rb") as fin, open(out, "wb") as fout:
                fin.seek(off)
                fout.write(fin.read(length))


def reencode_video():
    video = os.path.join(GAME, "video", "opening.ogv")
    if not os.path.isfile(video) or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return

    try:
        height = int(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height",
             "-of", "default=noprint_wrappers=1:nokey=1", video],
            capture_output=True, text=True, check=True).stdout.split()[0])
    except Exception:
        return

    # Theora encodes on one core: 360p takes about half as long as 480p on an H700 and
    # looks the same on a 3.5" screen.
    target = 360 if HEIGHT <= 480 else HEIGHT
    if height <= target:
        return

    say("Re-encoding the opening video (a few minutes)")
    tmp = os.path.join(GAME, "video", "opening.tmp.ogv")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video,
                        "-vf", "scale=-2:%d" % target, "-c:v", "libtheora", "-q:v", "7",
                        "-c:a", "libvorbis", "-q:a", "4", tmp])
    if r.returncode == 0:
        os.replace(tmp, video)
    elif os.path.exists(tmp):
        os.remove(tmp)


def remove_uploader():
    mods = os.path.join(GAME, "mods")
    if not os.path.isfile(os.path.join(mods, "ES_Content_Uploader.exe")):
        return

    say("Removing the Windows mod uploader from game/mods")
    for fn in os.listdir(mods):
        if fn in UPLOADER_FILES or (fn.startswith("ESCU_") and fn.endswith((".AppImage", ".tar.gz", ".zip"))):
            os.remove(os.path.join(mods, fn))

    for d in UPLOADER_DIRS:
        path = os.path.join(mods, d)
        scripts = any(f.endswith((".rpy", ".rpyc")) for _, _, fs in os.walk(path) for f in fs)
        if os.path.isdir(path) and not scripts:
            shutil.rmtree(path)


def main():
    if os.path.exists(STAMP) or not os.path.isfile(ARCHIVE):
        return

    remove_uploader()

    entries = read_index(ARCHIVE)
    if entries is not None:
        keep_cursor(entries)

        # A game folder built on a PC with prepare_gamefiles.py is already shrunk.
        if FACTOR > 1 and not os.path.exists(os.path.join(GAME, "portmaster_shrink.txt")):
            build_archive(entries)

    reencode_video()

    with open(STAMP, "w", encoding="utf-8", newline="\n") as f:
        f.write("shrink %g\n" % FACTOR)

    say("Done. Starting the game.")


if __name__ == "__main__":
    main()
