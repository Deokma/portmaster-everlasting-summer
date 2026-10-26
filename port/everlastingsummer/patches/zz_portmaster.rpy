## PortMaster layer for Everlasting Summer.
##
## The Steam release is built for Ren'Py 7.4.11 (Python 2). PortMaster runs it on the
## shared Ren'Py 8.3.4 runtime, so this file patches the Python 3 incompatibilities,
## adds support for the downscaled assets made by tools/prepare_gamefiles.py, and tunes
## Ren'Py for a 1 GB handheld. The launcher copies it into game/ on every start.

python early hide:
    import renpy.display.im as im_

    # prepare_gamefiles.py --shrink writes this manifest when it downscales the images
    # in archive.rpa. Listed images get a fractional oversample, so they keep their
    # 1920x1080-space size on screen while holding a fraction of the pixels.
    shrunk = { }

    try:
        f = renpy.loader.load("portmaster_shrink.txt")
        try:
            lines = f.read().decode("utf-8").splitlines()
        finally:
            f.close()

        oversample = float(lines[0])

        for name in lines[1:]:
            if name:
                shrunk[name.lower()] = oversample

    except Exception:
        shrunk = { }

    im_.portmaster_shrunk = shrunk

    # The credits build im.Map ramps from chr() strings, which were bytes in Python 2.
    map_load = im_.Map.load

    def portmaster_map_load(self):
        for attr in ("rmap", "gmap", "bmap", "amap"):
            ramp = getattr(self, attr)

            if isinstance(ramp, str):
                setattr(self, attr, ramp.encode("latin-1"))

        return map_load(self)

    im_.Map.load = portmaster_map_load

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


init 999 python hide:
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


init 1500 python:

    # gptokeyb turns the controls into keys and a mouse, so Ren'Py's own gamepad
    # handling stays off to avoid double input.
    _preferences.pad_enabled = False

    # The game asks for a 1000-step rollback and Ren'Py's desktop cache sizes; these are
    # Ren'Py's defaults sized down for 1 GB of shared RAM.
    config.image_cache_size_mb = 64 if renpy.display.im.portmaster_shrunk else 160
    config.predict_statements = 16
    config.rollback_length = 128
    config.hard_rollback_limit = 100
    config.hw_video = False
