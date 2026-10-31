## Everlasting Summer mod manager (PortMaster).
##
## Lists the Steam Workshop mods in everlastingsummer/workshop/. Every mod there loads
## unless it is unticked here (saved to workshop/disabled.txt), and mods can be deleted.
## The launcher runs this as a separate small Ren'Py game when started with ES_APP=mods.

define config.name = "Everlasting Summer mods"
define config.window_title = "Everlasting Summer mods"
define config.screen_width = 640
define config.screen_height = 480
define config.developer = False
define config.has_autosave = False
define config.rollback_enabled = False
define _game_menu_screen = None

define PAGE_SIZE = 9

style default:
    font "DejaVuSans.ttf"
    size 18
    color "#e8e8e8"

style mm_button:
    padding (6, 3, 6, 3)
    hover_background "#2f6db5"

style mm_button_text:
    size 18
    idle_color "#e8e8e8"
    hover_color "#ffffff"
    insensitive_color "#555555"

style mm_hint:
    size 14
    color "#8a96a8"

init python:
    import os
    import re
    import shutil
    import struct
    import zlib

    WORKSHOP = os.environ.get("ES_WORKSHOP", "")
    DISABLED_FILE = os.path.join(WORKSHOP, "disabled.txt")

    # Measured on the RG40XX H: the game (Russian + English) with two small mods takes
    # about 455 MB, and each MB of a mod's compiled script adds about 9 MB once loaded.
    BASE_MB = 450
    MB_PER_SCRIPT_MB = 9
    LIMIT_MB = 850

    # How a mod adds itself to the game's mod list: mods["label"] = "Title".
    MOD_ENTRY = re.compile(r"""mods\[\s*u?["']([^"']+)["']\s*\]\s*=\s*(?:u?["']([^"'\n]+)["'])?""")

    def script_text(path):
        """Returns a .rpy's text, or the Python source kept inside a .rpyc."""

        with open(path, "rb") as f:
            data = f.read()

        if path.lower().endswith(".rpyc"):
            if not data.startswith(b"RENPY RPC2"):
                return ""

            pos = 10
            while True:
                slot, start, length = struct.unpack("<III", data[pos:pos + 12])
                if slot in (0, 1):
                    break
                pos += 12

            data = zlib.decompress(data[start:start + length]) if slot == 1 else b""

        return data.decode("utf-8", "ignore")

    def find_title(path):
        """The title a mod gives itself in the game's mod list, else its label."""

        label = None

        for d, _, files in os.walk(path):
            for f in files:
                if not f.lower().endswith((".rpy", ".rpyc")):
                    continue

                try:
                    m = MOD_ENTRY.search(script_text(os.path.join(d, f)))
                except Exception:
                    continue

                if m and m.group(2):
                    # Drop text tags such as {font=mods/x/title.ttf}, which point into the mod.
                    return re.sub(r"\{[^{}]*\}", "", m.group(2)).strip() or m.group(1)

                label = label or (m and m.group(1))

        return label

    class Mod(object):

        def __init__(self, folder):
            self.folder = folder
            self.path = os.path.join(WORKSHOP, folder)
            title_file = os.path.join(self.path, "portmaster_mod.txt")

            # tools/prepare_mods.py writes the Workshop title here; for a mod copied straight
            # from Steam it is found once in the mod's own scripts and remembered.
            try:
                with open(title_file, encoding="utf-8") as f:
                    self.title = f.readline().strip() or folder
            except Exception:
                self.title = find_title(self.path) or folder

                try:
                    with open(title_file, "w", encoding="utf-8", newline="\n") as f:
                        f.write(self.title + "\n")
                except Exception:
                    pass

            # A .rpy without its .rpyc gets compiled to one of about the same size.
            script = 0

            for d, _, files in os.walk(self.path):
                names = set(f.lower() for f in files)

                for f in files:
                    low = f.lower()
                    if low.endswith(".rpyc") or (low.endswith(".rpy") and low + "c" not in names):
                        script += os.path.getsize(os.path.join(d, f))

            self.script_mb = script / 1e6
            self.optimized = os.path.exists(os.path.join(self.path, "portmaster_shrink.txt"))

            # Shown through Ren'Py text, where [ and { start substitutions and tags.
            self.shown_title = self.title.replace("[", "[[").replace("{", "{{")

    def scan_mods():
        if not os.path.isdir(WORKSHOP):
            return [ ]

        folders = [ f for f in os.listdir(WORKSHOP)
                    if os.path.isdir(os.path.join(WORKSHOP, f)) and not f.startswith((".", "_")) ]

        return sorted((Mod(f) for f in folders), key=lambda m: m.title.lower())

    def read_enabled():
        try:
            with open(DISABLED_FILE, encoding="utf-8") as f:
                disabled = set(l.strip() for l in f if l.strip())
        except Exception:
            disabled = set()

        return set(m.folder for m in mods if m.folder not in disabled)

    def memory_mb():
        return BASE_MB + sum(m.script_mb * MB_PER_SCRIPT_MB for m in mods if m.folder in enabled)

    def save_and_quit(play):
        with open(DISABLED_FILE, "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(m.folder + "\n" for m in mods if m.folder not in enabled))

        if play:
            open(os.path.join(WORKSHOP, ".play"), "w").close()

        renpy.quit()

    def delete_mod(mod):
        shutil.rmtree(mod.path, ignore_errors=True)
        enabled.discard(mod.folder)
        mods.remove(mod)

        store.page = min(store.page, max(0, (len(mods) - 1) // PAGE_SIZE))
        renpy.restart_interaction()


screen confirm_delete(mod):
    modal True
    style_prefix "mm"

    add Solid("#000000c0")

    frame:
        align (0.5, 0.5)
        padding (20, 16)
        background "#1f2a3c"

        vbox:
            spacing 14
            text "Delete this mod from the handheld?"
            text mod.shown_title color "#f0d070"

            hbox:
                spacing 20
                textbutton "Delete" action [ Function(delete_mod, mod), Hide("confirm_delete") ]
                textbutton "Keep" action Hide("confirm_delete") default_focus True

    key "K_ESCAPE" action Hide("confirm_delete")


screen mod_manager():
    style_prefix "mm"

    add Solid("#141b26")

    $ shown = mods[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    $ pages = max(1, (len(mods) + PAGE_SIZE - 1) // PAGE_SIZE)
    $ memory = memory_mb()

    vbox:
        xpos 16
        ypos 12
        xsize 608
        spacing 4

        text "Workshop mods" size 26
        text "D-pad move · A tick / untick · B quit without saving" style "mm_hint"

        null height 6

        if not mods:
            text "No mods yet. Copy Steam Workshop mod folders (steamapps/workshop/content/331470/<id>) into ports/everlastingsummer/workshop/, or import them with tools/prepare_mods.py on a PC." size 16

        for i, m in enumerate(shown):
            hbox:
                xfill True

                textbutton ("[[x] " if m.folder in enabled else "[[ ] ") + m.shown_title:
                    action ToggleSetMembership(enabled, m.folder)
                    text_size 17
                    xsize 470
                    default_focus (i == 0)

                text "{:.1f} MB".format(m.script_mb * MB_PER_SCRIPT_MB) size 14 yalign 0.5 color ("#8a96a8" if m.optimized else "#d0a050")

                textbutton "Del" action Show("confirm_delete", mod=m) xalign 1.0 text_size 15

        null height 6

        if pages > 1:
            hbox:
                spacing 12
                textbutton "< Prev" action SetVariable("page", page - 1) sensitive (page > 0)
                text "Page {} of {}".format(page + 1, pages) yalign 0.5 size 15
                textbutton "Next >" action SetVariable("page", page + 1) sensitive (page < pages - 1)

    vbox:
        xpos 16
        yalign 1.0
        yoffset -10
        spacing 6

        text "Memory if started: about {} of {} MB".format(int(memory), LIMIT_MB) size 15 color ("#ff7060" if memory > LIMIT_MB else "#8a96a8")
        text "Orange sizes: copied straight from Steam, not shrunk on a PC (slower, more RAM)." style "mm_hint"

        hbox:
            spacing 18
            textbutton "Play" action Function(save_and_quit, True)
            textbutton "Save and exit" action Function(save_and_quit, False)
            textbutton "Cancel" action Quit(confirm=False)

    key "K_ESCAPE" action Quit(confirm=False)


label start:
    $ mods = scan_mods()
    $ enabled = read_enabled()
    $ page = 0
    call screen mod_manager
    return
