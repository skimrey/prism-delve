"""Painting the Meadow hub as pixel art.

The whole landscape is painted every frame on a 240x160 canvas (one canvas
pixel = 4x4 screen pixels) and scaled up: sky in bands, parallax layers for
each zone (hills, tree trunks, mountain peaks, mesas, the sea...), the
ground column by column with its texture, the zone's features (roots, rocks,
pools, ice, drifts, caps, crystals, gusts), plants, towers, and little things
flying about. Colours blend from one zone into the next as you roll along.
Characters and words are drawn by meadow.py on top.
"""

import math
import random

import pygame

from .consts import COLOR_RGB, FLOORS, RAINBOW
from .pixel import OUTLINE, Pix, cached, mix, ramp, shade
from .world import ZONES

K = 4
LW, LH = 240, 160


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def mix_pal(a, b, k):
    return tuple(mix(a[i], b[i], k) for i in range(len(a)))


# ---------------------------------------------------------------- sprites

def sky_canvas(top, bottom):
    def build():
        p = Pix(LW, LH)
        p.vgrad(0, 0, LW, LH, top, bottom, steps=10)
        return p.s
    return cached(("sky", top, bottom), build)


def sun_sprite(color):
    def build():
        p = Pix(30, 30)
        for i in range(12):
            a = i * math.tau / 12
            for k in range(11, 14):
                p.px(15 + math.cos(a) * k, 15 + math.sin(a) * k, shade(color, 1))
        p.disc(15, 15, 9, shade(color, -1))
        p.disc(15, 15, 8, color)
        p.disc(13, 13, 4, shade(color, 2))
        return p.s
    return cached(("sun", color), build)


def cloud_sprite(v):
    def build():
        rng = random.Random(v)
        p = Pix(40, 16)
        for _ in range(6):
            x, y, r = rng.randint(8, 32), rng.randint(7, 10), rng.randint(4, 7)
            p.disc(x, y, r, (255, 255, 255))
        for x in range(40):
            for y in range(8, 16):
                c = p.get(x, y)
                if c and c[3] and y > 10:
                    p.px(x, y, (226, 238, 252))
        return p.s
    return cached(("cloud", v), build)


def far_sprite(kind, v, color):
    """Background silhouettes for a zone's far layer."""
    def build():
        rng = random.Random(v * 31 + len(kind))
        c = ramp(color)
        if kind == "trunks":
            w = rng.randint(6, 12)
            p = Pix(w * 4 + 8, 130)
            p.rect(w * 2 - w // 2 + 4, 20, w, 110, c[1])
            p.rect(w * 2 - w // 2 + 4, 20, 2, 110, c[2])
            for _ in range(5):
                p.disc(rng.randint(4, w * 4 + 4), rng.randint(4, 24), rng.randint(6, 12), c[2])
            for _ in range(3):
                p.disc(rng.randint(4, w * 4 + 4), rng.randint(2, 16), rng.randint(3, 6), c[3])
            return p.s
        if kind == "mushrooms":
            h = rng.randint(40, 80)
            cw = rng.randint(18, 30)
            p = Pix(cw * 2 + 4, h + 4)
            p.rect(cw - 3, 12, 7, h, c[2])
            p.ellipse(2, 2, cw * 2, 18, c[1])
            p.ellipse(4, 2, cw * 2 - 4, 12, c[3])
            for _ in range(4):
                p.disc(rng.randint(8, cw * 2 - 6), rng.randint(5, 11), 2, shade(color, 3))
            return p.s
        if kind == "peaks":
            w, h = rng.randint(50, 90), rng.randint(50, 80)
            p = Pix(w, h)
            p.poly([(0, h), (w // 2, 0), (w, h)], c[2])
            p.poly([(w // 2, 0), (w, h), (w // 2 + 6, h)], c[1])
            p.poly([(w // 2 - 10, 16), (w // 2, 0), (w // 2 + 10, 16), (w // 2 + 3, 12), (w // 2 - 3, 18)],
                   (250, 252, 255))
            return p.s
        if kind == "mesas":
            w, h = rng.randint(40, 80), rng.randint(26, 46)
            p = Pix(w, h)
            p.poly([(0, h), (6, 4), (w - 6, 4), (w, h)], c[2])
            p.rect(6, 4, w - 12, 3, c[3])
            for y in range(10, h, 7):
                p.line((3, y), (w - 3, y), c[1])
            return p.s
        if kind == "stalagmites":
            w, h = rng.randint(10, 22), rng.randint(30, 70)
            p = Pix(w, h)
            p.poly([(0, h), (w // 2, 0), (w, h)], c[1])
            p.poly([(w // 2, 0), (w // 2 - 2, h), (0, h)], c[2])
            if rng.random() < 0.5:
                p.px(w // 2, h // 2, (220, 180, 255))
            return p.s
        if kind == "islands":
            w = rng.randint(30, 50)
            p = Pix(w, 40)
            p.ellipse(0, 10, w, 8, (120, 200, 100))
            p.poly([(2, 14), (w - 2, 14), (w // 2, 36)], c[1])
            p.poly([(w // 2, 14), (w - 2, 14), (w // 2, 36)], c[0])
            p.disc(w // 3, 7, 5, (90, 170, 90))
            p.rect(w // 3, 8, 1, 5, (120, 90, 60))
            for k in range(8):                               # a little waterfall
                p.px(w * 2 // 3, 18 + k * 2, (200, 230, 255))
            return p.s
        return Pix(1, 1).s
    return cached(("far", kind, v, color), build)


PLANT_COLS = ((255, 110, 140), (255, 214, 90), (140, 170, 255), (255, 150, 80), (230, 120, 240), (120, 220, 230))


def plant_sprite(kind, v):
    """The little plants of every zone (each a few pixels)."""
    def build():
        rng = random.Random(v * 7 + len(kind))
        col = PLANT_COLS[v % len(PLANT_COLS)]
        if kind == "flower":
            h = rng.randint(3, 7)
            p = Pix(5, h + 3)
            p.rect(2, 2, 1, h, (60, 150, 70))
            p.px(1, h // 2 + 2, (90, 190, 90))
            p.rect(1, 0, 3, 3, col)
            p.px(2, 1, (255, 240, 170))
            return p.s
        if kind == "tuft":
            p = Pix(5, 4)
            for x in (0, 2, 4):
                p.line((x, 3), (x + rng.choice((-1, 0, 1)) * 0, rng.randint(0, 2)), (80, 170, 80))
            return p.s
        if kind == "fern":
            p = Pix(9, 7)
            for a in (-2.5, -2.0, -1.57, -1.1, -0.6):
                for k in range(5):
                    p.px(4 + math.cos(a) * k, 6 + math.sin(a) * k, (50, 140, 70) if k < 4 else (110, 210, 100))
            return p.s
        if kind == "bloom":
            p = Pix(7, 11)
            p.rect(3, 4, 1, 7, (50, 140, 70))
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                p.rect(3 + dx - 1, 3 + dy - 1, 2, 2, col)
            p.px(3, 3, (255, 240, 160))
            return p.s
        if kind == "glowshroom":
            glow = ((120, 240, 230), (250, 150, 230), (190, 250, 140))[v % 3]
            p = Pix(7, 7)
            p.rect(3, 3, 1, 4, (230, 220, 200))
            p.ellipse(0, 0, 7, 4, glow)
            p.px(2, 1, (255, 255, 255))
            return p.s
        if kind == "pine":
            h = rng.randint(12, 20)
            p = Pix(11, h + 2)
            for k in range(3):
                y0 = 2 + k * (h // 4)
                p.poly([(5, y0), (0, y0 + h // 2), (10, y0 + h // 2)], (50, 120, 100))
                p.line((2, y0 + h // 2), (8, y0 + h // 2), (250, 252, 255))
                p.px(5, y0, (250, 252, 255))
            p.rect(5, h - 2, 1, 4, (110, 80, 60))
            return p.s
        if kind == "icecrystal":
            p = Pix(5, 7)
            p.poly([(2, 0), (4, 3), (2, 6), (0, 3)], (200, 236, 255))
            p.px(1, 2, (255, 255, 255))
            return p.s
        if kind == "cactus":
            h = rng.randint(8, 14)
            p = Pix(9, h + 1)
            p.rect(3, 0, 3, h + 1, (80, 170, 90))
            p.rect(3, 0, 1, h + 1, (120, 210, 110))
            p.rect(0, h // 2, 3, 2, (80, 170, 90))
            p.rect(0, h // 2 - 3, 2, 3, (80, 170, 90))
            p.rect(6, h // 3 + 2, 3, 2, (80, 170, 90))
            p.rect(7, h // 3 - 1, 2, 3, (80, 170, 90))
            if v % 3 == 0:
                p.px(4, 0, (255, 120, 160))
            return p.s
        if kind == "drygrass":
            p = Pix(6, 5)
            for x in (0, 2, 3, 5):
                p.line((x, 4), (x + (1 if x < 3 else -1), rng.randint(0, 2)), (200, 170, 100))
            return p.s
        if kind == "crystal":
            c = ((190, 150, 255), (120, 230, 240), (255, 150, 210))[v % 3]
            h = rng.randint(5, 11)
            p = Pix(7, h + 1)
            p.poly([(1, h), (2, 2), (3, 0), (4, 2), (5, h)], c)
            p.line((2, h - 1), (2, 3), shade(c, 2))
            return p.s
        if kind == "seagrass":
            p = Pix(5, 8)
            for x in (1, 3):
                for y in range(8):
                    p.px(x + (1 if (y // 2) % 2 else 0), 7 - y, (90, 180, 110))
            return p.s
        if kind == "shell":
            p = Pix(5, 3)
            p.ellipse(0, 0, 5, 4, ((255, 200, 200), (255, 230, 190), (220, 220, 255))[v % 3])
            p.line((2, 0), (2, 2), (220, 160, 160))
            return p.s
        if kind == "windflower":
            p = Pix(5, 8)
            p.rect(2, 3, 1, 5, (60, 150, 70))
            p.disc(2, 2, 2, (250, 250, 255))
            p.px(2, 2, (255, 220, 120))
            return p.s
        return Pix(1, 1).s
    return cached(("plant", kind, v % 12), build)


def ground_texture(zone_kind):
    """A 64x160 strip of a zone's ground: a lit top band, then soil with
    stones and specks, darker the deeper it goes."""
    top, body, deep = ZONES[zone_kind]["ground"]

    def build():
        p = Pix(64, LH, seed=len(zone_kind))
        for y in range(LH):
            c = mix(body, deep, min(1.0, y / 60.0))
            p.rect(0, y, 64, 1, c)
        r = ramp(body)
        for _ in range(160):
            x, y = p.rng.randint(0, 63), p.rng.randint(4, LH - 1)
            c = mix(body, deep, min(1.0, y / 60.0))
            p.px(x, y, shade(c, p.rng.choice((-1, -1, 1))))
        for _ in range(14):                                      # stones
            x, y = p.rng.randint(0, 60), p.rng.randint(8, LH - 4)
            p.rect(x, y, 3, 2, mix(r[1], deep, 0.4))
            p.px(x, y, mix(r[3], deep, 0.3))
        return p.s
    return cached(("groundtex", zone_kind), build)


def blended_texture(a, b, f):
    """Zone a's ground fading into zone b's (f from 0 to 1)."""
    def build():
        out = ground_texture(a).copy()
        top = ground_texture(b).copy()
        top.set_alpha(int(255 * f))
        out.blit(top, (0, 0))
        return out
    return cached(("groundmix", a, b, f), build)


def rock_sprite(w, h, zone_kind, v):
    def build():
        base = {"frost": (190, 200, 220), "dunes": (214, 150, 100), "caves": (110, 96, 150),
                "coast": (140, 136, 150)}.get(zone_kind, (150, 140, 176))
        c = ramp(base)
        p = Pix(w + 2, h + 2, seed=v)
        p.ellipse(1, 1, w, h + 4, c[1])
        p.ellipse(1, 1, w - 3, h, c[2])
        p.ellipse(3, 2, w // 2, h // 2, c[3])
        p.px(4, 3, c[4])
        top = {"frost": (250, 252, 255), "dunes": (250, 220, 160)}.get(zone_kind, (110, 200, 90))
        p.ellipse(w // 4, 0, w // 2, 3, top)
        p.outline()
        return p.s
    return cached(("rock", w, h, zone_kind, v), build)


def crystal_cluster(h, v):
    def build():
        cols = ((190, 150, 255), (120, 230, 240), (255, 150, 210))
        p = Pix(h, h + 2, seed=v)
        for i in range(4):
            c = cols[(v + i) % 3]
            x = 2 + i * (h - 6) // 3
            hh = h - abs(i - 1.5) * h * 0.25
            p.poly([(x - 2, h + 1), (x, h + 1 - hh), (x + 1, h - hh), (x + 3, h + 1)], c)
            p.line((x - 1, h), (x, h + 2 - hh), shade(c, 2))
        p.outline()
        return p.s
    return cached(("crystals", h, v), build)


def cap_sprite(v):
    """A big bouncy mushroom cap (springs)."""
    def build():
        p = Pix(20, 10)
        p.rect(8, 5, 4, 5, (240, 228, 206))
        p.ellipse(0, 0, 20, 9, (226, 64, 84))
        p.ellipse(1, 0, 17, 5, (250, 110, 120))
        for x in (4, 9, 14):
            p.rect(x, 2, 2, 1, (255, 255, 255))
        p.outline()
        return p.s
    return cached(("cap", v), build)


def sorter_sprite():
    """The Sorter, where you came from: three floors in their colours, a roof,
    and the Round Door at the top (the Long Ramp ends by your feet)."""
    def build():
        p = Pix(40, 120, seed=4)
        for k, act in enumerate((3, 2, 1)):
            col = FLOORS[act]["wall"]
            p.bricks(4, 22 + k * 32, 32, 32, mix(col, (255, 255, 255), 0.35), bw=5, bh=3)
            p.rect(3, 22 + k * 32, 34, 2, shade(col, -1))
            p.rect(16, 32 + k * 32, 8, 10, (40, 30, 60))
            p.rect(17, 33 + k * 32, 6, 8, (255, 222, 130))
        p.poly([(0, 23), (40, 23), (20, 2)], (250, 220, 150))
        p.poly([(20, 2), (40, 23), (22, 23)], (230, 190, 120))
        p.disc(20, 15, 4, (255, 250, 220))
        p.ring(20, 15, 4, (200, 160, 100))
        p.outline()
        return p.s
    return cached(("sorter",), build)


# ---------------------------------------------------------------- painter

class HubPainter:
    """Holds where everything is (plants, far things, ambient life), and
    paints the world at camera `cam` onto a low-res canvas."""

    def __init__(self, world, land, width, epilogue=False):
        self.world, self.land, self.width = world, land, width
        self.epilogue = epilogue
        rng = random.Random(12)
        self.plants = []
        for z in world.zones:
            lo = z.start + (60 if z.index == 0 else 0)
            hi = min(width - 30, (z.kick - 40) if z.index == 0 else z.kick - 40)
            if z.index == 0 and epilogue:
                hi = width - 40
            x = lo
            kinds = z.spec["plants"]
            while x < hi:
                if not self._clear(x, z):
                    x += rng.uniform(8, 26)
                    continue
                self.plants.append((x, rng.choice(kinds), rng.randrange(12)))
                x += rng.uniform(8, 26)
            # past the tower, a bit more of the same while the next zone fades in
        self.clouds = [(rng.uniform(0, LW + 80), rng.uniform(4, 46), rng.randrange(4)) for _ in range(5)]
        self.far = []                                            # (parallax x, zone kind, variant)
        for z in world.zones:
            kind = z.spec["far"]
            if kind in ("hills", "sea"):
                continue
            x = (z.start - 1600) * 0.5                          # (half speed: they cover twice the ground)
            end = (z.end if z.index + 1 < len(world.zones) else width) * 0.5 + LW * K
            while x < end:
                self.far.append((x, z.kind, kind, rng.randrange(6)))
                x += rng.uniform(60, 200) if kind != "stalagmites" else rng.uniform(24, 70)
        self.life = []                                           # (x, y, phase, zone kind)
        for z in world.zones:
            hi = min(width, z.end)
            for _ in range(int((hi - z.start) / 140)):
                self.life.append((rng.uniform(z.start, hi), rng.uniform(20, 110), rng.uniform(0, math.tau),
                                  z.kind, rng.randrange(6)))
        self.over = []                                           # vines, stalactites
        for z in world.zones:
            if not z.spec.get("over"):
                continue
            x = z.start + 400
            while x < min(width, z.end):
                self.over.append((x, z.spec["over"], rng.uniform(8, 40), rng.uniform(0, math.tau)))
                x += rng.uniform(40, 110)

    def _clear(self, x, z):
        if z.pool_at(x) is not None or (z.index == 0 and abs(x - 2500) < 160):
            return False
        for kind, fx, size in z.features:
            if kind in ("root", "rock", "crystal", "spring") and abs(x - fx) < 90:
                return False
        return True

    # -- palette, blending from one zone into the next
    def palette(self, x):
        z = self.world.zone_at(x)
        spec = z.spec
        if z.index == 0:
            return spec, 1.0, None
        prev = self.world.zones[z.index - 1].spec
        k = smooth((x - z.start) / 1600.0)
        return spec, k, prev

    def blend(self, x, key):
        spec, k, prev = self.palette(x)
        if prev is None or k >= 1.0:
            return spec[key]
        return mix_pal(prev[key], spec[key], round(k * 12) / 12)

    # -- the whole picture
    def paint(self, L, cam, t, towers):
        """`towers`: [(zone, friend (shape, colour) or None, door open)]."""
        cx = cam + 480
        cl = int(round(cam / K))
        self.windows = []                       # (x, y, radius, friend) of who's waving at a window
        sky = self.blend(cx, "sky")
        L.blit(sky_canvas(tuple(sky[0]), tuple(sky[1])), (0, 0))
        spec, k, prev = self.palette(cx)
        here = spec if (k >= 0.5 or prev is None) else prev          # whose far things show
        sun = here.get("sun")
        if sun:
            L.blit(sun_sprite(sun), (190, 8))
        if here["far"] != "stalagmites":
            for x, y, v in self.clouds:
                X = (x - cam * 0.06 + t * 1.5) % (LW + 80) - 40
                L.blit(cloud_sprite(v), (int(X), int(y)))
        self._hills(L, cam, t)
        for px, zkind, kind, v in self.far:
            if ZONES[zkind] is not here:
                continue
            X = int((px - cam * 0.5) / K)
            if -80 < X < LW + 10:
                col = ZONES[zkind]["hills"][1]
                img = far_sprite(kind, v, col)
                Y = (104 if kind != "islands" else 20 + (v * 9) % 30) - img.get_height() + (
                    40 if kind in ("trunks",) else 0)
                if kind == "stalagmites":
                    Y = 118 - img.get_height()
                L.blit(img, (X, Y))
        if self.world.zones[0].start - cam < 1000:
            L.blit(sorter_sprite(), (int(-10 - cam * 0.8 / K), 4))
        for zone, friend, open_door in towers:
            self._tower(L, zone, cam, t, friend, open_door)
            if not open_door:
                self._flag(L, zone.lip, cam, t)
        self._ground(L, cam, cl)
        for zone in self.world.zones:
            self._features(L, zone, cam, t)
        if not self.epilogue or True:
            self._pond(L, cam, t)
        for x, kind, v in self.plants:
            X = int(x / K) - cl
            if -8 < X < LW + 8:
                img = plant_sprite(kind, v)
                L.blit(img, (X - img.get_width() // 2, int(self.land(x) / K) - img.get_height() + 1))
        self._life(L, cam, t)

    def paint_front(self, L, cam, t):
        """Things in front of everyone: vines and stalactites hanging down."""
        cl = int(round(cam / K))
        for x, kind, ln, ph in self.over:
            X = int(x / K) - cl
            if not -4 < X < LW + 4:
                continue
            if kind == "vines":
                sway = math.sin(t * 0.9 + ph) * 2
                for y in range(int(ln)):
                    xx = X + int(sway * (y / ln) ** 2)
                    L.set_at((xx, y), (40, 110, 70)) if 0 <= xx < LW else None
                    if y % 4 == 2 and 0 <= xx + 1 < LW:
                        L.set_at((xx + 1, y), (100, 200, 100))
            else:
                c = (70, 54, 110)
                w = max(2, int(ln / 6))
                pygame.draw.polygon(L, c, [(X - w, 0), (X + w, 0), (X, int(ln * 0.8))])
                pygame.draw.line(L, (120, 100, 170), (X - w + 1, 0), (X, int(ln * 0.8) - 2))
                if int(ph * 3) % 2 == 0:
                    drip = (t * 20 + ph * 40) % 60
                    L.set_at((X, min(LH - 1, int(ln * 0.8 + drip))), (190, 170, 255))

    def _hills(self, L, cam, t):
        hills = self.blend(cam + 480, "hills")
        spec, k, prev = self.palette(cam + 480)
        far = spec["far"] if k > 0.5 or prev is None else prev["far"]
        for layer, (par, amp, y0) in enumerate(((0.18, 12, 88), (0.35, 9, 100))):
            col = tuple(hills[layer])
            pts = [(0, LH)]
            for X in range(0, LW + 4, 2):
                wx = X * K + cam * par
                if far == "peaks":
                    h = abs(((wx * 0.004 + layer) % 2) - 1) * amp * 3.2
                elif far == "sea" and layer == 0:
                    h = 6 + math.sin(wx * 0.02 + t * 1.5) * 0.6
                else:
                    h = amp * (1 + math.sin(wx * 0.006 + layer)) + 4 * math.sin(wx * 0.017)
                pts.append((X, int(y0 - h)))
            pts.append((LW, LH))
            pygame.draw.polygon(L, col, pts)
            if far == "sea" and layer == 0:                       # glints on the sea
                for i in range(12):
                    gx = int((i * 23 + t * 6) % LW)
                    L.set_at((gx, int(y0 - 5) + (i % 3)), (230, 246, 255))
            elif far == "peaks":
                for X in range(0, LW, 2):
                    wx = X * K + cam * par
                    top = y0 - abs(((wx * 0.004 + layer) % 2) - 1) * amp * 3.2
                    if top < y0 - amp * 2.2:
                        pygame.draw.line(L, (250, 252, 255), (X, int(top)), (X + 1, int(top) + 3))

    def _ground(self, L, cam, cl):
        """The ground, one column at a time, with its zone's texture."""
        world = self.world
        for X in range(LW + 1):
            wx = (X + cl) * K
            top = int(self.land(wx) / K)
            if top >= LH:
                continue
            z = world.zone_at(wx)
            zkind = z.kind
            tex = ground_texture(zkind)
            g = ZONES[zkind]["ground"][0]
            if z.index > 0 and wx - z.start < 800:               # blend from the last zone's ground
                prev = world.zones[z.index - 1].kind
                f = int((wx - z.start) / 800.0 * 16) / 16.0
                tex = blended_texture(prev, zkind, f)
                g = mix(ZONES[prev]["ground"][0], g, f)
            L.blit(tex, (X, top), (((X + cl) % 64), 0, 1, LH - top))
            L.set_at((X, top), shade(g, 1)) if 0 <= top < LH else None
            if top + 1 < LH:
                L.set_at((X, top + 1), g)
            if top + 2 < LH:
                L.set_at((X, top + 2), shade(g, -1))
            if (X + cl) % 5 == 0 and top - 1 >= 0:                # grass blades along the top
                L.set_at((X, top - 1), g)

    def _features(self, L, z, cam, t):
        cl = int(round(cam / K))
        for kind, fx, size in z.features:
            X = int(fx / K) - cl
            if not -40 < X < LW + 40 and kind not in ("ice", "drift", "sand", "gust"):
                continue
            if kind == "root":
                pts_top, pts_low = [], []
                for wx in range(int(fx - 60), int(fx + 61), 4):
                    x = int(wx / K) - cl
                    y = int(self.land(wx) / K)
                    bump = size * math.exp(-((wx - fx) / 26.0) ** 2) / K
                    pts_top.append((x, y))
                    pts_low.append((x, min(y + 5, y + bump + 1)))
                pygame.draw.polygon(L, shade((54, 150, 74), -2), pts_top + pts_low[::-1])
                band = pts_top + [(x, min(y + 4, ly)) for (x, y), (_x, ly) in zip(pts_top[::-1], pts_low[::-1])]
                pygame.draw.polygon(L, (146, 98, 58), band)
                pygame.draw.lines(L, OUTLINE, False, pts_top, 1)
                pygame.draw.lines(L, (186, 136, 88), False, [(x, y + 1) for x, y in pts_top[2:-2]], 1)
            elif kind == "rock":
                w = int(size * 2.4 / K)
                img = rock_sprite(w, int(size * 1.3 / K), z.kind, int(fx) % 5)
                L.blit(img, (X - img.get_width() // 2, int(self.land(fx) / K) - 2))
            elif kind == "crystal":
                img = crystal_cluster(int(size / K) + 4, int(fx) % 3)
                L.blit(img, (X - img.get_width() // 2, int(self.land(fx) / K) - img.get_height() + 8))
                if int(t * 3 + fx) % 4 == 0:
                    L.set_at((X, int(self.land(fx) / K) - 6), (255, 255, 255))
            elif kind == "spring":
                img = cap_sprite(0)
                squash = 1 if (t * 2 + fx) % 1.0 < 0.1 else 0
                L.blit(img, (X - 10, int(self.land(fx) / K) - 6 + squash))
            elif kind == "pool":
                level = z.pool_at(fx)[2]
                lvl = int(level / K)
                x0, x1 = int((fx - size) / K) - cl, int((fx + size) / K) - cl
                basin = [(x, lvl + int(14 * (1 - ((x + cl) * K - fx) ** 2 / size ** 2)))
                         for x in range(x0, x1 + 1)]
                pygame.draw.polygon(L, (48, 150, 176), [(x0, lvl)] + basin + [(x1, lvl)])
                deep = [(x, lvl + (y - lvl) // 2 + 3) for x, y in basin]
                pygame.draw.polygon(L, (34, 110, 140), [(x0 + 4, lvl + 3)] + deep[4:-4] + [(x1 - 4, lvl + 3)])
                pygame.draw.line(L, (160, 236, 240), (x0, lvl), (x1, lvl))
                for i in range(5):
                    gx = x0 + int((i * 13 + t * 8) % max(1, x1 - x0))
                    L.set_at((gx, lvl + 1), COLOR_RGB[RAINBOW[i]])
                if z.kind in ("wilds", "grove"):
                    for i in range(3):
                        px = x0 + (x1 - x0) * (i + 1) // 4
                        pygame.draw.ellipse(L, (80, 170, 80), (px - 3, lvl - 1, 7, 3))
            elif kind in ("ice", "drift", "sand", "gust"):
                x0, x1 = int(fx / K) - cl, int((fx + size) / K) - cl
                if x1 < -2 or x0 > LW + 2:
                    continue
                for x in range(max(0, x0), min(LW, x1)):
                    wx = (x + cl) * K
                    y = int(self.land(wx) / K)
                    if kind == "ice":
                        L.set_at((x, y), (230, 248, 255))
                        L.set_at((x, y + 1), (170, 220, 250))
                        L.set_at((x, y + 2), (150, 200, 240))
                        if (x + cl) % 11 == 0:
                            L.set_at((x, y), (255, 255, 255))
                    elif kind == "drift":
                        for k in range(3):
                            L.set_at((x, y + k), (255, 255, 255) if k < 2 else (210, 226, 250))
                        if (x + cl) % 7 == 0:
                            L.set_at((x, y - 1), (255, 255, 255))
                    elif kind == "sand":
                        if (x + cl) % 4 == 0:
                            L.set_at((x, y + 2), (220, 180, 120))
                    elif kind == "gust":
                        pass
                if kind == "gust":                               # streaks of wind, blowing right
                    for i in range(10):
                        sx = x0 + ((i * 37 + t * 60) % max(1, x1 - x0))
                        sy = int(self.land((sx + cl) * K) / K) - 8 - (i * 7) % 40
                        if 0 <= sx < LW - 6:
                            pygame.draw.line(L, (255, 255, 255), (int(sx), sy), (int(sx) + 5, sy))

    def _flag(self, L, lip, cam, t):
        """A little flag at the lip of a kicker, so you know where to hop."""
        X = int(lip / K) - int(round(cam / K))
        if not -10 < X < LW + 10:
            return
        Y = int(self.land(lip - 1) / K)
        pygame.draw.line(L, OUTLINE, (X, Y), (X, Y - 10))
        wave = int(t * 5) % 2
        pygame.draw.polygon(L, (255, 214, 72), [(X + 1, Y - 10), (X + 6, Y - 9 + wave), (X + 1, Y - 7)])

    def _pond(self, L, cam, t):
        if self.world.zones[0].start > 0:
            return
        cx = int(2500 / K) - int(round(cam / K))
        if not -50 < cx < LW + 50:
            return
        gy = int(self.land(2500) / K)
        pygame.draw.ellipse(L, OUTLINE, (cx - 38, gy - 4, 77, 12))
        pygame.draw.ellipse(L, (150, 220, 250), (cx - 37, gy - 3, 75, 10))
        for i, c in enumerate(RAINBOW):
            a = t * 0.7 + i * math.tau / 6
            pygame.draw.ellipse(L, COLOR_RGB[c], (int(cx + math.cos(a) * 22) - 6, int(gy + math.sin(a) * 2), 12, 3))

    def _life(self, L, cam, t):
        cl = int(round(cam / K))
        for x, y, ph, zkind, v in self.life:
            amb = ZONES[zkind]["ambient"]
            X = int((x + math.sin(t * 0.5 + ph) * 60) / K) - cl
            if not 0 <= X < LW - 2:
                continue
            c = PLANT_COLS[v]
            if amb == "moths":
                Y = int(y + math.sin(t * 2.2 + ph) * 6)
                flap = int(t * 10 + ph) % 2
                L.set_at((X, Y), c)
                L.set_at((X + 2, Y), c)
                if flap:
                    L.set_at((X, Y - 1), c)
                    L.set_at((X + 2, Y - 1), c)
            elif amb == "fireflies":
                glow = 0.5 + 0.5 * math.sin(t * 3 + ph * 5)
                if glow > 0.3:
                    Y = int(y + 40 + math.sin(t * 1.3 + ph) * 5)
                    L.set_at((X, Y), mix(c, (255, 255, 200), 0.6))
                    if glow > 0.8:
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            L.set_at((X + dx, Y + dy), mix(c, (40, 80, 60), 0.4))
            elif amb == "spores":
                Y = int((y + 120 - t * 6 - ph * 20) % 130)
                L.set_at((X, Y), ((150, 255, 230), (255, 190, 240), (220, 255, 160))[v % 3])
            elif amb == "snow":
                Y = int((y + t * 10 + ph * 30) % LH)
                X2 = int(X + math.sin(t + ph) * 3) % LW
                L.set_at((X2, Y), (255, 255, 255))
            elif amb == "dust":
                Y = int(y + 50 + math.sin(t + ph) * 4)
                X2 = int(X + t * 8) % LW
                L.set_at((X2, Y), (255, 230, 180))
            elif amb == "sparkles":
                tw = (t * 1.5 + ph) % 2.0
                if tw < 0.3:
                    Y = int(y + 20)
                    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                        L.set_at((X + dx, Y + dy), (255, 255, 255) if (dx, dy) == (0, 0) else (200, 170, 255))
            elif amb == "gulls":
                Y = int(y * 0.5 + 8 + math.sin(t * 1.5 + ph) * 3)
                X2 = int(X + t * 4) % LW
                flap = int(t * 4 + ph) % 2
                for dx in (-2, -1, 1, 2):
                    L.set_at((X2 + dx, Y - (1 if abs(dx) == 1 and flap else 0)), (250, 250, 255))
            elif amb == "petals":
                Y = int((y + t * 8 + ph * 20) % 120)
                X2 = int(X + t * 12 + math.sin(t * 2 + ph) * 4) % LW
                L.set_at((X2, Y), (255, 190, 220))

    def _tower(self, L, zone, cam, t, friend, open_door):
        from .towers_art import overlay, tower_canvas
        img, meta = tower_canvas(zone.tower, open_door)
        cl = int(round(cam / K))
        wx, wy = meta["win"]
        left = int(zone.window[0] / K) - cl - wx
        if not -img.get_width() < left < LW:
            return
        base = int(self.land(zone.wall + 60) / K)
        top = base - img.get_height() + 1
        L.blit(img, (left, top))
        overlay(L, zone.tower, meta, left, top, 1, t)
        if friend is not None:                  # (drawn smooth, on top, by the screen: see windows)
            self.windows.append(((left + wx + 0.5) * K, (top + wy + 0.5) * K, meta["win_r"] * K, friend))


# ---------------------------------------------------------------- title

def title_scene(t, towers=()):
    """The title screen's picture (240x160, to scale 4x): a dusky pink sky
    with stars, far hills, the Sorter on the left with its Round Door
    glowing, a rainbow Long Ramp, the Meadow at the bottom, any towers
    you've found standing far off on the right, and a floating island for
    Tri to stand on."""
    L = pygame.Surface((LW, LH))
    from .scene import TITLE_SKY
    L.blit(sky_canvas(TITLE_SKY[0], TITLE_SKY[1]), (0, 0))
    rng = random.Random(5)
    for i in range(40):                                          # stars, twinkling
        x, y = rng.randrange(LW), rng.randrange(70)
        if (i + int(t * 3)) % 7:
            L.set_at((x, y), (255, 240, 255) if i % 3 else (255, 220, 150))
    for layer, (col, y0, amp, par) in enumerate((((170, 110, 220), 118, 10, 0.3), ((140, 90, 200), 128, 7, 0.6))):
        pts = [(0, LH)] + [(X, int(y0 - amp * (1 + math.sin(X * 0.05 + layer * 2 + t * 0.02 * par))))
                           for X in range(0, LW + 4, 2)] + [(LW, LH)]
        pygame.draw.polygon(L, col, pts)
    for i, img in enumerate(towers):                             # towers you've found, far off
        x = LW - 30 - i * 22
        L.blit(img, (x - img.get_width() // 2, 132 - img.get_height()))
    L.blit(sorter_sprite(), (4, 18))
    glow = 0.5 + 0.5 * math.sin(t * 2)
    pygame.draw.circle(L, mix((255, 250, 220), (255, 200, 120), glow), (24, 33), 5)
    for k in range(14):                                          # the Long Ramp, a rainbow band
        x0, y0 = 44 + k * 6, 40 + k * 6
        for j, c in enumerate(RAINBOW):
            L.set_at((x0 + j // 2, y0 + 2 + j // 2), COLOR_RGB[c])
            pygame.draw.line(L, COLOR_RGB[c], (x0, y0 + j), (x0 + 6, y0 + 6 + j))
    tex = ground_texture("meadow")
    for X in range(LW):                                          # the Meadow, at the bottom
        top = int(138 + 3 * math.sin(X * 0.06) + 2 * math.sin(X * 0.15))
        L.blit(tex, (X, top), (X % 64, 0, 1, LH - top))
        L.set_at((X, top), (170, 240, 140))
        L.set_at((X, top + 1), (130, 220, 104))
    for i in range(30):
        x = rng.randrange(LW)
        top = int(138 + 3 * math.sin(x * 0.06) + 2 * math.sin(x * 0.15))
        img = plant_sprite("flower", i)
        L.blit(img, (x, top - img.get_height() + 1))
    # a floating island for Tri to stand on
    pygame.draw.polygon(L, (120, 84, 70), [(37, 76), (203, 76), (190, 84), (150, 90), (90, 90), (50, 84)])
    pygame.draw.polygon(L, (150, 110, 90), [(40, 76), (200, 76), (186, 81), (60, 81)])
    pygame.draw.rect(L, (130, 220, 104), (37, 74, 167, 3))
    pygame.draw.line(L, (170, 240, 140), (37, 74), (203, 74))
    for x in range(40, 200, 3):
        L.set_at((x, 73 - (x % 2)), (130, 220, 104))
    pygame.draw.lines(L, OUTLINE, False, [(36, 74), (37, 77), (50, 85), (90, 91), (150, 91), (191, 85), (204, 77),
                                          (204, 74)])
    return L
