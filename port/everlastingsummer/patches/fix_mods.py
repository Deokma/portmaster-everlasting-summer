"""Fix Ren'Py 7 syntax in mod scripts that Ren'Py 8's parser rejects.

The launcher runs this with the runtime's Python on every mod folder before Ren'Py
starts (Ren'Py parses mod scripts before the port's own patch gets to run).
tools/prepare_mods.py uses the same fix when it imports mods on a PC.

    python fix_mods.py <mod folder>...

Only .rpy files changed since the last run (per-folder .portmaster_fixed stamp) are read.
"""

import os
import re
import sys

STAMP = ".portmaster_fixed"

# `show eileen happy:` with nothing indented under it was an empty ATL block in
# Ren'Py 7; Ren'Py 8 stops with "show statement expects a non-empty block".
EMPTY_BLOCK = re.compile(r"^(\s*)((?:show|scene|hide)\b[^#\n]*?)\s*:\s*(#.*)?$")


def fix_rpy(text):
    """Returns (fixed text, number of fixes)."""

    lines = text.split("\n")
    fixes = 0

    for i, line in enumerate(lines):
        m = EMPTY_BLOCK.match(line)
        if not m:
            continue

        indent = len(m.group(1).expandtabs())
        following = next((l for l in lines[i + 1:] if l.strip() and not l.strip().startswith("#")), "")

        if len(following) - len(following.lstrip()) <= indent:
            lines[i] = m.group(1) + m.group(2) + ("  " + m.group(3) if m.group(3) else "")
            fixes += 1

    return "\n".join(lines), fixes


def fix_file(path):
    with open(path, "rb") as f:
        raw = f.read()

    try:
        text, fixes = fix_rpy(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return 0

    if fixes:
        with open(path, "wb") as f:
            f.write(text.encode("utf-8"))

    return fixes


def fix_folder(root):
    stamp = os.path.join(root, STAMP)
    since = os.path.getmtime(stamp) if os.path.exists(stamp) else 0
    fixes = 0

    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            if fn.lower().endswith(".rpy") and os.path.getmtime(path) > since:
                n = fix_file(path)
                if n:
                    print("fix_mods: %s: %d Ren'Py 7 syntax fixes" % (os.path.relpath(path, root), n))
                fixes += n

    try:
        open(stamp, "w").close()
    except OSError:
        pass

    return fixes


if __name__ == "__main__":
    for root in sys.argv[1:]:
        if os.path.isdir(root):
            fix_folder(root)
