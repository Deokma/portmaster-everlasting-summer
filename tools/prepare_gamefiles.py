"""Build the PortMaster game folder for Everlasting Summer from a Steam install.

Copies what the game needs (leaving out the Windows modding tools, Steam's Python 2
caches and, unless asked, your saves), then optionally:

  --shrink N      downscale every image in archive.rpa by N (3 matches a 640x480
                  handheld: the 1920x1080 game is shown at 640x360). Writes
                  portmaster_shrink.txt so the port's zz_portmaster.rpy draws them at
                  their original size.
  --video-height  re-encode video/opening.ogv (1280x720 Theora) at this height.
  --languages     keep only these translations' dialogue (most of the script data;
                  Ren'Py loads every language at startup).

Needs Python 3.8+ and Pillow; the video step needs ffmpeg on PATH.

    python tools/prepare_gamefiles.py "E:/SteamLibrary/steamapps/common/Everlasting Summer"
"""

import argparse
import concurrent.futures
import io
import os
import pickle
import shutil
import subprocess
import sys
import time
import zlib

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "..", "port", "everlastingsummer", "game")

# Top-level folders of game/ that never go to the handheld.
SKIP_DIRS = {"mods", "cache"}
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
RPA_KEY = 0x42424242


def read_rpa_index(path):
    with open(path, "rb") as f:
        header = f.readline().decode("latin1").split()
        if header[0] != "RPA-3.0":
            sys.exit("%s: unsupported archive format %r" % (path, header[0]))
        offset, key = int(header[1], 16), int(header[2], 16)
        f.seek(offset)
        index = pickle.loads(zlib.decompress(f.read()), encoding="bytes")

    entries = []
    for name, parts in index.items():
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        if len(parts) != 1 or (len(parts[0]) > 2 and parts[0][2]):
            sys.exit("%s: split or prefixed archive entries are not supported (%s)" % (path, name))
        entries.append((parts[0][0] ^ key, parts[0][1] ^ key, name))

    entries.sort()
    return entries


def shrink_image(name, data, factor):
    """Returns re-encoded image bytes downscaled by `factor`."""

    im = Image.open(io.BytesIO(data))
    im.load()

    w, h = im.size
    size = (max(1, round(w / factor)), max(1, round(h / factor)))

    if name.lower().endswith((".jpg", ".jpeg")):
        im = im.convert("RGB").resize(size, Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "JPEG", quality=90, optimize=True)
    else:
        mode = "RGBA" if im.mode in ("RGBA", "LA", "P", "PA") or "transparency" in im.info else "RGB"
        im = im.convert(mode).resize(size, Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP" if name.lower().endswith(".webp") else "PNG", optimize=name.lower().endswith(".png"))

    return out.getvalue()


def shrink_job(args):
    name, data, factor = args
    try:
        return name, shrink_image(name, data, factor), None
    except Exception as e:
        return name, data, "%s: %s" % (type(e).__name__, e)


def rebuild_archive(src, dst, factor, jobs):
    """Writes a copy of archive.rpa with every image shrunk. Returns the shrunk names."""

    entries = read_rpa_index(src)
    index = {}
    shrunk = []
    failed = []

    with open(src, "rb") as fin, open(dst, "wb") as fout:
        fout.write(b"RPA-3.0 %016x %08x\n" % (0, RPA_KEY))

        def write_entry(name, data):
            index[name] = [(fout.tell() ^ RPA_KEY, len(data) ^ RPA_KEY, b"")]
            fout.write(data)

        def read_entry(off, length):
            fin.seek(off)
            return fin.read(length)

        images = [e for e in entries if e[2].lower().endswith(IMAGE_EXTS)]
        others = [e for e in entries if not e[2].lower().endswith(IMAGE_EXTS)]

        for off, length, name in others:
            write_entry(name, read_entry(off, length))

        before = sum(e[1] for e in images)
        after = 0
        start = time.time()

        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
            batch = 64
            for i in range(0, len(images), batch):
                work = [(name, read_entry(off, length), factor) for off, length, name in images[i:i + batch]]
                for name, data, error in pool.map(shrink_job, work):
                    if error:
                        failed.append((name, error))
                    else:
                        shrunk.append(name)
                    after += len(data)
                    write_entry(name, data)
                print("  images %d/%d" % (min(i + batch, len(images)), len(images)), end="\r", flush=True)

        print("  images %d/%d: %.0f MB -> %.0f MB in %.0fs" % (
            len(images), len(images), before / 1e6, after / 1e6, time.time() - start))

        index_offset = fout.tell()
        fout.write(zlib.compress(pickle.dumps(index, protocol=2)))
        fout.seek(0)
        fout.write(b"RPA-3.0 %016x %08x\n" % (index_offset, RPA_KEY))

    for name, error in failed:
        print("  ! kept original %s (%s)" % (name, error))

    return shrunk


def extract_entry(rpa, name, dst):
    """Copies one file out of an archive, untouched."""

    for off, length, entry in read_rpa_index(rpa):
        if entry == name:
            with open(rpa, "rb") as fin, open(dst, "wb") as fout:
                fin.seek(off)
                fout.write(fin.read(length))
            return True

    return False


def transcode_video(src, dst, height):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
        "-vf", "scale=-2:%d" % height,
        "-c:v", "libtheora", "-q:v", "7",
        "-c:a", "libvorbis", "-q:a", "4",
        dst,
    ]
    subprocess.run(cmd, check=True)


def copy_tree(src_game, out, with_saves, skip_files, languages):
    copied = 0
    for dirpath, dirnames, filenames in os.walk(src_game):
        rel = os.path.relpath(dirpath, src_game)
        parts = rel.split(os.sep)
        top = parts[0]

        if top in SKIP_DIRS or (top == "saves" and not with_saves):
            dirnames[:] = []
            continue

        # tl/<language>/scenario holds that language's dialogue; its menu strings
        # (tl/<language>/*.rpyc) are tiny and always kept.
        if languages is not None and parts[:1] == ["tl"] and parts[2:3] == ["scenario"] and parts[1] not in languages:
            dirnames[:] = []
            continue

        os.makedirs(os.path.join(out, rel), exist_ok=True)

        for fn in filenames:
            relfn = os.path.normpath(os.path.join(rel, fn))
            if relfn in skip_files:
                continue
            shutil.copy2(os.path.join(dirpath, fn), os.path.join(out, relfn))
            copied += os.path.getsize(os.path.join(dirpath, fn))

    return copied


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("install", help="Everlasting Summer install folder (the one holding game/)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output game folder (default: port/everlastingsummer/game)")
    ap.add_argument("--shrink", type=float, default=3, help="image downscale factor, 0 to keep originals (default 3)")
    ap.add_argument("--video-height", type=int, default=360, help="opening video height, 0 to keep original (default 360)")
    ap.add_argument("--languages", default="all",
                    help="translated dialogue to keep, e.g. english,german; 'none' keeps only the original "
                         "Russian. Each language costs about 6s of startup and 40 MB of RAM on the handheld (default all)")
    ap.add_argument("--with-saves", action="store_true", help="also copy game/saves (Ren'Py 7 saves, may not load)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count(), help="parallel image workers")
    args = ap.parse_args()

    src_game = os.path.join(args.install, "game")
    if not os.path.isfile(os.path.join(src_game, "archive.rpa")):
        sys.exit("No game/archive.rpa under %s" % args.install)

    out = os.path.abspath(args.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit("%s is not empty; delete it first." % out)
    os.makedirs(out, exist_ok=True)

    skip = set()
    if args.shrink:
        skip.add("archive.rpa")
    video = os.path.normpath("video/opening.ogv")
    if args.video_height and os.path.isfile(os.path.join(src_game, video)):
        skip.add(video)

    languages = None
    if args.languages != "all":
        languages = {l.strip().lower() for l in args.languages.split(",") if l.strip() and l.strip().lower() != "none"}

    print("Copying game files to %s" % out)
    copied = copy_tree(src_game, out, args.with_saves, skip, languages)
    print("  %.0f MB copied" % (copied / 1e6))

    if args.shrink:
        print("Shrinking images in archive.rpa by %gx" % args.shrink)
        shrunk = rebuild_archive(os.path.join(src_game, "archive.rpa"), os.path.join(out, "archive.rpa"), args.shrink, args.jobs)
        with open(os.path.join(out, "portmaster_shrink.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("%r\n" % (1.0 / args.shrink))
            f.write("\n".join(sorted(shrunk)) + "\n")

    # The port draws the mouse cursor itself (handheld GPUs have no hardware cursor);
    # this full-size copy keeps it sharp when the archive's images are shrunk.
    extract_entry(os.path.join(src_game, "archive.rpa"), "images/misc/mouse/1.png", os.path.join(out, "portmaster_cursor.png"))

    if video in skip:
        print("Re-encoding opening video at %dp" % args.video_height)
        transcode_video(os.path.join(src_game, video), os.path.join(out, video), args.video_height)

    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    print("Done: %.0f MB in %s" % (total / 1e6, out))


if __name__ == "__main__":
    main()
