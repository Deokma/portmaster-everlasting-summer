"""Build dist/everlastingsummer.zip, the ready-to-unzip PortMaster release.

Packs port/ (the two launchers and everlastingsummer/) without any game files: game/ and
workshop/ keep only their README.txt, and nothing written on a handheld at run time is
included. Launchers keep their executable bit.

    python scripts/build_release.py
"""

import os
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PORT = os.path.join(ROOT, "port")
OUT = os.path.join(ROOT, "dist", "everlastingsummer.zip")

# Folders under everlastingsummer/ that hold the player's files or run-time state.
PLAYER_DIRS = {"game", "workshop"}
RUNTIME_DIRS = {"renpy", "conf", "logs", "tl_parked", "__pycache__"}
RUNTIME_FILES = {"log.txt", "font.ttf"}
SKIP_EXTS = (".pyc", ".rpyc")


def included(rel):
    parts = rel.split("/")

    if any(p in RUNTIME_DIRS for p in parts) or parts[-1] in RUNTIME_FILES or rel.endswith(SKIP_EXTS):
        return False

    if parts[0] == "everlastingsummer" and len(parts) > 2 and parts[1] in PLAYER_DIRS:
        return parts[2:] == ["README.txt"]

    if parts[:2] == ["everlastingsummer", "modmanager"] and len(parts) > 3:
        return False

    return True


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    names = []

    for dirpath, dirnames, filenames in os.walk(PORT):
        dirnames.sort()
        for fn in sorted(filenames):
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, PORT).replace(os.sep, "/")
            if included(rel):
                names.append((rel, path))

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, path in names:
            info = zipfile.ZipInfo.from_file(path, rel)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if rel.endswith(".sh") else 0o100644) << 16

            with open(path, "rb") as f:
                data = f.read()

            if rel.endswith((".sh", ".py", ".rpy", ".gptk", ".txt", ".md", ".json", ".xml")) and b"\r\n" in data:
                sys.exit("%s has Windows line endings; the handheld needs Unix ones." % rel)

            z.writestr(info, data)

    for rel, _ in names:
        print("  " + rel)
    print("%s: %d files, %.0f KB" % (os.path.normpath(OUT), len(names), os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
