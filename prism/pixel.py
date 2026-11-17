"""A tiny pixel-art kit. Scenery is painted here at low resolution, one pixel
at a time (bricks, shingles, bark, leaves, ice...), with hue-shifted shading
ramps and a dark outline, then scaled up with nearest-neighbour so every pixel
stays crisp. Everything is cached: a tower is painted once.

    ramp(colour)        five shades: shadows lean purple-blue, lights lean warm
    Pix(w, h, seed)     a low-res canvas with brushes (bricks, shingles, leaves...)
    sprite(rows, pal)   a small hand-drawn sprite from text rows
    critter(...)        a shape with a face, painted as pixel art
"""

import colorsys
import functools
import math
import random

import pygame

OUTLINE = (38, 24, 58)           # the dark outline every sprite gets (a warm near-black)
SHADOW_HUE, LIGHT_HUE = 0.70, 0.13


def _lerp_hue(h, target, k):
    d = (target - h + 0.5) % 1.0 - 0.5
    return (h + d * k) % 1.0


def shade(c, k):
    """`c` moved k steps darker (k < 0) or lighter (k > 0), with the hue shift
    pixel artists use: shadows cool and saturated, lights warm and soft."""
    return _shade(tuple(c[:3]), k)


@functools.lru_cache(maxsize=8192)
def _shade(c, k):
    r, g, b = [v / 255.0 for v in c]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if k < 0:
        n = -k
        h = _lerp_hue(h, SHADOW_HUE, 0.08 * n) if s > 0.05 else h
        s = min(1.0, s + 0.07 * n + (0.1 * n if s < 0.05 else 0))
        v = max(0.0, v - 0.14 * n)
    elif k > 0:
        h = _lerp_hue(h, LIGHT_HUE, 0.06 * k) if s > 0.05 else h
        s = max(0.0, s - 0.1 * k)
        v = min(1.0, v + 0.11 * k)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def ramp(c, n=2):
    """[darkest .. c .. lightest]: 2n + 1 shades."""
    return [shade(c, k) for k in range(-n, n + 1)]


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Pix:
    """A low-resolution canvas. Coordinates are pixels of the final art."""

    def __init__(self, w, h, seed=0):
        self.w, self.h = int(w), int(h)
        self.s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.rng = random.Random(seed)

    # -- plain brushes
    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.s.set_at((x, y), c)

    def get(self, x, y):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.s.get_at((x, y))
        return None

    def rect(self, x, y, w, h, c):
        if w > 0 and h > 0:
            self.s.fill(c, (int(x), int(y), int(w), int(h)))

    def line(self, a, b, c, width=1):
        pygame.draw.line(self.s, c, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), width)

    def disc(self, cx, cy, r, c):
        pygame.draw.circle(self.s, c, (int(cx), int(cy)), max(1, int(r)))

    def ring(self, cx, cy, r, c, width=1):
        pygame.draw.circle(self.s, c, (int(cx), int(cy)), max(1, int(r)), width)

    def ellipse(self, x, y, w, h, c):
        pygame.draw.ellipse(self.s, c, (int(x), int(y), max(1, int(w)), max(1, int(h))))

    def poly(self, pts, c):
        pygame.draw.polygon(self.s, c, [(int(round(x)), int(round(y))) for x, y in pts])

    def dither(self, x, y, w, h, c, level=2):
        """Sprinkle `c` over a rect in an ordered pattern: level 1 sparse .. 3 dense."""
        pattern = {1: ((0, 0),), 2: ((0, 0), (1, 1)), 3: ((0, 0), (1, 1), (1, 0))}[level]
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                if ((xx % 2, yy % 2) in pattern) and self.get(xx, yy) is not None and self.get(xx, yy)[3]:
                    self.px(xx, yy, c)

    def vgrad(self, x, y, w, h, top, bottom, steps=6):
        """A vertical gradient in flat bands with dithered seams (pixel-art style)."""
        band = max(1, h / steps)
        for i in range(steps):
            c = mix(top, bottom, i / max(1, steps - 1))
            self.rect(x, y + i * band, w, band + 1, c)
            if i:
                prev = mix(top, bottom, (i - 1) / max(1, steps - 1))
                for xx in range(int(x), int(x + w)):
                    if xx % 2 == 0:
                        self.px(xx, y + i * band, prev)

    # -- textured brushes
    def bricks(self, x0, y0, w, h, base, bw=6, bh=3, mask=None, rough=0.25):
        """A wall of bricks: mortar, a lit top edge, a shaded bottom, a few
        darker or lighter bricks. `mask(x, y)` limits where they go."""
        r = ramp(base)
        mortar = r[0]
        for row, y in enumerate(range(int(y0), int(y0 + h), bh + 1)):
            off = (bw // 2 + 1) * (row % 2)
            for x in range(int(x0) - off, int(x0 + w), bw + 1):
                pick = self.rng.random()
                body = r[2] if pick > rough else (r[1] if pick < rough / 2 else r[3])
                for yy in range(y, min(y + bh, int(y0 + h))):
                    for xx in range(max(x, int(x0)), min(x + bw, int(x0 + w))):
                        if mask is None or mask(xx, yy):
                            c = body
                            if yy == y:
                                c = shade(body, 1)
                            elif yy == y + bh - 1:
                                c = shade(body, -1)
                            self.px(xx, yy, c)
                for xx in range(max(x - 1, int(x0)), min(x + bw, int(x0 + w))):
                    yy = y + bh
                    if yy < y0 + h and (mask is None or mask(xx, yy)):
                        self.px(xx, yy, mortar)
                xx = x + bw
                for yy in range(y, min(y + bh, int(y0 + h))):
                    if x0 <= xx < x0 + w and (mask is None or mask(xx, yy)):
                        self.px(xx, yy, mortar)

    def shingles(self, x0, y0, w, h, base, mask=None, size=4):
        """Rows of rounded roof tiles, each with a lit crown and a dark lip."""
        r = ramp(base)
        for row, y in enumerate(range(int(y0), int(y0 + h), size - 1)):
            off = (size // 2) * (row % 2)
            for x in range(int(x0) - off, int(x0 + w), size):
                for dx in range(size):
                    for dy in range(size):
                        xx, yy = x + dx, y + dy
                        if not (x0 <= xx < x0 + w and y0 <= yy < y0 + h):
                            continue
                        if mask is not None and not mask(xx, yy):
                            continue
                        edge = dy == size - 1 or (dy == size - 2 and dx in (0, size - 1))
                        c = r[1] if edge else (r[3] if dy == 0 and 0 < dx < size - 1 else r[2])
                        self.px(xx, yy, c)

    def planks(self, x0, y0, w, h, base, pw=3, mask=None):
        """Vertical wooden planks with grain and the odd knot."""
        r = ramp(base)
        for x in range(int(x0), int(x0 + w)):
            col = (x - int(x0)) % pw
            for y in range(int(y0), int(y0 + h)):
                if mask is not None and not mask(x, y):
                    continue
                c = r[0] if col == pw - 1 else (r[3] if col == 0 else r[2])
                if col == 1 and (y * 7 + x * 3) % 11 == 0:
                    c = r[1]
                self.px(x, y, c)

    def leaves(self, cx, cy, rad, base, fruit=None, n=None):
        """A leafy clump: dark inside, lit on top-left, ragged edge, maybe fruit."""
        r = ramp(base)
        n = n or int(rad * 1.6) + 3
        blobs = []
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(0, rad * 0.7)
            blobs.append((cx + math.cos(a) * d, cy + math.sin(a) * d * 0.8, self.rng.uniform(rad * 0.35, rad * 0.6)))
        for bx, by, br in blobs:
            self.disc(bx, by + 1, br, r[0])
        for bx, by, br in blobs:
            self.disc(bx, by, br, r[1])
        for bx, by, br in blobs:
            self.disc(bx - br * 0.25, by - br * 0.3, br * 0.7, r[2])
        for bx, by, br in blobs:
            if by < cy:
                self.disc(bx - br * 0.35, by - br * 0.45, max(1, br * 0.35), r[3])
        for _ in range(int(rad * 2)):                               # leaf glints
            a = self.rng.uniform(math.pi, math.tau)
            d = self.rng.uniform(rad * 0.3, rad * 0.9)
            self.px(cx + math.cos(a) * d, cy + math.sin(a) * d * 0.8, r[4])
        if fruit:
            for _ in range(max(1, int(rad / 4))):
                a = self.rng.uniform(0, math.tau)
                d = self.rng.uniform(0, rad * 0.7)
                fx, fy = cx + math.cos(a) * d, cy + math.sin(a) * d * 0.7
                c = self.rng.choice(fruit)
                self.rect(fx, fy, 2, 2, c)
                self.px(fx, fy, shade(c, 2))

    def grass(self, x0, y, w, base, tall=3):
        r = ramp(base)
        for x in range(int(x0), int(x0 + w)):
            hgt = self.rng.randint(1, tall)
            for k in range(hgt):
                self.px(x, y - k, r[2] if k < hgt - 1 else r[3])
            if self.rng.random() < 0.08:
                self.px(x, y - hgt - 1, self.rng.choice(((255, 120, 140), (255, 220, 90), (150, 200, 255))))

    # -- finishing
    def outline(self, c=OUTLINE, corners=False):
        """A 1-pixel outline around everything painted so far."""
        mask = pygame.mask.from_surface(self.s, 1)
        sil = mask.to_surface(setcolor=c, unsetcolor=(0, 0, 0, 0))
        out = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        offs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if corners:
            offs += [(1, 1), (-1, 1), (1, -1), (-1, -1)]
        for dx, dy in offs:
            out.blit(sil, (dx, dy))
        out.blit(self.s, (0, 0))
        self.s = out

    def up(self, k):
        return pygame.transform.scale(self.s, (self.w * k, self.h * k))


_CACHE = {}


def cached(key, build):
    """build() once per key (build returns a Surface or anything)."""
    v = _CACHE.get(key)
    if v is None:
        if len(_CACHE) > 4000:
            _CACHE.clear()
        v = _CACHE[key] = build()
    return v


def sprite(rows, pal, k=1):
    """A little hand-drawn sprite: `rows` of characters, `pal` maps a character
    to a colour ('.' and ' ' are clear)."""
    h, w = len(rows), max(len(r) for r in rows)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = pal.get(ch)
            if c is not None:
                s.set_at((x, y), c)
    return pygame.transform.scale(s, (w * k, h * k)) if k != 1 else s


# ------------------------------------------------------------- characters

SIDES = {"triangle": 3, "square": 4, "diamond": 4, "pentagon": 5, "hexagon": 6}
PASTELS = ((255, 132, 150), (255, 214, 120), (130, 228, 160), (120, 222, 244), (140, 160, 255),
           (226, 140, 244))


def critter_points(shape, cx, cy, r, rot=0.0, sx=1.0, sy=1.0):
    """Polygon corners for a shape (None for a circle), matching art.shape_points,
    squashed by sx, sy about the base."""
    if shape == "circle" or shape == 0:
        return None
    n = shape if isinstance(shape, int) else SIDES.get(shape, 4)
    start = {"triangle": -math.pi / 2, "square": -math.pi / 4, "diamond": -math.pi / 2,
             "pentagon": -math.pi / 2, "hexagon": 0.0}.get(shape, -math.pi / 2)
    scale = {"triangle": 1.22, "square": 1.27, "diamond": 1.18, "pentagon": 1.1, "hexagon": 1.06}.get(shape, 1.05)
    dy = r * 0.14 if shape == "triangle" else 0
    pts = [(cx + r * scale * math.cos(start + rot + math.tau * i / n),
            cy + dy + r * scale * math.sin(start + rot + math.tau * i / n)) for i in range(n)]
    if shape == "square":                                   # squares sit flat on the floor
        pts = [(cx + (x - cx) * 0.92, cy + (y - cy) * 0.92) for x, y in pts]
    base = cy + r
    return [(cx + (x - cx) * sx, base + (y - base) * sy) for x, y in pts]


def _body(p, shape, cx, cy, r, col, rot=0.0, sx=1.0, sy=1.0, grow=0.0):
    pts = critter_points(shape, cx, cy, r + grow, rot, sx, sy)
    if pts is None:
        rr = r + grow
        p.ellipse(cx - rr * sx, cy + r - (r + rr) * sy, 2 * rr * sx + 1, 2 * rr * sy + 1, col)
    else:
        p.poly(pts, col)


def critter(shape, color, r, mood="plain", look=(0.0, 0.0), rot=0.0, sx=1.0, sy=1.0, mark=None,
            prism=False, phase=0.0, spin=0.0):
    """A shape with a face, painted at low resolution (radius r pixels): a
    shaded body with a lit rim, a dark outline, a face, and its mark. Returns
    an unscaled Surface, square, with the shape's centre in the middle. Cached."""
    r = max(3, int(round(r)))
    n = math.hypot(*look)
    look = (0, 0) if n < 0.25 else (round(look[0] / max(n, 1)), round(look[1] / max(n, 1)))
    q = math.pi / 8
    rotq = round(rot / q) * q if shape != "circle" else 0.0
    spinq = round(spin / q) % 16 if shape == "circle" else 0
    sxq, syq = round(sx * 10) / 10, round(sy * 10) / 10
    key = ("critter", shape, tuple(color[:3]) if color else None, r, mood, look, round(rotq, 3), sxq, syq,
           mark, prism, int(phase * 6) % 6 if prism else 0, spinq)

    def build():
        size = int(r * 3 + 8)
        c = size // 2
        p = Pix(size, size)
        body = tuple(color[:3]) if color else (250, 250, 255)
        sh = ramp(body)
        # three layers, clipped to the silhouette: shadow side, body, lit crown
        _body(p, shape, c, c, r, sh[1], rotq, sxq, syq)
        sil = pygame.mask.from_surface(p.s, 1).to_surface(setcolor=(255, 255, 255, 255),
                                                          unsetcolor=(0, 0, 0, 0))
        layer = Pix(size, size)
        off = max(1, r * 0.2)
        _body(layer, shape, c - off, c - off, r * 0.86, sh[2], rotq, sxq, syq)
        _body(layer, shape, c - r * 0.42, c - r * 0.45, r * 0.34, sh[3], rotq, sxq, syq)
        layer.s.blit(sil, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if prism:
            layer = Pix(size, size)
            sm = pygame.mask.from_surface(sil, 1)
            for y in range(size):
                for x in range(size):
                    if sm.get_at((x, y)):
                        i = int((x + y * 0.6) / max(2, r * 0.45) + phase * 6) % 6
                        col = mix(PASTELS[i], (255, 255, 255), 0.25)
                        if (x - c) * 0.7 + (y - c) > r * 0.55:
                            col = shade(col, -1)
                        layer.px(x, y, col)
        p.s.blit(layer.s, (0, 0))
        # a crisp lit rim: the top-left edge pixels of the silhouette
        sm = pygame.mask.from_surface(sil, 1)
        rim = shade(body, 2) if not prism else (255, 255, 255)
        for y in range(1, size):
            for x in range(1, size):
                if (x - c) + (y - c) < -r * 0.3 and sm.get_at((x, y)) and (
                        not sm.get_at((x - 1, y)) or not sm.get_at((x, y - 1))):
                    p.px(x, y, rim)
        if mark:
            _mark(p, mark, shape, c, c, r, body, sxq, syq)
        p.outline()
        fx, fy = c, c
        if shape == "triangle":
            fy = c + r * 0.3
        elif shape == "diamond":
            fy = c + r * 0.05
        fy = c + r - (c + r - fy) * syq
        _face(p, fx, fy, r * min(1.0, max(0.7, sxq)), mood, look, spinq * q)
        return p.s
    return cached(key, build)


def _mark(p, mark, shape, cx, cy, r, color, sx, sy):
    """The little details that tell same-shaped Set members apart."""
    ink = OUTLINE
    top = cy + r - 2 * r * sy
    base = cy + r
    if mark == "frame":
        pts = critter_points(shape, cx, cy + r * (1 - sy) * 0.9, r * 0.62, 0.0, sx, sy)
        if pts:
            p.s.lock()
            pygame.draw.lines(p.s, shade(color, -2), True, [(int(x), int(y)) for x, y in pts], 1)
            p.s.unlock()
    elif mark == "seam":
        for k in range(0, int(2 * r * sy), 2):
            p.px(cx - r * 0.8 * sx + k * 0.8 * sx, top + 2 + k * 0.95, ink)
    elif mark == "feet":
        for side in (-1, 1):
            fx = cx + side * r * 0.45
            p.rect(fx - max(1, r * 0.25), base, max(2, r * 0.5), max(1, r * 0.22), shade(color, -2))
    elif mark == "horn":
        t = top - (r * 0.25 if shape == "triangle" else 0)
        hh = max(2, r * 0.5)
        p.poly([(cx - max(1, r * 0.18), t + 1), (cx + max(1, r * 0.18), t + 1), (cx, t - hh)], shade(color, 2))
    elif mark == "sash":
        for k in range(-int(r * 0.7), int(r * 0.7)):
            x = cx + k * sx
            y = cy + k * 0.9
            p.px(x, y, shade(color, 2))
            p.px(x + 1, y, shade(color, 2))
    elif mark == "spring":
        for k in range(4):
            y = base + 1 + k
            p.px(cx + (-1 if k % 2 else 1) * max(1, r * 0.3), y, ink)
            p.px(cx, y, ink)
    elif mark == "sprout":
        p.line((cx, top + 1), (cx + r * 0.12, top - r * 0.4), (60, 140, 70))
        p.poly([(cx + r * 0.12, top - r * 0.4), (cx + r * 0.6, top - r * 0.65), (cx + r * 0.4, top - r * 0.2)],
               (120, 210, 110))


def _face(p, cx, cy, r, mood, look, spin=0.0):
    """Eyes (and a little mouth when happy or surprised), sized to the body."""
    ink = OUTLINE
    gap = max(2.0, r * 0.4)
    ew = max(1, int(round(r * 0.2)))
    lift = r * 0.12 if spin else 0.0
    cs, sn = math.cos(spin), math.sin(spin)
    lx, ly = look
    eyes = []
    for side in (-1, 1):
        dx, dy = side * gap, -lift
        eyes.append((int(round(cx + dx * cs - dy * sn)), int(round(cy + dx * sn + dy * cs))))
    for ex, ey in eyes:
        if mood == "happy":
            for k in range(-ew, ew + 1):
                p.px(ex + k, ey - (ew - abs(k)) * 0.8, ink)
            continue
        if mood in ("sleep", "blink"):
            p.rect(ex - ew, ey, 2 * ew + 1, max(1, ew // 2), ink)
            continue
        if mood == "hurt":
            for k in range(-ew, ew + 1):
                p.px(ex + k, ey + k, ink)
                p.px(ex + k, ey - k, ink)
            continue
        big = ew + (1 if mood == "wow" else 0)
        p.disc(ex, ey, big, (255, 255, 255))
        if big >= 2:
            p.ring(ex, ey, big, ink)
        pr = max(1, big // 2 + (big > 2))
        px_, py_ = ex + lx * max(1, big - pr), ey + ly * max(1, big - pr)
        if pr <= 1:
            p.px(px_, py_, ink)
        else:
            p.disc(px_, py_, pr - 1 if pr > 2 else 1, ink)
            if pr == 2:
                p.rect(px_ - 1, py_ - 1, 2, 2, ink)
        if big >= 3:
            p.px(ex - 1, ey - 1, (255, 255, 255))
        if mood == "cross":                              # brows, sloping down to the middle
            inward = 1 if ex < cx else -1
            for k in range(big + 2):
                p.px(ex - inward * (big + 1) + inward * k, ey - big - 2 + (k * (1 if big < 3 else 2)) // (big + 1), ink)
    if mood == "happy" and r >= 8:
        p.px(cx, cy + max(2, r * 0.25), ink)
        p.px(cx - 1, cy + max(2, r * 0.25) - 1, ink)
        p.px(cx + 1, cy + max(2, r * 0.25) - 1, ink)
        if r >= 9:
            for ex, ey in eyes:                          # rosy cheeks
                p.px(ex + (1 if ex > cx else -1) * ew, ey + ew + 1, (255, 150, 170))
    if mood == "wow" and r >= 8:
        p.disc(cx, cy + max(2, r * 0.32), max(1, r * 0.1), ink)


def shadow(w, h):
    """A soft pixel shadow ellipse (low-res), cached."""
    w, h = max(3, int(w)), max(2, int(h))

    def build():
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (*OUTLINE, 70), s.get_rect())
        pygame.draw.ellipse(s, (*OUTLINE, 40), s.get_rect().inflate(-max(1, w // 4), 0))
        return s
    return cached(("shadow", w, h), build)


def critter_up(k, *args, **kw):
    """critter(...) scaled up k times (cached)."""
    low = critter(*args, **kw)
    if k == 1:
        return low
    return cached(("up", k, id(low)), lambda: pygame.transform.scale(low, (low.get_width() * k, low.get_height() * k)))


def scale_for(r):
    """How big a pixel is, for a character drawn at radius r (screen pixels):
    small ones at 1:1, most at 2x, the big story ones at 3x."""
    if r < 10:
        return 1
    if r < 44:
        return 2
    return 3


def confetti_sprite(shape, size, color, rot):
    """A drifting shape for a backdrop: a soft pixel shape with a lit edge (2x)."""
    q = round(rot / (math.pi / 8)) % 16
    r = max(2, int(size / 2))
    key = ("confetti", shape, r, tuple(color[:3]), q)

    def build():
        n = r * 3 + 4
        p = Pix(n, n)
        c = n / 2
        pts = critter_points(shape, c, c, r, q * math.pi / 8)
        if pts is None:
            p.disc(c, c, r, color)
            p.disc(c - 1, c - 1, max(1, r - 1), shade(color, 1))
        else:
            p.poly(pts, color)
            inner = [(c + (x - c) * 0.6 - 0.5, c + (y - c) * 0.6 - 0.5) for x, y in pts]
            p.poly(inner, shade(color, 1))
        p.outline(shade(color, -2))
        return p.up(2)
    return cached(key, build)


def sky_up(top, bottom, size=(960, 640), k=4):
    """A sky in flat bands with dithered seams, painted small and scaled up."""
    def build():
        w, h = size[0] // k, size[1] // k
        p = Pix(w, h)
        p.vgrad(0, 0, w, h, top, bottom, steps=9)
        return p.up(k)
    return cached(("skyup", tuple(top), tuple(bottom), size, k), build)


def draw_morph(surf, pts, cx, cy, r, t, mood="wow", k=2):
    """A shape in the middle of growing a side (any polygon `pts`, screen
    coordinates), painted as you: prism light inside, outline, and a face."""
    xs = [x for x, _y in pts]
    ys = [y for _x, y in pts]
    x0, y0 = min(xs) - 6, min(ys) - 6
    w, h = int((max(xs) - x0) / k) + 8, int((max(ys) - y0) / k) + 8
    p = Pix(w, h)
    low = [((x - x0) / k, (y - y0) / k) for x, y in pts]
    p.poly(low, (255, 255, 255))
    sm = pygame.mask.from_surface(p.s, 1)
    lc = ((cx - x0) / k, (cy - y0) / k)
    rr = r / k
    for y in range(h):
        for x in range(w):
            if sm.get_at((x, y)):
                i = int((x + y * 0.6) / max(2, rr * 0.45) + t * 3) % 6
                col = mix(PASTELS[i], (255, 255, 255), 0.25)
                if (x - lc[0]) * 0.7 + (y - lc[1]) > rr * 0.55:
                    col = shade(col, -1)
                p.px(x, y, col)
    p.outline()
    _face(p, lc[0], lc[1] + rr * 0.15, rr, mood, (1, 0))
    surf.blit(p.up(k), (int(x0), int(y0)))
