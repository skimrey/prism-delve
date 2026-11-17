"""The towers of the Meadow, painted as pixel art (see pixel.py).

Every tower is painted on a low-res canvas with its base on the bottom row
and its window (where the one who asked waits) exactly WIN_UP pixels above
it, so in the hub (at 4x) every window sits where the hop takes you. Each
painter returns the canvas plus where its window and ground door are. The
moving bits (flags, sails, a lighthouse beam, spores, the friend waving)
are drawn separately each frame by `overlay`.

    tower_sprite(tid, scale, open_door)  -> (Surface, meta)
    draw_tower_art(surf, tid, x, base, scale, t, friend, open_door)
        draws it with its window centred on x and its base on `base`, and
        returns the window's (centre, radius) on screen.
"""

import math

import pygame

from .pixel import OUTLINE, Pix, cached, mix, ramp, shade

WIN_UP = 87                      # window centre, in art pixels above the base
INK = OUTLINE
GLOW = (255, 222, 130)
NIGHT = (42, 36, 72)


def _ground(p, y, x0, x1, green=(96, 186, 80), stones=(150, 140, 160)):
    """A strip of soil, stones and grass tufts along the base."""
    g = ramp(green)
    for x in range(int(x0), int(x1)):
        p.px(x, y, g[1])
        if p.rng.random() < 0.55:
            p.px(x, y - 1, g[2])
        if p.rng.random() < 0.2:
            p.px(x, y - 2, g[3])
    for _ in range(int((x1 - x0) / 8)):
        sx = p.rng.randint(int(x0), int(x1) - 3)
        s = ramp(stones)
        p.rect(sx, y - 1, 3, 2, s[2])
        p.px(sx, y - 1, s[3])
        p.px(sx + 2, y, s[1])


def _round_window(p, cx, cy, r, frame, inner=NIGHT):
    f = ramp(frame)
    p.disc(cx, cy, r + 2, f[1])
    p.disc(cx, cy, r + 1, f[3])
    p.disc(cx - 0.5, cy - 0.5, r + 1, f[2])
    p.disc(cx, cy, r, inner)
    p.disc(cx, cy + 1, r - 1, shade(inner, -1))
    p.px(cx - r + 2, cy - r + 3, shade(inner, 3))
    p.px(cx - r + 3, cy - r + 2, shade(inner, 3))


LIGHT_IN = ((255, 246, 210), (255, 222, 150), (240, 180, 110))


def _doorway(p, cx, base, w, h):
    """An open doorway with sunshine pouring through from the other side."""
    x0 = int(cx - w / 2)
    top = base - h
    p.rect(x0, top + w // 2, w, h - w // 2 + 1, LIGHT_IN[2])
    p.disc(cx, top + w // 2, w // 2, LIGHT_IN[2])
    p.rect(x0 + 2, top + w // 2, w - 4, h - w // 2 + 1, LIGHT_IN[1])
    p.disc(cx, top + w // 2 + 1, w // 2 - 2, LIGHT_IN[1])
    p.rect(x0 + 3, top + w // 2 + 2, w - 6, h - w // 2 - 1, LIGHT_IN[0])
    for k in range(4):                                       # light spilling onto the ground
        p.rect(x0 - k, base - k // 2, w + 2 * k, 1, mix(LIGHT_IN[1], (120, 200, 110), 0.4 + 0.15 * k))


def _arch_door(p, cx, base, w, h, wood, open_door):
    """A round-topped door at the foot of a tower. Open, it glows."""
    x0 = int(cx - w / 2)
    top = base - h
    dr = ramp(wood)
    frame = shade(wood, -2)
    p.rect(x0 - 1, top + w // 2, w + 2, h - w // 2 + 1, frame)
    p.disc(cx, top + w // 2, w // 2 + 1, frame)
    if open_door:
        _doorway(p, cx, base, w, h)
        return
    p.rect(x0, top + w // 2, w, h - w // 2, dr[2])
    p.disc(cx, top + w // 2, w // 2, dr[2])
    for x in range(x0 + 2, x0 + w, 3):
        p.line((x, top + 2), (x, base - 1), dr[1])
    p.line((x0, base - h // 3), (x0 + w - 1, base - h // 3), dr[0])
    p.line((x0, base - 2 * h // 3), (x0 + w - 1, base - 2 * h // 3), dr[0])
    p.px(x0 + w - 3, base - h // 2, GLOW)


# ------------------------------------------------------------------ towers

def _leaning(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    lean = 0.11
    top = 34

    def x0(y):
        return 22 + (base - y) * lean

    def width(y):
        return 30 - (base - y) * 0.05

    def inside(x, y):
        return top <= y <= base and x0(y) <= x < x0(y) + width(y)
    stone = (138, 162, 214)
    p.bricks(0, top, W, base - top + 1, stone, bw=5, bh=3, mask=inside)
    s = ramp(stone)
    for y in range(top, base + 1):                          # lit left edge, shadowed right
        a, w = x0(y), width(y)
        for k in range(2):
            p.px(a + k, y, shade(p.get(a + k, y)[:3], 1))
        for k in range(5):
            c = p.get(a + w - 1 - k, y)
            if c and c[3]:
                p.px(a + w - 1 - k, y, shade(c[:3], -1 if k > 1 else -2))
    for ly in (64, 90, 116):                                 # floor ledges
        a, w = x0(ly), width(ly)
        p.rect(a - 1, ly, w + 2, 1, s[4])
        p.rect(a - 1, ly + 1, w + 2, 1, s[1])
    for wx, wy in ((8, 102), (19, 78), (7, 128)):            # little lit windows
        a = x0(wy) + wx
        p.rect(a - 1, wy - 3, 5, 7, INK)
        p.rect(a, wy - 2, 3, 5, GLOW)
        p.px(a + 1, wy - 3, INK)
        p.px(a, wy - 2, (255, 246, 200))
    # ivy, creeping up the lit side
    g = ramp((80, 170, 90))
    x, y = x0(base) + 2, base - 2
    for _ in range(70):
        p.px(x, y, g[1])
        if p.rng.random() < 0.5:
            p.px(x + p.rng.choice((-1, 1)), y, g[3])
        y -= 1
        x = max(x0(y) - 1, min(x0(y) + 8, x + p.rng.choice((-1, 0, 0, 1))))
        if y < 70:
            break
    # the round window, on a little balcony
    wy = base - WIN_UP
    wcx = int(x0(wy) + width(wy) / 2)
    p.rect(wcx - 8, wy + 10, 17, 2, s[4])
    p.rect(wcx - 8, wy + 12, 17, 1, s[0])
    for k in range(-7, 8, 3):
        p.px(wcx + k, wy + 9, s[1])
    _round_window(p, wcx, wy, 8, (230, 214, 190))
    # the roof: a cone of tiles, a gold knob, a pole
    a, w = x0(top), width(top)
    apex = (a + w / 2 + 3, 8)
    roof = [(a - 4, top + 1), (a + w + 4, top + 1), apex]
    tmp = Pix(W, H)
    tmp.poly(roof, (255, 255, 255))
    rmask = pygame.mask.from_surface(tmp.s)
    p.shingles(0, 6, W, top - 4, (236, 140, 104), mask=lambda xx, yy: rmask.get_at((xx, yy)))
    p.rect(a - 5, top, w + 10, 2, shade((236, 140, 104), -2))
    p.line((apex[0], apex[1]), (apex[0], apex[1] - 7), INK)
    p.disc(apex[0], apex[1], 2, (250, 210, 90))
    p.px(apex[0] - 1, apex[1] - 1, (255, 250, 200))
    _arch_door(p, int(x0(base) + width(base) / 2), base - 1, 10, 15, (150, 96, 60), open_door)
    _ground(p, base, 6, W - 6)
    return {"win": (wcx, wy), "win_r": 8, "flag": (apex[0], apex[1] - 7)}


def _hollow(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    bark = (132, 88, 52)
    b = ramp(bark)

    def cx(y):
        return 55 + math.sin((base - y) * 0.045) * 3

    def half(y):
        return 12 + max(0, (y - 100)) * 0.25 + max(0, 40 - y) * 0.1

    # roots
    for side in (-1, 1):
        for k in range(3):
            rx = cx(base) + side * (8 + k * 5)
            pts = [(rx, base - 14 + k * 4), (rx + side * (16 + k * 8), base), (rx - side * 5, base)]
            p.poly(pts, b[2 - (k % 2)])
            p.line(pts[0], pts[1], b[3] if side < 0 else b[1])
    for y in range(26, base):
        c, h = cx(y), half(y)
        for x in range(int(c - h), int(c + h) + 1):
            u = (x - (c - h)) / (2 * h)
            grain = math.sin(x * 1.3 + math.sin(y * 0.15 + x) * 2)
            col = b[2]
            if u < 0.18:
                col = b[3]
            elif u > 0.78:
                col = b[1] if u < 0.9 else b[0]
            if grain > 0.75:
                col = shade(col, -1)
            p.px(x, y, col)
    for kx, ky in ((-5, 112), (6, 92), (-6, 74)):            # knots
        p.ellipse(cx(ky) + kx - 2, ky - 3, 5, 6, b[0])
        p.px(cx(ky) + kx, ky - 1, b[3])
    g = (96, 190, 90)
    for _ in range(16):                                     # moss near the foot
        p.px(cx(base) + p.rng.randint(-13, 13), base - p.rng.randint(2, 24), shade(g, p.rng.choice((0, 1))))
    # the canopy: clumps of every green, with fruit
    fruit = ((255, 96, 120), (255, 214, 80), (120, 180, 255), (230, 120, 240), (255, 150, 70))
    greens = ((72, 172, 84), (96, 196, 92), (52, 150, 104), (124, 208, 96))
    clumps = ((55, 18, 20), (30, 26, 15), (80, 26, 15), (44, 8, 13), (68, 8, 13), (18, 34, 11),
              (92, 36, 11), (55, 34, 14))
    for i, (lx, ly, lr) in enumerate(clumps):
        p.leaves(lx, ly, lr, greens[i % 4], fruit=fruit)
    for vx in (24, 40, 71, 88):                              # vines
        ln = p.rng.randint(10, 22)
        for k in range(ln):
            p.px(vx + int(math.sin(k * 0.5) * 1), 36 + k, (52, 130, 70))
            if k % 3 == 0:
                p.px(vx + 1, 36 + k, (110, 210, 100))
    # the big knothole
    wy = base - WIN_UP
    wcx = int(cx(wy))
    p.ellipse(wcx - 11, wy - 11, 23, 23, b[0])
    p.ellipse(wcx - 10, wy - 10, 21, 21, b[3])
    p.ellipse(wcx - 9, wy - 9, 19, 19, b[1])
    p.disc(wcx, wy, 8, (36, 22, 26))
    p.disc(wcx, wy + 1, 6, (26, 16, 22))
    # mushrooms on the roots
    for mx, my in ((cx(base) - 22, base - 3), (cx(base) + 25, base - 2), (cx(base) - 14, base - 6)):
        p.rect(mx, my, 2, 3, (240, 230, 210))
        p.rect(mx - 2, my - 2, 6, 2, (230, 70, 80))
        p.px(mx - 1, my - 2, (255, 255, 255))
    if open_door:
        p.ellipse(cx(base) - 7, base - 18, 14, 20, b[0])
        _doorway(p, int(cx(base)), base - 1, 11, 16)
    _ground(p, base, 4, W - 4, green=(70, 160, 80))
    return {"win": (wcx, wy), "win_r": 8}


def _toadstool(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    stem = (240, 226, 196)
    st = ramp(stem)
    wy = base - WIN_UP

    def half(y):
        return 13 + 2 * math.sin((base - y) * 0.04) + max(0, y - 120) * 0.4

    for y in range(34, base + 1):
        h = half(y)
        for x in range(int(55 - h), int(55 + h) + 1):
            u = (x - (55 - h)) / (2 * h)
            col = st[3] if u < 0.2 else (st[2] if u < 0.7 else (st[1] if u < 0.88 else st[0]))
            if (y * 3 + x * 7) % 29 == 0 and 0.2 < u < 0.7:
                col = st[1]
            p.px(x, y, col)
    # shelf caps climbing the stem (little steps)
    for sx, sy, col, side in ((40, 112, (255, 170, 80), -1), (70, 96, (250, 210, 90), 1),
                              (41, 72, (240, 120, 160), -1)):
        r = ramp(col)
        p.ellipse(sx - 8 + side * 2, sy - 3, 16, 6, r[1])
        p.ellipse(sx - 8 + side * 2, sy - 4, 16, 5, r[2])
        p.px(sx - 4 + side * 2, sy - 3, r[4])
        p.px(sx - 3 + side * 2, sy - 3, r[4])
    # the cap: a big red dome with white spots, gills underneath
    cap = (226, 64, 84)
    c = ramp(cap)
    for y in range(4, 38):
        f = (y - 4) / 34
        h = 46 * math.sqrt(max(0.0, 1 - (1 - f) ** 2 * 0.95))
        for x in range(int(55 - h), int(55 + h) + 1):
            u = (x - (55 - h)) / max(1, 2 * h)
            col = c[3] if (u < 0.25 and f < 0.6) else (c[2] if u < 0.72 else c[1])
            if f > 0.85:
                col = c[1] if u < 0.8 else c[0]
            p.px(x, y, col)
    for sx, sy, sr in ((36, 16, 5), (60, 10, 4), (77, 22, 5), (48, 28, 3), (22, 30, 3), (88, 32, 3), (64, 26, 3)):
        p.disc(sx, sy, sr, (250, 244, 236))
        p.disc(sx + 1, sy + 1, max(1, sr - 1), (222, 214, 220))
        p.disc(sx - 0.5, sy - 0.5, max(1, sr - 1), (255, 255, 255))
    for x in range(14, 97, 3):                                # gills
        p.line((x, 38), (55 + (x - 55) * 0.6, 42), shade(stem, -2))
    p.rect(12, 37, 87, 1, c[0])
    # the window, round, in the stem
    _round_window(p, 55, wy, 8, (190, 130, 80))
    p.rect(45, wy + 10, 21, 2, (170, 110, 70))
    # a lantern by the door
    p.rect(66, base - 16, 3, 4, GLOW)
    p.px(67, base - 17, INK)
    _arch_door(p, 55, base - 1, 10, 15, (180, 120, 70), open_door)
    for mx, my, col in ((20, base - 1, (120, 170, 255)), (92, base - 1, (250, 200, 90)), (100, base - 1, (230, 120, 240))):
        p.rect(mx, my - 3, 2, 3, st[3])
        p.ellipse(mx - 2, my - 6, 6, 4, col)
        p.px(mx - 1, my - 5, shade(col, 2))
    _ground(p, base, 4, W - 4, green=(110, 190, 90))
    return {"win": (55, wy), "win_r": 8}


def _icicle(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    ice = (168, 216, 244)
    r = ramp(ice)
    wy = base - WIN_UP

    def half(y):
        return max(3.0, 17 - (base - y) * 0.115)

    tip = 6
    for y in range(tip, base + 1):
        h = half(y) if y > 26 else max(0.5, (y - tip) * 0.16)
        for x in range(int(40 - h), int(40 + h) + 1):
            u = (x - (40 - h)) / max(1, 2 * h)
            block = ((y // 6) + (x // 8 if (y // 6) % 2 else (x + 4) // 8)) % 3
            col = r[2] if block else r[3]
            if u < 0.22:
                col = r[4]
            elif u > 0.75:
                col = r[1]
            if y % 6 == 0:
                col = shade(col, -1)
            if (x * 3 + y * 5) % 23 == 0 and 0.2 < u < 0.6:
                col = (255, 255, 255)
            p.px(x, y, col)
    # snowy ledges with icicles hanging off them
    for ly in (48, 70, 96, 120):
        h = half(ly) + 3
        p.rect(40 - h, ly - 2, 2 * h + 1, 3, (250, 252, 255))
        p.rect(40 - h, ly + 1, 2 * h + 1, 1, (200, 220, 240))
        for x in range(int(40 - h), int(40 + h), 3):
            ln = p.rng.randint(2, 6)
            for k in range(ln):
                p.px(x + (1 if k == ln - 1 else 0) * 0, ly + 2 + k, r[3] if k < ln - 1 else (255, 255, 255))
    # the crystal on the tip
    p.poly([(40, 0), (43, 5), (40, 9), (37, 5)], (230, 250, 255))
    p.px(39, 3, (255, 255, 255))
    _round_window(p, 40, wy, 8, (240, 248, 255), inner=(46, 70, 120))
    for k in range(5):                                       # frost on the glass
        p.px(40 - 5 + k * 2, wy + 5 - (k % 2), (170, 210, 240))
    _arch_door(p, 40, base - 1, 10, 14, (90, 130, 200), open_door)
    snow = (246, 250, 255)
    for x in range(2, W - 2):
        hgt = 3 + int(2 * math.sin(x * 0.3)) + (4 if abs(x - 40) < 18 else 0)
        p.rect(x, base - hgt + 1, 1, hgt, snow)
        p.px(x, base - hgt + 1, (255, 255, 255))
    for _ in range(10):
        p.px(p.rng.randint(2, W - 3), base - p.rng.randint(0, 3), (190, 215, 245))
    return {"win": (40, wy), "win_r": 8}


def _sundial(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    sand = (232, 192, 128)
    s = ramp(sand)
    wy = base - WIN_UP
    tiers = ((base - 30, base, 36), (base - 62, base - 30, 29), (wy - 26, base - 62, 22), (wy - 34, wy - 26, 26))
    for top, bottom, half in tiers:
        p.bricks(55 - half, top, half * 2 + 1, bottom - top, sand, bw=7, bh=4, rough=0.15)
        for y in range(top, bottom):
            for k in range(3):
                cc = p.get(55 + half - k, y)
                if cc and cc[3]:
                    p.px(55 + half - k, y, shade(cc[:3], -1))
            p.px(55 - half, y, shade(p.get(55 - half, y)[:3], 1))
        p.rect(55 - half - 1, top, half * 2 + 3, 2, s[4])
        p.rect(55 - half - 1, top + 2, half * 2 + 3, 1, s[1])
        # a band of turquoise tiles, for colour
        for x in range(55 - half + 2, 55 + half - 1, 4):
            p.rect(x, top + 5, 2, 2, (64, 200, 200))
            p.px(x, top + 5, (160, 240, 230))
    # banners hanging from the second tier
    for bx, col in ((30, (220, 70, 90)), (78, (80, 110, 220))):
        for k in range(14):
            w = 5 if k < 12 else (3 if k == 12 else 1)
            p.rect(bx - w // 2, base - 60 + k, w, 1, shade(col, 1 if k < 2 else 0))
        p.px(bx, base - 55, (255, 220, 120))
    # the dial, with its pointer's spot in the middle (that's the window)
    p.disc(55, wy, 11, s[0])
    p.disc(55, wy, 10, (250, 236, 200))
    p.disc(55, wy, 8, (242, 222, 176))
    for k in range(12):
        a = k * math.tau / 12
        p.px(55 + math.cos(a) * 9, wy + math.sin(a) * 9, s[0])
    p.disc(55, wy, 5, NIGHT)
    # a shadow line across the dial, the time of day
    p.line((55, wy), (55 + 8, wy + 5), (200, 170, 120))
    # palms
    for px_, lean in ((10, 1), (100, -1)):
        for k in range(26):
            p.px(px_ + int(lean * k * 0.12), base - k, (150, 100, 60) if k % 3 else (120, 80, 50))
        tx, ty = px_ + int(lean * 3), base - 26
        for a in (-2.6, -2.0, -1.3, -0.6, -0.2, 0.3):
            for k in range(9):
                p.px(tx + math.cos(a) * k, ty + math.sin(a) * k + k * k * 0.05, (70, 170, 90) if k < 7 else (120, 210, 110))
    _arch_door(p, 55, base - 1, 12, 16, (110, 70, 50), open_door)
    for x in range(2, W - 2):                                  # dunes at the foot
        hgt = 2 + int(2 * math.sin(x * 0.12) + 1)
        p.rect(x, base - hgt + 1, 1, hgt, (240, 210, 150))
        p.px(x, base - hgt + 1, (250, 232, 180))
    return {"win": (55, wy), "win_r": 5}


def _lens(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    wy = base - WIN_UP

    def column(cx, top, half, col, lit=True):
        r = ramp(col)
        for y in range(top - half, base):
            if y < top:
                h = (y - (top - half)) * 1.0
            else:
                h = half
            for x in range(int(cx - h), int(cx + h) + 1):
                u = (x - (cx - h)) / max(1, 2 * h)
                c = r[3] if u < 0.34 else (r[2] if u < 0.67 else r[1])
                if y < top and u > 0.5:
                    c = r[1]
                if (x + y) % 13 == 0 and u < 0.34:
                    c = r[4]
                p.px(x, y, c)
            if y >= top:
                p.px(cx - h + int(2 * h * 0.34), y, r[4] if lit else r[3])
    column(24, 90, 9, (150, 120, 240))
    column(86, 80, 10, (110, 206, 236))
    column(70, 58, 8, (250, 140, 200))
    column(38, 68, 8, (120, 230, 190))
    column(55, 26, 15, (196, 170, 255))
    for y in range(30, base - 6):                              # the glowing core
        p.px(53, y, (255, 246, 255))
        if y % 4 == 0:
            p.px(54, y, (230, 220, 255))
    # the lens: a round pane that breaks light into colour
    p.disc(55, wy, 10, (230, 230, 240))
    p.disc(55, wy, 9, (170, 170, 200))
    bands = ((255, 120, 140), (255, 214, 110), (120, 226, 150), (110, 220, 240), (130, 150, 255), (220, 130, 240))
    for y in range(wy - 8, wy + 9):
        for x in range(55 - 8, 56 + 8):
            if (x - 55) ** 2 + (y - wy) ** 2 <= 64:
                p.px(x, y, mix(bands[((x + y) // 3) % 6], NIGHT, 0.55))
    p.disc(55, wy, 4, NIGHT)
    p.px(51, wy - 6, (255, 255, 255))
    # rock at the foot, sprinkled with little crystals
    rock = ramp((110, 100, 140))
    for x in range(4, W - 4):
        hgt = 4 + int(3 * abs(math.sin(x * 0.21)))
        for k in range(hgt):
            p.px(x, base - k, rock[2] if k < hgt - 1 else rock[3])
    for cxs, col in ((12, (250, 140, 200)), (97, (110, 206, 236)), (44, (255, 220, 120))):
        p.poly([(cxs - 2, base - 4), (cxs, base - 10), (cxs + 2, base - 4)], col)
        p.px(cxs - 1, base - 7, (255, 255, 255))
    if open_door:
        p.poly([(49, base), (55, base - 19), (61, base)], LIGHT_IN[2])
        p.poly([(51, base), (55, base - 15), (59, base)], LIGHT_IN[1])
        p.poly([(53, base), (55, base - 10), (57, base)], LIGHT_IN[0])
    else:
        p.poly([(51, base), (55, base - 16), (59, base)], NIGHT)
        p.px(55, base - 10, (200, 180, 255))
    return {"win": (55, wy), "win_r": 8}


def _lighthouse(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    wy = base - WIN_UP
    top = 30

    def half(y):
        return 10 + (y - top) * 0.055

    red, white = (226, 70, 72), (246, 240, 232)
    for y in range(top, base - 3):
        h = half(y)
        band = ((y - top) // 12) % 2
        col = red if band == 0 else white
        r = ramp(col)
        for x in range(int(40 - h), int(40 + h) + 1):
            u = (x - (40 - h)) / (2 * h)
            k = math.cos((u - 0.32) * math.pi)
            c = r[3] if k > 0.92 else (r[2] if k > 0.35 else (r[1] if k > -0.2 else r[0]))
            p.px(x, y, c)
    # the gallery and lantern room
    p.rect(26, top - 1, 29, 2, (60, 60, 80))
    for x in range(27, 54, 3):
        p.rect(x, top - 5, 1, 4, (60, 60, 80))
    p.rect(26, top - 6, 29, 1, (60, 60, 80))
    p.rect(32, 14, 17, top - 15, (80, 80, 100))
    p.rect(33, 15, 15, top - 17, GLOW)
    p.rect(33, 15, 4, top - 17, (255, 246, 200))
    for x in (37, 42):
        p.rect(x, 15, 1, top - 17, (80, 80, 100))
    p.poly([(30, 14), (51, 14), (40, 4)], red)
    p.poly([(31, 13), (40, 5), (40, 13)], shade(red, 1))
    p.disc(40, 4, 1, (250, 210, 90))
    # a porthole (that's the window)
    _round_window(p, 40, wy, 7, (214, 170, 90), inner=(40, 60, 110))
    # rocks and surf at the foot
    rk = ramp((120, 116, 140))
    for cxr, w, h in ((14, 16, 8), (64, 20, 10), (40, 30, 6), (28, 12, 5)):
        p.ellipse(cxr - w / 2, base - h, w, h + 2, rk[2])
        p.ellipse(cxr - w / 2 + 1, base - h, w - 4, 3, rk[3])
    for x in range(0, W):
        wave = int(1.5 + math.sin(x * 0.5) * 1.5)
        p.rect(x, base - wave, 1, wave + 1, (90, 170, 230))
        if math.sin(x * 0.5) > 0.6:
            p.px(x, base - wave, (240, 250, 255))
    _arch_door(p, 40, base - 4, 9, 12, (90, 110, 170), open_door)
    return {"win": (40, wy), "win_r": 7, "lamp": (40, 22)}


def _windmill(p, open_door):
    W, H = p.w, p.h
    base = H - 1
    wy = base - WIN_UP
    top = 26

    def half(y):
        return 11 + (y - top) * 0.1

    plaster = ramp((244, 236, 222))
    for y in range(top, base + 1):
        h = half(y)
        for x in range(int(60 - h), int(60 + h) + 1):
            u = (x - (60 - h)) / (2 * h)
            c = plaster[3] if u < 0.2 else (plaster[2] if u < 0.7 else plaster[1])
            p.px(x, y, c)
    wood = ramp((150, 100, 64))
    for y in range(top, base + 1, 22):                          # timber frame
        h = half(y)
        p.rect(60 - h, y, 2 * h + 1, 2, wood[1])
    for y in range(top, base):
        h = half(y)
        p.px(60 - h, y, wood[2])
        p.px(60 + h, y, wood[0])
    for y0 in range(top, base - 22, 22):                         # cross braces between the beams
        for k in range(22):
            y = y0 + 2 + k
            if y > base - 15:
                break
            h = half(y) - 2
            u = k / 21
            p.px(60 - h + 2 * h * u, y, wood[1])
            p.px(60 + h - 2 * h * u, y, wood[1])
    # the cap
    p.poly([(46, top + 1), (74, top + 1), (70, top - 10), (50, top - 10)], (90, 90, 120))
    p.shingles(46, top - 10, 29, 11, (96, 96, 130),
               mask=lambda xx, yy: 46 + (top + 1 - yy) * 0.4 <= xx <= 74 - (top + 1 - yy) * 0.4)
    p.rect(58, top - 14, 4, 4, (90, 90, 120))
    # the window, with shutters
    _round_window(p, 60, wy, 7, (150, 100, 64), inner=(44, 60, 100))
    p.rect(49, wy - 6, 3, 12, (120, 170, 220))
    p.rect(69, wy - 6, 3, 12, (120, 170, 220))
    # flowers in a box under it
    p.rect(52, wy + 9, 17, 3, wood[2])
    for k, col in enumerate(((255, 110, 140), (255, 220, 90), (140, 170, 255), (255, 150, 80), (230, 120, 240))):
        p.px(53 + k * 3, wy + 8, col)
        p.px(54 + k * 3, wy + 7, col)
    # a stone base, and a hill of grass
    p.bricks(42, base - 14, 37, 14, (170, 164, 180), bw=5, bh=3)
    _arch_door(p, 60, base - 1, 10, 14, (150, 100, 64), open_door)
    for x in range(0, W):
        hgt = 2 + int(2 * math.sin(x * 0.09))
        p.rect(x, base - hgt, 1, hgt + 1, (110, 196, 96))
        p.px(x, base - hgt, (150, 220, 120))
    return {"win": (60, wy), "win_r": 7, "hub": (60, top - 12)}


PAINTERS = {
    "leaning": (_leaning, 76, 142),
    "hollow": (_hollow, 110, 142),
    "toadstool": (_toadstool, 110, 142),
    "icicle": (_icicle, 80, 142),
    "sundial": (_sundial, 110, 142),
    "lens": (_lens, 110, 142),
    "lighthouse": (_lighthouse, 80, 142),
    "windmill": (_windmill, 120, 142),
}


def tower_canvas(tid, open_door=False):
    """(low-res Surface, meta) for a tower, painted once."""
    def build():
        painter, w, h = PAINTERS[tid]
        p = Pix(w, h, seed=len(tid) * 7 + 3)
        meta = painter(p, open_door)
        p.outline()
        meta["size"] = (w, h)
        return p.s, meta
    return cached(("tower", tid, open_door), build)


def tower_sprite(tid, scale=4, open_door=False):
    """(Surface at `scale`, meta in low-res pixels)."""
    canvas, meta = tower_canvas(tid, open_door)
    surf = cached(("tower_up", tid, open_door, scale),
                  lambda: pygame.transform.scale(canvas, (canvas.get_width() * scale, canvas.get_height() * scale)))
    return surf, meta


def draw_tower_art(surf, tid, win_x, base, scale, t, friend=None, open_door=False):
    """Draw a tower with its window centred on x = win_x and its base row on
    y = base. `friend` is (shape, colour) to show at the window, waving.
    Returns ((window x, window y), window radius) on screen."""
    img, meta = tower_sprite(tid, scale, open_door)
    wx, wy = meta["win"]
    w, h = meta["size"]
    left = win_x - (wx + 0.5) * scale
    top = base - h * scale
    surf.blit(img, (int(left), int(top)))
    win = (int(left + (wx + 0.5) * scale), int(top + (wy + 0.5) * scale))
    overlay(surf, tid, meta, left, top, scale, t)
    if friend is not None:                       # who asked, waving: smooth, like every character
        from .art import draw_critter
        shape, color = friend
        rr = max(6, (meta["win_r"] - 3) * scale)
        wave = math.sin(t * 6)
        draw_critter(surf, shape, win[0], win[1] + scale, rr, color, look=(-0.6, 0.5), mood="happy",
                     rot=wave * 0.08, shadow=False, width=2)
        arm = (win[0] + rr + 2, win[1] - 2)
        pygame.draw.line(surf, INK, arm, (arm[0] + rr * 0.6, arm[1] - rr * 0.7 + wave * rr * 0.4), max(2, scale))
    return win, meta["win_r"] * scale


def overlay(surf, tid, meta, left, top, k, t):
    """The moving parts: pennants, sails, a beam, spores, snow glints."""
    if tid == "leaning":
        fx, fy = meta["flag"]
        wave = int(t * 5) % 3
        for i in range(7):
            dy = (0, 1, 0)[(i + wave) % 3] if i > 1 else 0
            h = max(1, 4 - i // 2)
            pygame.draw.rect(surf, (232, 70, 90) if i < 6 else (200, 50, 70),
                             (left + (fx + 1 + i) * k, top + (fy + dy) * k, k, h * k))
    elif tid == "windmill":
        hx, hy = meta["hub"]
        cx, cy = left + (hx + 0.5) * k, top + (hy + 0.5) * k
        a0 = t * 0.9
        step = int(a0 * 16) / 16                             # turn in little clicks: pixel-ish
        for i in range(4):
            a = step + i * math.pi / 2
            for s in range(3, 27):
                for w in range(-2, 3):
                    x = cx + math.cos(a) * s * k - math.sin(a) * w * k
                    y = cy + math.sin(a) * s * k + math.cos(a) * w * k
                    lattice = (s % 4 == 0) or abs(w) == 2
                    col = (120, 84, 56) if lattice else (250, 246, 236)
                    if w == 0 and s < 6:
                        col = (120, 84, 56)
                    pygame.draw.rect(surf, col, (int(x), int(y), k, k))
        pygame.draw.circle(surf, (90, 90, 120), (int(cx), int(cy)), 2 * k)
    elif tid == "lighthouse":
        lx, ly = meta["lamp"]
        cx, cy = left + lx * k, top + ly * k
        a = math.sin(t * 1.3) * 0.9
        beam = pygame.Surface((900, 900), pygame.SRCALPHA)
        for side in (-1, 1):
            d = side
            far = 420
            pts = [(450, 450), (450 + d * far * math.cos(a * d), 450 - far * 0.12 - 60 * math.sin(a)),
                   (450 + d * far * math.cos(a * d), 450 + far * 0.12 - 60 * math.sin(a))]
            pygame.draw.polygon(beam, (255, 240, 170, 46), pts)
        surf.blit(beam, (cx - 450, cy - 450))
    elif tid == "toadstool":
        for i in range(9):
            ph = t * 0.4 + i * 0.37
            y = top + (110 - (ph % 1.0) * 100) * k
            x = left + (20 + i * 9 + math.sin(ph * 5) * 3) * k
            glow = (255, 250, 200) if i % 2 else (200, 255, 220)
            pygame.draw.rect(surf, glow, (int(x), int(y), k, k))
    elif tid == "icicle" or tid == "lens":
        for i in range(6):
            ph = (t * 1.5 + i * 0.71) % 3.0
            if ph < 0.5:
                x = left + (20 + (i * 37) % 60) * k
                y = top + (30 + (i * 53) % 90) * k
                c = (255, 255, 255)
                pygame.draw.rect(surf, c, (int(x), int(y), k, k))
                pygame.draw.rect(surf, c, (int(x - k), int(y), 3 * k, k // 2 + 1))
                pygame.draw.rect(surf, c, (int(x), int(y - k), k // 2 + 1, 3 * k))
