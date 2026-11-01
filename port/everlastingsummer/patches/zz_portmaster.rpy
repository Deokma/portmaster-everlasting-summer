## PortMaster layer for Everlasting Summer.
##
## The Steam release is built for Ren'Py 7.4.11 (Python 2). PortMaster runs it on the
## shared Ren'Py 8.3.4 runtime, so this file patches the Python 3 incompatibilities,
## adds support for the downscaled assets made by tools/prepare_gamefiles.py, and tunes
## Ren'Py for a 1 GB handheld. The launcher copies it into game/ on every start.
##
## Each block imports the builtins its functions use: those functions run later, with
## the store as their globals, and the game puts its own values there (script.rpyc does
## `hour, min, sec = t.split(":")`).

python early hide:
    from builtins import getattr, int, isinstance, max, min, round, setattr, str, zip

    import os
    import renpy.display.im as im_

    # prepare_gamefiles.py --shrink writes this manifest when it downscales images: one
    # in game/ for archive.rpa, one in each Workshop mod folder the launcher adds to the
    # search path. Listed images get a fractional oversample, so they keep their
    # 1920x1080-space size on screen while holding a fraction of the pixels.
    shrunk = { }

    for root in renpy.config.searchpath:
        try:
            with open(os.path.join(root, "portmaster_shrink.txt"), "rb") as f:
                lines = f.read().decode("utf-8").splitlines()

            oversample = float(lines[0])

            for name in lines[1:]:
                if name:
                    shrunk.setdefault(name.lower(), oversample)

        except Exception:
            pass

    im_.portmaster_shrunk = shrunk

    # The runtime's compiled gl2 code reads config.mipmap, which its own 8.3.4 Python
    # side never defines. Shrunk images draw 1:1, so they don't need mipmaps.
    if not hasattr(renpy.config, "mipmap"):
        renpy.config.mipmap = not shrunk

    # The credits build im.Map ramps from chr() strings, which were bytes in Python 2.
    map_load = im_.Map.load

    def portmaster_map_load(self):
        for attr in ("rmap", "gmap", "bmap", "amap"):
            ramp = getattr(self, attr)

            if isinstance(ramp, str):
                setattr(self, attr, ramp.encode("latin-1"))

        return map_load(self)

    im_.Map.load = portmaster_map_load

    # Workshop mods are Python 2 code that indexes d.keys()[0] and the like; Python 3
    # returns views. Dicts made by game code are RevertableDicts, so hand them back
    # RevertableLists, which is what Python 2 gave and what rollback and saves expect.
    # (In the store, `dict` is RevertableDict itself, so call the builtin's methods.)
    import builtins
    import renpy.revertable as revertable_

    RevertableList = revertable_.RevertableList
    pydict = builtins.dict

    revertable_.RevertableDict.keys = lambda self: RevertableList(pydict.keys(self))
    revertable_.RevertableDict.values = lambda self: RevertableList(pydict.values(self))
    revertable_.RevertableDict.items = lambda self: RevertableList(pydict.items(self))

    # The game's settings, history, music room and mod list scroll only with a mouse
    # wheel, and options scrolled out of view can't take D-pad focus. Let PageUp and
    # PageDown (L1 / R1 through gptokeyb) page every wheel-scrolled viewport.
    import renpy.display.viewport as viewport_

    viewport_init = viewport_.Viewport.__init__

    def portmaster_viewport_init(self, *args, **properties):
        viewport_init(self, *args, **properties)

        if self.mousewheel:
            self.pagekeys = True

    viewport_.Viewport.__init__ = portmaster_viewport_init

    if shrunk:

        image_init = im_.Image.__init__

        def portmaster_image_init(self, filename, *args, **properties):
            if "oversample" not in properties and isinstance(filename, str):
                oversample = shrunk.get(filename.replace("\\", "/").lower())

                if oversample:
                    properties["oversample"] = oversample

            image_init(self, filename, *args, **properties)

        im_.Image.__init__ = portmaster_image_init

        # Ren'Py multiplies by the oversample without rounding, which only works for
        # whole-number factors. These are the stock load() methods with rounding added.

        def rounded(v):
            return int(round(v))

        def composite_load(self):
            oversample = self.oversample

            if self.size:
                size = [ rounded(s * oversample) for s in self.size ]
            else:
                size = im_.cache.get(self.images[0]).get_size()

            rv = renpy.display.pgrender.surface(size, True)

            for pos, image in zip(self.positions, self.images):
                rv.blit(im_.cache.get(image), [ rounded(p * oversample) for p in pos ])

            return rv

        def crop_load(self):
            oversample = self.oversample
            surf = im_.cache.get(self.image)
            sw, sh = surf.get_size()

            x = min(rounded(self.x * oversample), sw)
            y = min(rounded(self.y * oversample), sh)
            w = min(rounded(self.w * oversample), sw - x)
            h = min(rounded(self.h * oversample), sh - y)

            return surf.subsurface((x, y, w, h))

        def scale_load(self):
            child = im_.cache.get(self.image)
            size = (max(1, rounded(self.width * self.oversample)), max(1, rounded(self.height * self.oversample)))

            with renpy.display.render.blit_lock:
                if self.bilinear:
                    return renpy.display.scale.smoothscale(child, size)
                else:
                    return renpy.display.pgrender.transform_scale(child, size)

        im_.Composite.load = composite_load
        im_.Crop.load = crop_load
        im_.Scale.load = scale_load


python early:
    # Python 2 builtins that Workshop mods use and Ren'Py 8's store doesn't define.
    import functools as _portmaster_functools

    xrange = range
    unichr = chr
    long = int
    reduce = _portmaster_functools.reduce


init -999 python hide:
    from builtins import int, max, min

    import os

    # PortMaster's renpy_8.3.4 runtime ships with GL off, so every port falls back to
    # Ren'Py's slow software renderer. The Mali GLES2 driver handles gl2 fine;
    # ES_RENDERER=sw in the launcher restores the runtime's default.
    config.gl_enable = os.environ.get("ES_RENDERER", "gl") != "sw"

    # ES_ASPECT: how the 16:9 game uses a screen of another shape (the RG40XX H is 4:3).
    # "fit" letterboxes it, "stretch" fills the screen by stretching it (33% taller on
    # 4:3), "zoom" fills it at the right proportions by cutting off the sides.
    def portmaster_view_size(width, height, mode=os.environ.get("ES_ASPECT", "fit")):
        game_w, game_h = config.screen_width, config.screen_height
        fit = min(1.0 * width / game_w, 1.0 * height / game_h)
        fill = max(1.0 * width / game_w, 1.0 * height / game_h)

        if mode == "stretch":
            return width, height
        elif mode == "zoom":
            return int(game_w * fill), int(game_h * fill)
        else:
            return int(game_w * fit), int(game_h * fit)

    config.adjust_view_size = portmaster_view_size


init 999 python hide:
    from builtins import enumerate, int, list, min, round

    import renpy.display.im as im_

    # pyclasses.rpyc defines its own crop that slices surfaces in 1920x1080 units.
    if im_.portmaster_shrunk and hasattr(store, "VerticalCrop"):

        def vertical_crop_load(self):
            oversample = self.image.get_oversample()
            surf = im_.cache.get(self.image)
            width, height = surf.get_size()

            y = min(int(round(self.y * oversample)), height)
            h = min(int(round(self.h * oversample)), height - y)

            return surf.subsurface((0, y, width, h))

        store.VerticalCrop.load = vertical_crop_load
        store.VerticalCrop.get_oversample = lambda self: self.image.get_oversample()

    # filters/img_filters.rpyc walks Ren'Py's image table with dict.iteritems(), which
    # Python 3 dicts lack. Same logic, Python 3 spelling.
    if hasattr(store, "lb__recolor"):

        def lb__recolor(im_op):
            images = renpy.display.image.images

            for id, img in list(images.items()):
                try:
                    for i, (c, sub) in enumerate(img.child.args[0]):
                        img.child.args[0][i] = (c, im_op(sub))
                except Exception:
                    try:
                        images[id] = im_op(img)
                    except Exception:
                        pass

            for id in list(store.map_pics):
                store.map_pics[id] = im_op(store.map_pics[id])

        store.lb__recolor = lb__recolor


init 1500 python hide:
    from builtins import float

    import os

    # gptokeyb turns the controls into keys and a mouse, so Ren'Py's own gamepad
    # handling stays off to avoid double input.
    _preferences.pad_enabled = False

    # Some Workshop mods ship with developer mode on; Ren'Py would then load its
    # _developer tools at init 1700, which the runtime doesn't include.
    config.developer = False

    # Mods name DejaVuSans, which Ren'Py 7 bundled and the Ren'Py 8 runtime doesn't.
    # prepare_gamefiles.py copies it from the Steam install; for a game folder copied
    # straight over, the game's own Calibri (with Cyrillic) stands in.
    if not renpy.loadable("DejaVuSans.ttf") and renpy.loadable("fonts/calibri.ttf"):
        for name, bold in (("DejaVuSans.ttf", False), ("DejaVuSans.ttf", True), ("DejaVuSans-Bold.ttf", False)):
            config.font_replacement_map[(name, bold, False)] = ("fonts/calibrib.ttf" if bold or "Bold" in name else "fonts/calibri.ttf", False, False)

    # Text laid out for 1080p comes out about 7px tall on a 640x360 screen. The launcher
    # sets ES_TEXT_SCALE; Ren'Py multiplies every font size by this preference.
    _preferences.font_size = float(os.environ.get("ES_TEXT_SCALE", "1.0"))

    # Handheld display drivers have no hardware cursor, so the gptokeyb mouse was
    # invisible. Ren'Py draws the game's cursor into the frame instead, scaled by
    # ES_CURSOR_SCALE (0 keeps the hardware cursor).
    cursor_scale = float(os.environ.get("ES_CURSOR_SCALE", "0"))

    if cursor_scale and config.mouse:
        cursor, cursor_x, cursor_y = config.mouse["default"][0]

        # Full-size copy written by prepare_gamefiles.py, so shrinking doesn't blur it.
        if renpy.loadable("portmaster_cursor.png"):
            cursor = "portmaster_cursor.png"

        config.mouse = None
        config.mouse_displayable = MouseDisplayable(Transform(cursor, zoom=cursor_scale), cursor_x * cursor_scale, cursor_y * cursor_scale)

    # The game asks for a 1000-step rollback and Ren'Py's desktop cache sizes; these are
    # Ren'Py's defaults sized down for 1 GB of shared RAM. A game folder copied straight
    # from Steam (full-size images) already uses about 650 MB on the RG40XX H.
    config.image_cache_size_mb = 64 if renpy.display.im.portmaster_shrunk else 96
    config.predict_statements = 16
    config.rollback_length = 128
    config.hard_rollback_limit = 100
    config.hw_video = False
