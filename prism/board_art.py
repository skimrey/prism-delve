"""Pixel-art pieces for the combat board: floor tiles, wall blocks, and the
special tiles a tower's twist puts in its floors (holes, springy caps,
snow, crystal facets, colour pools, currents, gusts). Painted at half size and scaled
2x, cached per place."""

import math

from .pixel import Pix, cached, mix, ramp, shade

K = 2                                   # board pixels are 2x2 screen pixels

MATERIALS = {                           # what a place's floor is made of (default: glazed tile)
    "leaning": "stone", "hollow": "wood", "toadstool": "spongy", "icicle": "ice", "sundial": "sand",
    "lens": "crystal", "lighthouse": "planks", "windmill": "planks",
}
HOLE_RIMS = ((255, 170, 60), (170, 110, 255), (60, 200, 230))


def material_for(place_id):
    return MATERIALS.get(place_id, "tile")


def floor_tile(size, color, material, variant=0):
    """One floor tile, `size` screen pixels square."""
    n = size // K

    def build():
        p = Pix(n, n, seed=variant * 13 + len(material))
        r = ramp(color)
        p.rect(1, 1, n - 2, n - 2, r[2])
        if material == "tile":                       # glazed: a soft shine in one corner
            p.rect(2, 2, n - 5, 1, r[3])
            p.rect(2, 2, 1, n - 5, r[3])
            p.px(4, 4, r[4])
            p.px(5, 4, r[4])
            p.px(4, 5, r[4])
        elif material == "stone":
            for _ in range(10):
                x, y = p.rng.randint(2, n - 3), p.rng.randint(2, n - 3)
                p.px(x, y, r[1])
            p.line((2, n // 2 + variant % 3), (n // 2, n // 2 + 2), r[1])
        elif material == "wood" or material == "planks":
            for x in range(2, n - 2, 5):
                p.line((x, 1), (x, n - 2), r[1])
            for _ in range(4):
                x, y = p.rng.randint(3, n - 4), p.rng.randint(3, n - 4)
                p.px(x, y, r[0])
                p.px(x + 1, y, r[1])
        elif material == "spongy":
            for _ in range(7):
                x, y = p.rng.randint(3, n - 4), p.rng.randint(3, n - 4)
                p.disc(x, y, 1, r[3])
                p.px(x, y + 1, r[1])
        elif material == "ice":
            p.line((3, n - 5), (n // 2, 6), r[4])
            p.line((n // 2, 6), (n - 4, 9), r[3])
            p.px(5, 5, (255, 255, 255))
        elif material == "sand":
            for _ in range(14):
                x, y = p.rng.randint(2, n - 3), p.rng.randint(2, n - 3)
                p.px(x, y, r[1] if (x + y) % 2 else r[3])
        elif material == "crystal":
            p.poly([(2, n - 3), (n // 2, 3), (n // 2 + 3, 3), (5, n - 3)], r[3])
            p.px(n // 2 + 1, 4, (255, 255, 255))
        # bevel: lit top-left, shadowed bottom-right, corners rounded off
        p.rect(1, 1, n - 2, 1, r[3])
        p.rect(1, 1, 1, n - 2, r[3])
        p.rect(1, n - 2, n - 2, 1, r[1])
        p.rect(n - 2, 1, 1, n - 2, r[1])
        for x, y in ((1, 1), (n - 2, 1), (1, n - 2), (n - 2, n - 2)):
            p.px(x, y, (0, 0, 0, 0))
        return p.up(K)
    return cached(("floor", n, tuple(color), material, variant % 3), build)


def wall_block(size, color, material):
    """A raised block, top face and front face, a little taller than a tile."""
    n = size // K

    def build():
        p = Pix(n, n + 4, seed=7)
        r = ramp(color)
        top, front = 1, n - 6
        p.rect(1, top + 2, n - 2, n - 2, r[0])                  # the drop shadow
        p.rect(1, front, n - 2, 8, r[1])                        # front face
        for x in range(3, n - 3, 4):
            p.px(x, front + 3, r[0])
        p.rect(1, top, n - 2, front - top, r[2])                # top face
        if material in ("stone", "tile", "sand"):
            for y in range(top + 4, front - 1, 5):
                p.line((2, y), (n - 3, y), r[1])
                off = 4 if (y // 5) % 2 else 8
                for x in range(off, n - 2, 9):
                    p.line((x, y - 4), (x, y - 1), r[1])
        elif material in ("wood", "planks"):
            for x in range(4, n - 2, 5):
                p.line((x, top + 1), (x, front - 2), r[1])
        elif material in ("ice", "crystal"):
            p.line((3, front - 3), (n - 6, top + 3), r[4])
            p.line((5, front - 3), (n - 4, top + 5), r[3])
        elif material == "spongy":
            for _ in range(6):
                p.disc(p.rng.randint(4, n - 5), p.rng.randint(top + 4, front - 4), 1, r[3])
        p.rect(2, top + 1, n - 4, 1, r[4])
        p.rect(2, top + 1, 1, front - top - 2, r[3])
        p.outline()
        return p.up(K)
    return cached(("wall", n, tuple(color), material), build)


def hole_tile(size, pair, frame, sea=False):
    """A knothole: a wooden rim glowing its pair's colour, and a slow swirl
    down into the dark. By the sea (`sea`), a blowhole: a rock rim and dark
    water, spraying a little."""
    n = size // K

    def build():
        p = Pix(n, n)
        c = n / 2
        rim = HOLE_RIMS[pair % len(HOLE_RIMS)]
        glow = 0.5 + 0.5 * math.sin(frame / 6 * math.tau)
        lip, lit, deep = ((120, 130, 150), (160, 172, 190), (20, 50, 90)) if sea else \
            ((150, 100, 60), (180, 126, 80), (34, 22, 30))
        p.disc(c, c, n * 0.42, mix(rim, (255, 255, 255), 0.3 * glow))
        p.disc(c, c, n * 0.36, lip)
        p.disc(c, c - 0.5, n * 0.36, lit)
        p.disc(c, c, n * 0.28, deep)
        for k in range(3):
            a = frame / 6 * math.tau / 3 + k * math.tau / 3
            p.px(c + math.cos(a) * n * 0.14, c + math.sin(a) * n * 0.12, mix(deep, rim if not sea else
                                                                             (200, 240, 255), 0.7))
        if sea and frame % 6 in (1, 2, 3):                      # a puff of spray
            h = (1, 3, 2)[frame % 6 - 1]
            for k in range(h):
                p.px(c - 1 + (k % 2) * 2, c - n * 0.2 - k * 2, (236, 250, 255))
        p.outline()
        return p.up(K)
    return cached(("hole", n, pair, frame % 6, sea), build)


def special_tile(size, kind, frame=0):
    """Springy cap, snow, crystal facet, colour pool, current or gust, painted on a tile."""
    n = size // K

    def build():
        p = Pix(n, n, seed=len(kind))
        c = n / 2
        if kind == "spring":
            squash = (0, 1, 0, 0, 0, 0)[frame % 6]
            p.rect(c - 2, c + 1, 5, 6, (240, 226, 200))              # a little stem
            p.ellipse(c - 9, c - 6 + squash, 19, 10 - squash, (230, 70, 90))
            p.ellipse(c - 8, c - 6 + squash, 16, 6 - squash, (250, 110, 120))
            for dx, dy in ((-4, -3), (3, -4), (0, -1)):
                p.px(c + dx, c + dy + squash, (255, 255, 255))
                p.px(c + dx + 1, c + dy + squash, (255, 255, 255))
        elif kind == "snow":                                  # a soft layer of snow over the tile
            p.rect(2, 3, n - 4, n - 5, (236, 244, 255))
            p.rect(3, 2, n - 6, n - 3, (246, 250, 255))
            for k in range(5):
                p.ellipse(2 + k * (n - 8) // 4, 1 + (k % 2), 8, 5, (255, 255, 255))
            for dx, dy in ((5, 9), (14, 15), (20, 7), (9, 20)):
                p.px(dx, dy, (200, 222, 250))
            if frame % 3 == 0:
                p.px(c + 4, c - 4, (170, 210, 255))
        elif kind.startswith("current:") or kind.startswith("gust:"):
            fdx, fdy = (int(v) for v in kind.split(":")[1].split(","))
            gust = kind.startswith("gust")
            base = (236, 246, 255) if gust else (110, 190, 236)
            if not gust:
                p.rect(2, 2, n - 4, n - 4, base)
                p.rect(3, 3, n - 6, n - 6, (130, 206, 246))
            off = (frame % 6) / 6.0
            for k in range(3):                                  # chevrons, marching along the flow
                f = ((k / 3.0) + off) % 1.0
                mx = c + fdx * (f - 0.5) * (n - 8)
                my = c + fdy * (f - 0.5) * (n - 8)
                col = (255, 255, 255) if not gust else (140, 170, 230)
                for w in range(-4, 5):
                    ax = mx - fdx * abs(w) * 0.8 + (w if fdy else 0)
                    ay = my - fdy * abs(w) * 0.8 + (w if fdx else 0)
                    p.px(ax, ay, col)
            if gust:
                for k in range(3):
                    p.px(4 + k * 7, 6 + (k * 5) % 13, (200, 220, 250))
        elif kind.startswith("bend"):
            slope = 1 if kind == "bend/" else -1
            pts = []
            for k in range(-8, 9):
                pts.append((c + k, c - slope * k))
            for w in range(-1, 2):
                for x, y in pts:
                    p.px(x, y + w, (200, 170, 255) if w else (255, 255, 255))
            for x, y in pts[::4]:
                p.px(x, y - 2, (150, 230, 250))
            p.disc(c, c, 2, (255, 250, 255))
        elif kind.startswith("pool:"):
            col = {"R": (240, 80, 96), "G": (80, 200, 110), "B": (80, 120, 240)}[kind[5:]]
            p.ellipse(c - 9, c - 5, 19, 12, shade(col, -1))
            p.ellipse(c - 8, c - 5, 17, 10, col)
            p.ellipse(c - 6, c - 4, 8, 3, shade(col, 2))
            ripple = frame % 6
            p.px(c + 2 + ripple // 2, c, shade(col, 3))
        p.outline()
        return p.up(K)
    return cached(("special", n, kind, frame % 6), build)


def pool_colour(kind):
    return kind[5:] if kind.startswith("pool:") else None
