"""Composed scenery shared by several screens: backdrops, the Sorter tower,
map icons, the glint icon and the polygon morph used when you grow a side."""

import math

import pygame

from .art import (Confetti, draw_body, draw_critter, draw_door, draw_eyes, draw_player, draw_poly,
                  draw_shadow, lighten, mix, shape_points)
from .consts import COLOR_RGB, COLORS, FLOORS, FORMS, RAINBOW, RELICS
from .enemies import BOSS_FOR_ACT, KINDS
from .rules import pattern_offsets
from .widgets import INK, PAPER, WHITE, draw_colour_mark, draw_text, font

SCREEN = (960, 640)
TITLE_SKY = ((104, 78, 236), (255, 124, 150))
MEADOW_SKY = ((112, 196, 255), (214, 244, 255))
GRASS = (104, 206, 96)


def floor_style(act):
    return FLOORS[max(1, min(act, len(FLOORS)))]


class Backdrop:
    """Gradient sky plus drifting confetti. One per screen."""

    def __init__(self, sky, seed=3, n=22, soft=0.45):
        self.sky = sky
        self.confetti = Confetti((0, 0, *SCREEN), n=n, seed=seed, soft=soft)

    @classmethod
    def for_act(cls, act, **kw):
        return cls(floor_style(act)["sky"], seed=act * 11, **kw)

    @classmethod
    def for_run(cls, run, **kw):
        """The sky of wherever the run is: a Sorter floor, or another tower."""
        return cls(run.place()["sky"], seed=run.act * 11 + (7 if run.tower else 0), **kw)

    def update(self, dt):
        self.confetti.update(dt)

    def draw(self, surf):
        from .pixel import sky_up
        surf.blit(sky_up(self.sky[0], self.sky[1]), (0, 0))
        self.confetti.draw(surf)


def heading(surf, text, pos, size=44, center=False):
    """Big white title with an ink drop shadow (for text on colour)."""
    return draw_text(surf, font(size), text, pos, WHITE, center=center, shadow=INK)


def glint_icon(surf, cx, cy, r=7):
    """A four-pointed sparkle: the currency."""
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.4
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    draw_poly(surf, pts, (255, 226, 92), INK, 2)


def heart_icon(surf, cx, cy, r=7):
    pygame.draw.circle(surf, (255, 84, 110), (int(cx - r * 0.45), int(cy - r * 0.2)), int(r * 0.55))
    pygame.draw.circle(surf, (255, 84, 110), (int(cx + r * 0.45), int(cy - r * 0.2)), int(r * 0.55))
    pygame.draw.polygon(surf, (255, 84, 110), [(cx - r * 0.95, cy), (cx + r * 0.95, cy),
                                               (cx, cy + r * 0.95)])


def stat_chip(surf, x, y, icon, text, fill=PAPER):
    """A small pill: icon + text. Returns its right edge."""
    f = font(22)
    w = f.size(text)[0] + 40
    r = pygame.Rect(x, y, w, 30)
    pygame.draw.rect(surf, INK, r.move(0, 3), border_radius=15)
    pygame.draw.rect(surf, fill, r, border_radius=15)
    pygame.draw.rect(surf, INK, r, 2, border_radius=15)
    icon(surf, x + 16, y + 15)
    draw_text(surf, f, text, (x + 30, y + 8), INK)
    return r.right


def keeper_kind(act):
    return BOSS_FOR_ACT[max(1, min(act, len(BOSS_FOR_ACT)))]


def keeper_shape(act):
    return KINDS[keeper_kind(act)]["shape"]


def cycling_color(t, speed=0.7, offset=0):
    k = t * speed + offset
    a = COLOR_RGB[RAINBOW[int(k) % 6]]
    b = COLOR_RGB[RAINBOW[(int(k) + 1) % 6]]
    return mix(a, b, k % 1)


# ---------------------------------------------------------------- patterns

PATTERN_SAMPLE_AIM = {"beam": (0, -1), "slant": (1, -1), "halo": (0, 0), "leap": (0, 0),
                      "lob": (0, -3)}


def draw_pattern_icon(surf, pattern, cx, cy, cell=5, color=None, aim=None, you=True):
    """A tiny grid diagram of a pattern: the dot is the caster, filled cells
    are where the light goes. The same picture is used for your patterns
    and for the ones the Set attacks with."""
    color = color or INK
    offs = pattern_offsets(pattern, *(aim or PATTERN_SAMPLE_AIM[pattern])) or []
    if pattern in ("beam", "slant"):
        offs = offs[:3]                     # rays run to the wall; the icon shows the idea
    rad = max([max(abs(x), abs(y)) for x, y in offs] + [1])
    # centre the drawing on the pattern's bounding box, not on the caster
    xs = [x for x, _ in offs] + [0]
    ys = [y for _, y in offs] + [0]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for gx in range(min(xs), max(xs) + 1):
        for gy in range(min(ys), max(ys) + 1):
            r = pygame.Rect(0, 0, cell - 1, cell - 1)
            r.center = (int(cx + (gx - mx) * cell), int(cy + (gy - my) * cell))
            if (gx, gy) in offs:
                pygame.draw.rect(surf, color, r)
            elif rad <= 4:
                pygame.draw.rect(surf, (226, 218, 206), r)
    if you:
        pygame.draw.circle(surf, INK, (int(cx - mx * cell), int(cy - my * cell)), max(2, cell // 2 + 1))
        pygame.draw.circle(surf, WHITE, (int(cx - mx * cell), int(cy - my * cell)), max(1, cell // 2 - 1))


# ---------------------------------------------------------------- morphing

def morph_between(src, dst, t):
    """Interpolate polygon src into polygon dst (dst may have more corners).
    New corners are born in the middle of src's edges and pushed outward, so
    the shape visibly grows a side rather than melting."""
    t = max(0.0, min(1.0, t))
    n_from, n_to = len(src), len(dst)
    if n_to < n_from:
        return dst if t >= 1 else src
    extra = n_to - n_from
    start = []
    for i in range(n_from):
        a, b = src[i], src[(i + 1) % n_from]
        start.append(a)
        born = extra // n_from + (1 if i < extra % n_from else 0)
        for j in range(born):
            f = (j + 1) / (born + 1)
            start.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    # pair corners up with the rotation of dst that moves them the least
    best = min(range(n_to), key=lambda k: sum(math.dist(start[i], dst[(i + k) % n_to])
                                              for i in range(n_to)))
    return [(s[0] + (dst[(i + best) % n_to][0] - s[0]) * t,
             s[1] + (dst[(i + best) % n_to][1] - s[1]) * t) for i, s in enumerate(start)]


def morph_points(frm, to, t, cx, cy, r):
    """Points for a shape growing from `frm` to `to`. Each may be a shape name
    or a number of sides."""
    def pts(shape):
        if shape == "circle":
            shape = 40
        return shape_points(shape, cx, cy, r)
    return morph_between(pts(frm), pts(to), t)


# ------------------------------------------------------------------ tower

def _sorter_picture(w, h, act, won):
    """The whole climb, painted small: three floors of bricks in their
    colours, the roof and the Round Door, the Long Ramp and the Meadow."""
    from .pixel import Pix, cached, ramp as pramp, shade

    def build():
        p = Pix(w, h, seed=11)
        x0, tw, fh = 9, 42, 39
        base = h - 29
        # the meadow
        p.rect(2, base + 7, w - 4, 20, (120, 210, 96))
        p.rect(2, base + 7, w - 4, 2, (160, 236, 130))
        for i, c in enumerate(COLORS):
            p.rect(5 + i * ((w - 10) // 6), base + 11 + (i % 2) * 5, 2, 2, COLOR_RGB[c])
        for k in range(1, 4):
            style = floor_style(k)
            col = mix(style["wall"], (255, 255, 255), 0.45)
            if k > act and not won:
                col = mix(col, (255, 255, 255), 0.55)
            y = base - k * fh
            p.bricks(x0, y, tw, fh, col, bw=5, bh=3)
            r = pramp(col)
            p.rect(x0 - 1, y, tw + 2, 2, r[4])
            p.rect(x0 - 1, y + 2, tw + 2, 1, r[0])
            door = style["door"]
            from .pixel import critter_points
            pts = critter_points(door, x0 + tw - 9, y + fh // 2 + 4, 5)
            lit = k < act or won
            dcol = (255, 236, 170) if lit else shade(style["wall"], -2)
            if pts:
                p.poly(pts, dcol)
            else:
                p.disc(x0 + tw - 9, y + fh // 2 + 4, 5, dcol)
        roof_y = base - 3 * fh
        p.shingles(0, roof_y - 20, w, 21, (246, 206, 140),
                   mask=lambda xx, yy: abs(xx - (x0 + tw / 2)) <= (yy - (roof_y - 20)) * 1.1 + 1 and yy <= roof_y)
        glow = won or act > 3
        p.disc(x0 + tw // 2, roof_y - 7, 4, (255, 255, 220) if glow else (120, 96, 150))
        p.ring(x0 + tw // 2, roof_y - 7, 4, (200, 160, 100))
        # the Long Ramp, zigzagging down the right to the meadow
        pts = [(x0 + tw // 2 + 5, roof_y - 4), (w - 5, roof_y + 15), (x0 + tw + 5, roof_y + 55),
               (w - 4, roof_y + 90), (x0 + tw + 5, roof_y + 125), (w - 6, base + 8)]
        for i in range(len(pts) - 1):
            for j in range(3):
                p.line((pts[i][0], pts[i][1] + j), (pts[i + 1][0], pts[i + 1][1] + j),
                       COLOR_RGB[RAINBOW[(i + j) % 6]])
        p.outline()
        return p.up(2), pts, base, fh, x0, tw
    return cached(("sorter_pic", w, h, act, won), build)


def draw_tower(surf, rect, act, t, won=False):
    """Side view of the whole climb (pixel art): three floors, the Round Door
    on the roof, the Long Ramp, and the Meadow at the bottom. Marks where you are."""
    rect = pygame.Rect(rect)
    img, pts, base, fh, x0, tw = _sorter_picture(rect.w // 2, rect.h // 2, act, won)
    surf.blit(img, rect.topleft)
    for k in range(1, 4):
        y = rect.y + (base - k * fh) * 2
        draw_text(surf, font(24), str(k + 2), (rect.x + x0 * 2 + 8, y + 10), WHITE, shadow=INK)
        if k == act and not won:
            bob = math.sin(t * 4) * 3
            draw_player(surf, FORMS[k]["shape"], rect.x + x0 * 2 + 36, y + fh + 14 + bob, 12, t,
                        look=(0.6, 0), shadow=False)
    draw_text(surf, font(18), "Meadow", (rect.x + rect.w // 2, rect.y + base * 2 + 36), INK, center=True)
    if won:                                       # a little circle rolling down the ramp, forever
        seg = (t * 0.6) % 1 * (len(pts) - 1)
        i = int(seg)
        a, b = pts[i], pts[min(i + 1, len(pts) - 1)]
        f = seg - i
        draw_player(surf, "circle", rect.x + (a[0] + (b[0] - a[0]) * f) * 2,
                    rect.y + (a[1] + (b[1] - a[1]) * f) * 2 - 8, 7, t, shadow=False)


# -------------------------------------------------------------- map icons

# What each room is for. Fights are where you grow (glint + a reward pick);
# the calm rooms only spend or trade what fights give you. Every path up has
# at least three fights (dungeon.path_ok), so choosing a way is choosing which
# fights and which breathers, never whether to fight.
KIND_INFO = {
    "fight": ("The Set", "Fight. Win glint and pick a reward: a pattern, a facet, more colour.", "R"),
    "elite": ("Hard Set", "A tougher fight. More glint, and a facet is always among the rewards.", "M"),
    "shop": ("Tinter", "Spend the glint fights gave you: light, edges, facets, patterns.", "Y"),
    "rest": ("Still Tile", "No fight, no reward: heal, or hold one more of a colour.", "G"),
    "event": ("Oddity", "No fight. Something for something: a small gift, or a deal.", "C"),
    "boss": ("Keeper", "Holds the side you need for the next door.", None),
}


def node_title(kind, keeper):
    """A room's name. `keeper` is the boss kind on this floor (run.keeper())."""
    if kind == "boss":
        return KINDS[keeper]["label"]
    return KIND_INFO[kind][0]


def node_blurb(kind, keeper):
    if kind == "boss":
        return KINDS[keeper]["desc"]
    return KIND_INFO[kind][1]


def node_color(kind, t=0.0):
    c = KIND_INFO[kind][2]
    return cycling_color(t) if c is None else COLOR_RGB[c]


def draw_node_icon(surf, kind, cx, cy, r, keeper, t, faded=False):
    """A little picture of what is in a room, drawn from shapes."""
    k = 0.55 if faded else 0.0

    def col(c):
        return mix(c, (255, 255, 255), k)

    if kind == "fight":
        draw_critter(surf, "triangle", cx + r * 0.38, cy + r * 0.05, r * 0.42, col(COLOR_RGB["B"]),
                     look=(-0.6, 0), shadow=False, width=2)
        draw_critter(surf, "square", cx - r * 0.3, cy + r * 0.1, r * 0.45, col(COLOR_RGB["R"]),
                     look=(0.6, 0), shadow=False, width=2)
    elif kind == "elite":
        for sx in (-1, 1):
            draw_poly(surf, [(cx + sx * r * 0.25, cy - r * 0.45), (cx + sx * r * 0.6, cy - r * 0.45),
                             (cx + sx * r * 0.45, cy - r * 0.95)], col(COLOR_RGB["Y"]), INK, 2)
        draw_critter(surf, "square", cx, cy + r * 0.1, r * 0.55, col(COLOR_RGB["M"]),
                     shadow=False, width=2)
    elif kind == "shop":
        for i, c in enumerate(("R", "G", "B")):
            a = -math.pi / 2 + i * math.tau / 3
            pygame.draw.circle(surf, col(COLOR_RGB[c]),
                               (int(cx + math.cos(a) * r * 0.3), int(cy + math.sin(a) * r * 0.3)),
                               int(r * 0.42))
        for i, c in enumerate(("R", "G", "B")):
            a = -math.pi / 2 + i * math.tau / 3
            pygame.draw.circle(surf, INK, (int(cx + math.cos(a) * r * 0.3),
                                           int(cy + math.sin(a) * r * 0.3)), int(r * 0.42), 2)
    elif kind == "rest":
        draw_critter(surf, "square", cx, cy + r * 0.12, r * 0.52, col(COLOR_RGB["G"]),
                     mood="sleep", shadow=False, width=2)
        draw_text(surf, font(18), "z", (cx + r * 0.55, cy - r * 0.7), INK, center=True)
    elif kind == "event":
        draw_body(surf, "diamond", cx, cy, r * 0.62, col(COLOR_RGB["C"]), INK, 2)
        draw_text(surf, font(26), "?", (cx, cy + 1), INK, center=True)
    elif kind == "boss":
        draw_critter(surf, KINDS[keeper]["shape"], cx, cy + r * 0.05, r * 0.6, col(cycling_color(t)),
                     shadow=False, width=3)
    else:  # pragma: no cover - a new node kind with no icon
        draw_body(surf, "circle", cx, cy, r * 0.5, col(PAPER), INK, 2)


def draw_exit_door(surf, style, cx, cy, r, t, open_=False):
    return draw_door(surf, style["door"], cx, cy, r, style["wall"], t, 1.0 if open_ else 0.0,
                     locked=not open_)


def draw_slot(surf, shape, cx, cy, r, wall):
    """The hole you came in through (or were cut from)."""
    pygame.draw.ellipse(surf, INK, pygame.Rect(cx - r * 1.5, cy - r * 0.5 + 4, r * 3, r * 1.2))
    pygame.draw.ellipse(surf, lighten(wall, 0.3), pygame.Rect(cx - r * 1.5, cy - r * 0.5, r * 3, r * 1.2))
    pygame.draw.ellipse(surf, INK, pygame.Rect(cx - r * 1.5, cy - r * 0.5, r * 3, r * 1.2), 2)
    draw_body(surf, shape, cx, cy + 1, r * 0.45, mix(wall, INK, 0.45), INK, 2, sy=0.5)


# ------------------------------------------------------------------ tinter

def _hexagon_pts(cx, cy, r, rot=0.25, sx=1.15):
    pts = shape_points("hexagon", cx, cy, r, rot)
    return [(cx + (x - cx) * sx, y) for x, y in pts]


def draw_tinter(surf, cx, cy, r, t, look=(-0.5, 0.3), mood="happy"):
    """The Tinter: a lopsided glass hexagon with coloured light sloshing in it."""
    rot = 0.25 + math.sin(t * 1.3) * 0.06
    draw_shadow(surf, cx, cy + r * 1.0, r * 2.2, r * 0.5)
    pts = _hexagon_pts(cx, cy, r, rot)
    pygame.draw.polygon(surf, (246, 244, 255), pts)
    # the liquid: rainbow layers with a wavy top, clipped to the glass
    size = int(r * 3)
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    ox, oy = cx - size / 2, cy - size / 2
    level = size / 2 + r * 0.05
    for i, c in enumerate(RAINBOW):
        top = level + i * r * 0.16
        wave = [(x, top + math.sin(t * 2.5 + x * 0.06 + i) * r * 0.06) for x in range(0, size + 8, 8)]
        pygame.draw.polygon(img, (*lighten(COLOR_RGB[c], 0.15), 255), wave + [(size, size), (0, size)])
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [(x - ox, y - oy) for x, y in pts])
    img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(img, (int(ox), int(oy)))
    draw_poly(surf, pts, None, INK, 4)
    pygame.draw.arc(surf, WHITE, pygame.Rect(cx - r * 0.8, cy - r * 0.9, r * 0.9, r * 1.1), 1.7, 2.9, 4)
    # a spout, with a drip forming
    sx, sy = pts[1]
    draw_poly(surf, [(sx - 4, sy + 6), (sx + r * 0.35, sy - r * 0.12), (sx + 2, sy + 16)], (246, 244, 255),
              INK, 3)
    drip = (t * 0.7) % 1
    pygame.draw.circle(surf, COLOR_RGB[RAINBOW[int(t * 0.7) % 6]],
                       (int(sx + r * 0.33), int(sy - r * 0.05 + drip * r * 0.9)), max(2, int(r * 0.07)))
    draw_eyes(surf, cx - r * 0.05, cy - r * 0.35, r * 0.75, look, mood)


def draw_ware(surf, rid, cx, cy, t):
    """A thing you can buy, drawn as the thing itself, standing at (cx, cy)."""
    if rid == "heal":                                 # a jar of warm light
        glow = 0.5 + 0.5 * math.sin(t * 3)
        for i in range(8):
            a = i * math.tau / 8 + t * 0.4
            pygame.draw.line(surf, (255, 226, 120), (cx + math.cos(a) * 20, cy - 18 + math.sin(a) * 20),
                             (cx + math.cos(a) * (30 + 4 * glow), cy - 18 + math.sin(a) * (30 + 4 * glow)), 3)
        jar = pygame.Rect(cx - 18, cy - 40, 36, 44)
        pygame.draw.rect(surf, (240, 244, 255), jar, border_radius=10)
        pygame.draw.circle(surf, (255, 214, 72), (cx, cy - 16), 11)
        pygame.draw.circle(surf, WHITE, (cx - 3, cy - 19), 4)
        pygame.draw.rect(surf, INK, jar, 3, border_radius=10)
        pygame.draw.rect(surf, (200, 140, 90), (cx - 14, cy - 48, 28, 10), border_radius=3)
        pygame.draw.rect(surf, INK, (cx - 14, cy - 48, 28, 10), 2, border_radius=3)
    elif rid == "maxhp":                              # a thick, sturdy edge
        pygame.draw.line(surf, INK, (cx - 22, cy), (cx + 16, cy - 44), 17)
        pygame.draw.line(surf, (255, 140, 160), (cx - 22, cy), (cx + 16, cy - 44), 11)
        pygame.draw.line(surf, (255, 200, 210), (cx - 18, cy - 8), (cx + 8, cy - 38), 3)
    elif rid.startswith("cap:"):                      # a bottle of deeper colour
        col = COLOR_RGB[rid.split(":", 1)[1]]
        body = pygame.Rect(cx - 17, cy - 34, 34, 36)
        pygame.draw.rect(surf, col, body, border_radius=12)
        pygame.draw.rect(surf, INK, body, 3, border_radius=12)
        neck = pygame.Rect(cx - 7, cy - 48, 14, 16)
        pygame.draw.rect(surf, lighten(col, 0.4), neck)
        pygame.draw.rect(surf, INK, neck, 3)
        pygame.draw.rect(surf, (200, 140, 90), (cx - 8, cy - 56, 16, 9), border_radius=3)
        pygame.draw.rect(surf, INK, (cx - 8, cy - 56, 16, 9), 2, border_radius=3)
        pygame.draw.circle(surf, lighten(col, 0.6), (cx - 7, cy - 24), 4)
        draw_colour_mark(surf, rid.split(":", 1)[1], cx + 4, cy - 14, 8)
    elif rid.startswith("relic:"):                    # a cut facet on a cushion
        cushion = pygame.Rect(cx - 26, cy - 12, 52, 14)
        pygame.draw.ellipse(surf, (150, 90, 200), cushion)
        pygame.draw.ellipse(surf, INK, cushion, 2)
        draw_facet(surf, rid.split(":", 1)[1], cx, cy - 30 + math.sin(t * 2.5) * 3, 18, t)
    elif rid.startswith("pattern:"):                  # a printed pattern card
        card = pygame.Rect(cx - 24, cy - 56, 48, 56)
        pygame.draw.rect(surf, INK, card.move(2, 3), border_radius=6)
        pygame.draw.rect(surf, PAPER, card, border_radius=6)
        pygame.draw.rect(surf, INK, card, 3, border_radius=6)
        draw_pattern_icon(surf, rid.split(":", 1)[1], cx, cy - 28, 5, COLOR_RGB["M"])


# ------------------------------------------------------------------ portal

def draw_portal(surf, cx, cy, r, t, shape="circle", power=1.0):
    """A door that is open to you: rings of every colour turning in opposite
    directions, spiral arms, a blazing core and sparks in orbit. `shape` cuts
    the rings (the Round Door is round; the Four-Door is square...)."""
    power = max(0.0, min(1.5, power))
    layer = pygame.Surface((int(r * 6), int(r * 6)), pygame.SRCALPHA)
    lc = (layer.get_width() // 2, layer.get_height() // 2)
    # rays fanning out behind
    for i in range(18):
        a = t * 0.35 + i * math.tau / 18
        w = 0.09
        pts = [lc, (lc[0] + math.cos(a) * r * 3, lc[1] + math.sin(a) * r * 3),
               (lc[0] + math.cos(a + w) * r * 3, lc[1] + math.sin(a + w) * r * 3)]
        pygame.draw.polygon(layer, (*COLOR_RGB[RAINBOW[i % 6]], int(60 * power)), pts)
    # spiral arms
    for arm in range(6):
        pts = []
        for k in range(24):
            f = k / 23
            a = t * 1.6 + arm * math.tau / 6 + f * 3.2
            pts.append((lc[0] + math.cos(a) * r * f, lc[1] + math.sin(a) * r * f))
        pygame.draw.lines(layer, (*COLOR_RGB[RAINBOW[arm]], int(200 * min(1, power))), False, pts,
                          max(2, int(r * 0.07)))
    surf.blit(layer, (int(cx - lc[0]), int(cy - lc[1])))
    # rings, alternating spin, cut to the door's shape
    for i in range(7):
        rr = r * (1 - i * 0.12)
        spin = t * (0.6 if i % 2 else -0.6)
        col = COLOR_RGB[RAINBOW[(i + int(t * 3)) % 6]]
        if shape == "circle":
            pygame.draw.circle(surf, col, (int(cx), int(cy)), int(rr), max(2, int(r * 0.06)))
        else:
            draw_poly(surf, shape_points(shape, cx, cy, rr * 0.85, spin), None, col, max(2, int(r * 0.06)))
    # the core
    glow = 0.5 + 0.5 * math.sin(t * 5)
    for i in range(4):
        pygame.draw.circle(surf, mix((255, 240, 180), WHITE, 0.3 * i),
                           (int(cx), int(cy)), int(r * (0.32 - i * 0.07) * (1 + 0.15 * glow * power)))
    # sparks in orbit
    for i in range(14):
        a = t * (1.2 + (i % 3) * 0.4) + i * math.tau / 14
        rr = r * (1.05 + 0.12 * math.sin(t * 2 + i))
        pygame.draw.circle(surf, WHITE, (int(cx + math.cos(a) * rr), int(cy + math.sin(a) * rr)),
                           max(2, int(r * 0.04)))


# ------------------------------------------------------------------ facets

def draw_facet(surf, rid, cx, cy, r, t=0.0):
    """A facet: always the same cut gem (a table on top, a point below), in
    its colour if it is about a colour, or shot through with every colour if
    not. Deliberately not a triangle/square/circle: those mean enemies."""
    tint = RELICS[rid].get("tint")
    crown = [(cx - r, cy - r * 0.15), (cx - r * 0.55, cy - r * 0.7), (cx + r * 0.55, cy - r * 0.7),
             (cx + r, cy - r * 0.15)]
    outline = crown + [(cx, cy + r)]
    if tint:
        body, light = COLOR_RGB[tint], lighten(COLOR_RGB[tint], 0.5)
        pygame.draw.polygon(surf, body, outline)
    else:
        pygame.draw.polygon(surf, (250, 248, 255), outline)
        for i, c in enumerate(RAINBOW):                        # prismatic: light split inside
            a = (cx - r + (2 * r) * (i + 0.5) / 6, cy - r * 0.15)
            pygame.draw.line(surf, lighten(COLOR_RGB[c], 0.2), a, (cx, cy + r * 0.9), 2)
        light = WHITE
    pygame.draw.polygon(surf, light, crown)                   # the table catches the light
    for x in (cx - r * 0.55, cx + r * 0.55):
        pygame.draw.line(surf, INK, (x, cy - r * 0.7), (cx, cy + r), 1)
    pygame.draw.line(surf, INK, (cx - r, cy - r * 0.15), (cx + r, cy - r * 0.15), 2)
    draw_poly(surf, outline, None, INK, 2 if r < 14 else 3)
    if math.sin(t * 3 + cx) > 0.6:                             # a glint
        pygame.draw.circle(surf, WHITE, (int(cx - r * 0.3), int(cy - r * 0.45)), max(1, int(r * 0.12)))
