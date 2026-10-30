"""Shrink Everlasting Summer Steam Workshop mods for the PortMaster port.

Optional: a Workshop folder copied straight from steamapps/workshop/content/331470/<id>
into the port's workshop/ folder already works. This makes it load faster and use less
RAM on a 1 GB handheld. For each mod it writes port/everlastingsummer/workshop/<id>/:
images shrunk like the game's (with the mod's own portmaster_shrink.txt), videos
re-encoded at 360p, Windows-only files dropped, Ren'Py 7 syntax fixed, and the mod's
Workshop title in portmaster_mod.txt for the on-device mod manager.

Needs Python 3.8+ and Pillow; video re-encoding needs ffmpeg and ffprobe on PATH.

    python tools/prepare_mods.py "E:/SteamLibrary/steamapps/workshop/content/331470"
"""

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT_DIR = os.path.join(HERE, "..", "port", "everlastingsummer")
DEFAULT_OUT = os.path.join(PORT_DIR, "workshop")

# The launcher runs the same fixer on the handheld for mods copied straight from Steam.
sys.path[:0] = [HERE, os.path.join(PORT_DIR, "patches")]
from fix_mods import fix_rpy  # noqa: E402
from prepare_gamefiles import IMAGE_EXTS, rebuild_archive, shrink_image  # noqa: E402

VIDEO_EXTS = (".webm", ".ogv", ".mp4", ".mkv", ".avi", ".m4v")

# Windows binaries, editor and Steam leftovers, and Python 2 bytecode caches.
SKIP_EXTS = (".dll", ".exe", ".docx", ".sfk", ".db", ".rpyb", ".bak")

# Encoder per source codec, so a re-encoded video stays in a format Ren'Py already played.
VIDEO_ENCODERS = {
    "theora": ["-c:v", "libtheora", "-q:v", "7"],
    "vp8": ["-c:v", "libvpx", "-crf", "10", "-b:v", "1M"],
    "vp9": ["-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0"],
    "h264": ["-c:v", "libx264", "-crf", "23", "-preset", "veryfast"],
}

def workshop_titles(ids):
    """Looks up mod titles with Steam's public Workshop API; missing ones stay unnamed."""

    data = {"itemcount": len(ids)}
    for i, mod_id in enumerate(ids):
        data["publishedfileids[%d]" % i] = mod_id

    try:
        req = urllib.request.Request(
            "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
            data=urllib.parse.urlencode(data).encode())
        with urllib.request.urlopen(req, timeout=20) as r:
            details = json.load(r)["response"]["publishedfiledetails"]
    except Exception as e:
        print("  ! could not look up titles (%s); using Workshop ids" % e)
        return {}

    return {d["publishedfileid"]: d["title"] for d in details if d.get("title")}


def probe_video(path):
    """Returns (codec, height) of the first video stream, or (None, 0)."""

    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,height", "-of", "json", path],
            capture_output=True, check=True, text=True).stdout
        stream = json.loads(out)["streams"][0]
        return stream["codec_name"], int(stream.get("height") or 0)
    except Exception:
        return None, 0


def transcode(src, dst, height):
    """Re-encodes a video at `height` with its own codec. Returns False to copy it as-is."""

    codec, src_height = probe_video(src)
    if codec not in VIDEO_ENCODERS or src_height <= height:
        return False

    cmd = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
            "-vf", "scale=-2:%d" % height] + VIDEO_ENCODERS[codec] + ["-c:a", "copy", dst])

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        if os.path.exists(dst):
            os.remove(dst)
        return False


def copy_rpy(src, dst, name):
    with open(src, "rb") as f:
        raw = f.read()

    try:
        text, fixes = fix_rpy(raw.decode("utf-8"))
    except UnicodeDecodeError:
        fixes = 0

    if fixes:
        with open(dst, "wb") as f:
            f.write(text.encode("utf-8"))
        print("  %s: %d Ren'Py 7 syntax fixes" % (name, fixes))
    else:
        shutil.copy2(src, dst)


def shrink_file(args):
    src, dst, factor = args
    try:
        with open(src, "rb") as f:
            data = shrink_image(src, f.read(), factor)
        with open(dst, "wb") as f:
            f.write(data)
        return src, None
    except Exception as e:
        shutil.copy2(src, dst)
        return src, "%s: %s" % (type(e).__name__, e)


def import_mod(src, dst, factor, video_height, pool):
    """Copies one Workshop item into `dst`, shrinking as it goes. Returns the shrunk names."""

    images = []
    shrunk = []

    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, src)
        os.makedirs(os.path.join(dst, rel_dir), exist_ok=True)

        for fn in filenames:
            low = fn.lower()
            if fn.startswith(".") or low.endswith(SKIP_EXTS):
                continue

            s = os.path.join(dirpath, fn)
            d = os.path.join(dst, rel_dir, fn)
            name = os.path.normpath(os.path.join(rel_dir, fn)).replace(os.sep, "/")

            if factor and low.endswith(IMAGE_EXTS):
                images.append((s, d, name))

            elif factor and low.endswith(".rpa"):
                try:
                    shrunk += rebuild_archive(s, d, factor, None)
                except ValueError as e:
                    print("  ! %s copied as-is (%s)" % (name, e))
                    shutil.copy2(s, d)

            elif low.endswith(".rpy"):
                copy_rpy(s, d, name)

            elif video_height and low.endswith(VIDEO_EXTS):
                if transcode(s, d, video_height):
                    print("  video %s re-encoded at %dp" % (name, video_height))
                else:
                    shutil.copy2(s, d)

            else:
                shutil.copy2(s, d)

    by_src = {s: name for s, _, name in images}
    for s, error in pool.map(shrink_file, [(s, d, factor) for s, d, _ in images], chunksize=8):
        if error:
            print("  ! kept original %s (%s)" % (by_src[s], error))
        else:
            shrunk.append(by_src[s])

    return shrunk


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workshop", help="steamapps/workshop/content/331470 (one folder per mod)")
    ap.add_argument("--ids", help="comma-separated Workshop ids to import (default: every folder)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output folder (default: port/everlastingsummer/workshop)")
    ap.add_argument("--shrink", type=float, default=3, help="image downscale factor, 0 to keep originals (default 3)")
    ap.add_argument("--video-height", type=int, default=360, help="re-encode taller videos to this height, 0 to keep (default 360)")
    ap.add_argument("--force", action="store_true", help="re-import mods that are already in --out")
    ap.add_argument("--jobs", type=int, default=os.cpu_count(), help="parallel image workers")
    args = ap.parse_args()

    ids = sorted((i.strip() for i in args.ids.split(",")) if args.ids else os.listdir(args.workshop), key=lambda i: (len(i), i))
    ids = [i for i in ids if os.path.isdir(os.path.join(args.workshop, i))]
    if not ids:
        sys.exit("No mod folders found in %s" % args.workshop)

    titles = workshop_titles(ids)
    os.makedirs(args.out, exist_ok=True)

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for mod_id in ids:
            title = titles.get(mod_id, mod_id)
            dst = os.path.join(args.out, mod_id)
            print("%s  %s" % (mod_id, title))

            if os.path.exists(dst):
                if not args.force:
                    print("  already imported (use --force to redo)")
                    continue
                shutil.rmtree(dst)

            shrunk = import_mod(os.path.join(args.workshop, mod_id), dst, args.shrink, args.video_height, pool)

            if shrunk:
                with open(os.path.join(dst, "portmaster_shrink.txt"), "w", encoding="utf-8", newline="\n") as f:
                    f.write("%r\n" % (1.0 / args.shrink))
                    f.write("\n".join(sorted(shrunk)) + "\n")

            with open(os.path.join(dst, "portmaster_mod.txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write(title + "\n")

            size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(dst) for f in fs)
            print("  %d images shrunk, %.0f MB" % (len(shrunk), size / 1e6))


if __name__ == "__main__":
    main()
