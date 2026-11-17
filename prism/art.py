"""Procedural art: shapes with faces, gradients, confetti, particles, doors.

Everything is drawn with plain pygame.draw calls (CPU only, no image
assets), so every visual in the game is literally made of shape and colour.
Surfaces that are expensive to build (gradients, hatching, shadows) are
cached by size.
"""

import math
import random

import pygame

from .consts import COLOR_RGB, COLORS, RAINBOW
from .widgets import INK, WHITE

TAU = math.tau
SIDES = {"triangle": 3, "square": 4, "diamond": 4, "pentagon": 5, "hexagon": 6}


def mix(a, b, t):
    """Blend colour a toward b by t (0..1)."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(c, t=0.35):
    return mix(c, (255, 255, 255), t)


def darken(c, t=0.35):
    return mix(c, (0, 0, 0), t)


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ shapes

def regular_points(n, cx, cy, r, rot=-math.pi / 2):
    return [(cx + r * math.cos(rot + TAU * i / n), cy + r * math.sin(rot + TAU * i / n))
            for i in range(n)]


def shape_points(shape, cx, cy, r, rot=0.0):
    """Polygon points for a named shape (or an int number of sides), scaled
    so every shape has roughly the same visual weight as a circle of r.
    Returns None for a circle."""
    if shape == "circle":
        return None
    if isinstance(shape, int):
        return regular_points(shape, cx, cy, r * 1.05, -math.pi / 2 + rot)
    if shape == "triangle":
        return regular_points(3, cx, cy + r * 0.14, r * 1.22, -math.pi / 2 + rot)
    if shape == "square":
        return regular_points(4, cx, cy, r * 1.27, -math.pi / 4 + rot)
    if shape == "diamond":
        return regular_points(4, cx, cy, r * 1.18, -math.pi / 2 + rot)
    if shape == "pentagon":
        return regular_points(5, cx, cy + r * 0.04, r * 1.1, -math.pi / 2 + rot)
    if shape == "hexagon":
        return regular_points(6, cx, cy, r * 1.06, rot)
    return regular_points(SIDES.get(shape, 4), cx, cy, r, rot)


def _scaled(pts, cx, cy, sx, sy, anchor_y):
    return [(cx + (x - cx) * sx, anchor_y + (y - anchor_y) * sy) for x, y in pts]


def draw_poly(surf, pts, fill, outline=INK, width=3):
    """Filled polygon with a round-jointed outline (reads as a chunky toy)."""
    if fill is not None:
        pygame.draw.polygon(surf, fill, pts)
    if outline is not None and width:
        pygame.draw.lines(surf, outline, True, pts, width)
        if width > 2:
            for p in pts:
                pygame.draw.circle(surf, outline, (int(p[0]), int(p[1])), width // 2)


def draw_body(surf, shape, cx, cy, r, fill, outline=INK, width=3, rot=0.0, sx=1.0, sy=1.0):
    """One shape centred on (cx, cy). sx/sy squash and stretch about the base."""
    base = cy + r
    if shape == "circle":
        w, h = 2 * r * sx, 2 * r * sy
        rect = pygame.Rect(0, 0, max(2, int(w)), max(2, int(h)))
        rect.center = (int(cx), int(base - h / 2))
        if fill is not None:
            pygame.draw.ellipse(surf, fill, rect)
        if outline is not None and width:
            pygame.draw.ellipse(surf, outline, rect, width)
        return rect
    pts = shape_points(shape, cx, cy, r, rot)
    if sx != 1.0 or sy != 1.0:
        pts = _scaled(pts, cx, cy, sx, sy, base)
    draw_poly(surf, pts, fill, outline, width)
    return pygame.Rect(int(cx - r), int(cy - r), int(2 * r), int(2 * r))


_SHADOWS = {}


def draw_shadow(surf, cx, cy, w, h, alpha=60):
    key = (int(w), int(h), alpha)
    s = _SHADOWS.get(key)
    if s is None:
        s = pygame.Surface((max(2, int(w)), max(2, int(h))), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (*INK, alpha), s.get_rect())
        _SHADOWS[key] = s
    surf.blit(s, (int(cx - w / 2), int(cy - h / 2)))


def _rot(cx, cy, x, y, cs, sn):
    dx, dy = x - cx, y - cy
    return cx + dx * cs - dy * sn, cy + dx * sn + dy * cs


def draw_eyes(surf, cx, cy, r, look=(0.0, 0.0), mood="plain", blink=False, spin=0.0):
    """Two eyes. mood: plain | cross | happy | sleep | hurt | wow.
    spin rotates the whole face about (cx, cy): that is how a circle rolls."""
    gap = r * 0.38
    er = max(3.4, r * 0.24)
    lift = r * 0.14 if spin else 0.0
    cs, sn = math.cos(spin), math.sin(spin)
    lw = max(2, int(er * 0.45))
    for side in (-1, 1):
        ex, ey = _rot(cx, cy, cx + side * gap, cy - lift, cs, sn)
        if mood == "happy":
            pts = [_rot(ex, ey, ex + math.cos(a) * er, ey - math.sin(a) * er * 0.9 + er * 0.3, cs, sn)
                   for a in (0.15, 0.8, 1.57, 2.34, 3.0)]
            pygame.draw.lines(surf, INK, False, pts, lw)
            continue
        if mood == "sleep" or blink:
            a = _rot(ex, ey, ex - er, ey, cs, sn)
            b = _rot(ex, ey, ex + er, ey, cs, sn)
            pygame.draw.line(surf, INK, a, b, lw)
            continue
        if mood == "hurt":
            d = er * 0.8
            pygame.draw.line(surf, INK, (ex - d, ey - d), (ex + d, ey + d), lw)
            pygame.draw.line(surf, INK, (ex - d, ey + d), (ex + d, ey - d), lw)
            continue
        big = er * (1.25 if mood == "wow" else 1.0)
        pygame.draw.circle(surf, WHITE, (int(ex), int(ey)), int(big))
        pygame.draw.circle(surf, INK, (int(ex), int(ey)), int(big), max(1, int(er * 0.3)))
        lx, ly = look
        n = math.hypot(lx, ly)
        if n > 1:
            lx, ly = lx / n, ly / n
        pr = max(1.6, big * 0.55)
        pygame.draw.circle(surf, INK, (int(ex + lx * big * 0.4), int(ey + ly * big * 0.4)), int(pr))
        if mood == "cross":
            # angry brows: high on the outside, low toward the middle
            y0 = ey - big * 1.3
            pygame.draw.line(surf, INK, (ex + side * big * 1.15, y0 - big * 0.5),
                             (ex - side * big * 0.6, y0 + big * 0.3), lw)


def face_center(shape, cx, cy, r):
    """Where the eyes sit: lower on a triangle (its belly is at the bottom)."""
    if shape == "triangle":
        return cx, cy + r * 0.32
    if shape == "diamond":
        return cx, cy + r * 0.05
    return cx, cy - r * 0.02


def draw_mark(surf, mark, shape, cx, cy, r, color, sx=1.0, sy=1.0):
    """Small body details that tell same-shaped enemies apart."""
    if mark == "frame":          # a Warden: a square inside a square
        draw_body(surf, shape, cx, cy + r * (1 - sy) * 0.9, r * 0.72, None, darken(color, 0.3),
                  2, 0, sx, sy)
    elif mark == "seam":         # a Splitter: the diagonal it will come apart along
        h = r * 0.9
        top = cy + r - 2 * r * sy
        for k in range(5):
            f0, f1 = k / 5, (k + 0.55) / 5
            pygame.draw.line(surf, INK, (cx - h * sx + 2 * h * sx * f0, top + 3 + (2 * r * sy - 6) * f0),
                             (cx - h * sx + 2 * h * sx * f1, top + 3 + (2 * r * sy - 6) * f1), 2)
    elif mark == "feet":         # a Stomper: two stubby feet
        base = cy + r
        for side in (-1, 1):
            foot = pygame.Rect(0, 0, int(r * 0.55), int(r * 0.32))
            foot.center = (int(cx + side * r * 0.45), int(base + r * 0.05))
            pygame.draw.ellipse(surf, darken(color, 0.25), foot)
            pygame.draw.ellipse(surf, INK, foot, 2)
    elif mark == "horn":         # a Lancer: a point sticking straight up
        top = cy + r - 2 * r * sy
        if shape == "triangle":
            top -= r * 0.25
        draw_poly(surf, [(cx - r * 0.18, top + 3), (cx + r * 0.18, top + 3), (cx, top - r * 0.55)],
                  lighten(color, 0.45), INK, 2)
    elif mark == "sash":         # a Skew: a diagonal band, because it only looks sideways
        a = (cx - r * 0.75 * sx, cy - r * 0.55)
        b = (cx + r * 0.75 * sx, cy + r * 0.75)
        pygame.draw.line(surf, INK, a, b, 7)
        pygame.draw.line(surf, lighten(color, 0.5), a, b, 3)
    elif mark == "spring":       # a Hopper: a coil underneath
        base = cy + r
        pts = [(cx + (-1 if k % 2 else 1) * r * 0.3, base - 2 + k * r * 0.14) for k in range(5)]
        pygame.draw.lines(surf, INK, False, pts, 3)
    elif mark == "sprout":       # a Bloom: a circle that took root instead of rolling
        top = cy + r - 2 * r * sy
        pygame.draw.line(surf, INK, (cx, top + 2), (cx + r * 0.15, top - r * 0.45), 3)
        leaf = [(cx + r * 0.15, top - r * 0.45), (cx + r * 0.6, top - r * 0.7),
                (cx + r * 0.35, top - r * 0.25)]
        draw_poly(surf, leaf, lighten(color, 0.3), INK, 2)


PIXEL_CHARACTERS = False      # True: characters painted as pixel art too (pixel.critter). They're
                              # smooth on purpose: the world has corners; the characters are
                              # the ones growing round.


def _pixel_character(surf, shape, cx, cy, r, color, look, mood, rot, sx, sy, shadow, blink, mark,
                     prism=False, t=0.0):
    from . import pixel
    k = pixel.scale_for(r)
    if shadow:
        sh = pixel.shadow(r * 1.9 * sx / k, r * 0.55 / k)
        big = pygame.transform.scale(sh, (sh.get_width() * k, sh.get_height() * k))
        surf.blit(big, (int(cx - big.get_width() / 2), int(cy + r * 1.05 - big.get_height() / 2)))
    circle = shape == "circle"
    img = pixel.critter_up(k, shape, color, r / k, "blink" if blink else mood, look,
                           rot=0.0 if circle else rot, sx=sx, sy=sy, mark=mark, prism=prism,
                           phase=t * 0.5, spin=rot if circle else 0.0)
    surf.blit(img, (int(cx - img.get_width() / 2), int(cy - img.get_height() / 2)))


def draw_critter(surf, shape, cx, cy, r, color, look=(0.0, 0.0), mood="cross", rot=0.0,
                 sx=1.0, sy=1.0, shadow=True, blink=False, outline=INK, width=3, mark=None, face=None):
    """A shape with a face. All characters in the game are drawn with this.
    `face` gives a Keeper its own expression (see draw_face)."""
    if PIXEL_CHARACTERS and r >= 6 and color is not None and len(color) >= 3:
        _pixel_character(surf, shape, cx, cy, r, color, look, mood, rot, sx, sy, shadow, blink, mark)
        return
    if shadow:
        draw_shadow(surf, cx, cy + r * 1.05, r * 1.9 * sx, r * 0.55)
    draw_body(surf, shape, cx, cy, r, color, outline, width, rot, sx, sy)
    if mark:
        draw_mark(surf, mark, shape, cx, cy, r, color, sx, sy)
    # a soft highlight, upper left
    hl = lighten(color, 0.5)
    hx, hy = cx - r * 0.42 * sx, cy + r - 2 * r * sy * 0.78
    if shape == "triangle":
        hx, hy = cx - r * 0.18, cy - r * 0.2
    pygame.draw.circle(surf, hl, (int(hx), int(hy)), max(2, int(r * 0.16)))
    fx, fy = face_center(shape, cx, cy, r)
    fy = cy + r - (cy + r - fy) * sy
    spin = rot if (shape == "circle" or isinstance(shape, int)) else 0.0
    if face and mood not in ("hurt", "sleep"):
        draw_face(surf, face, fx, fy, r * min(1.0, max(0.7, sx)), look, mood, blink)
        return
    draw_eyes(surf, fx, fy, r * min(1.0, max(0.7, sx)), look, mood, blink, spin)


# ------------------------------------------------------------------ faces

def _brow(surf, ex, ey, w, lift_in, lift_out, side, lw):
    """An eyebrow over an eye at (ex, ey): `side` -1 left eye, 1 right eye;
    lifts are how high the inner and outer ends sit (in eye widths)."""
    inner = (ex - side * w * 0.9, ey - w * (1.4 + lift_in))
    outer = (ex + side * w * 1.1, ey - w * (1.4 + lift_out))
    pygame.draw.line(surf, INK, inner, outer, lw)


def draw_face(surf, style, cx, cy, r, look=(0.0, 0.0), mood="plain", blink=False):
    """A Keeper's own expression. Each one is a little portrait of what it
    believes: the Latch worries, the Knot digs in, the Cap can't stop
    grinning, the Rime is frozen stern, the Hourglass frets, the Focus
    squints, the Beacon beams, the Vane is dizzy. Happy (once it lets go)
    softens every one of them into a smile."""
    gap = r * 0.38
    er = max(3.4, r * 0.24)
    lw = max(2, int(er * 0.45))
    lx, ly = look
    n = math.hypot(lx, ly)
    if n > 1:
        lx, ly = lx / n, ly / n
    eyes = [(cx - gap, cy), (cx + gap, cy)]

    def round_eye(ex, ey, size=1.0, pupil=0.55, dx=0.0, dy=0.0):
        big = er * size
        pygame.draw.circle(surf, WHITE, (int(ex), int(ey)), int(big))
        pygame.draw.circle(surf, INK, (int(ex), int(ey)), int(big), max(1, int(er * 0.3)))
        pr = max(1.6, big * pupil)
        pygame.draw.circle(surf, INK, (int(ex + (lx + dx) * big * 0.4), int(ey + (ly + dy) * big * 0.4)), int(pr))
        pygame.draw.circle(surf, WHITE, (int(ex + (lx + dx) * big * 0.4 - pr * 0.4),
                                         int(ey + (ly + dy) * big * 0.4 - pr * 0.4)), max(1, int(pr * 0.3)))

    def mouth(kind, w=0.5, y=0.42):
        mx, my = cx, cy + r * y
        ww = r * w
        if kind == "smile":
            pygame.draw.arc(surf, INK, (mx - ww / 2, my - ww * 0.45, ww, ww * 0.7), math.pi * 1.1, math.pi * 1.9, lw)
        elif kind == "grin":                                  # wide open, D-shaped
            rect = pygame.Rect(0, 0, int(ww), int(ww * 0.55))
            rect.midtop = (int(mx), int(my - ww * 0.1))
            pygame.draw.ellipse(surf, INK, rect)
            pygame.draw.rect(surf, INK, (rect.x, rect.y, rect.w, rect.h // 2))
            pygame.draw.ellipse(surf, (240, 110, 130), rect.inflate(-lw * 2, -lw * 2).move(0, lw // 2))
        elif kind == "flat":
            pygame.draw.line(surf, INK, (mx - ww / 2, my), (mx + ww / 2, my), lw)
        elif kind == "frown":
            pygame.draw.arc(surf, INK, (mx - ww / 2, my, ww, ww * 0.6), math.pi * 0.15, math.pi * 0.85, lw)
        elif kind == "wobble":
            pts = [(mx - ww / 2 + k * ww / 6, my + (2 if k % 2 else -2)) for k in range(7)]
            pygame.draw.lines(surf, INK, False, pts, lw)
        elif kind == "o":
            pygame.draw.circle(surf, INK, (int(mx), int(my)), max(2, int(ww * 0.22)))
        elif kind == "smirk":
            pygame.draw.arc(surf, INK, (mx - ww * 0.2, my - ww * 0.35, ww * 0.6, ww * 0.5),
                            math.pi * 1.2, math.pi * 1.95, lw)

    if mood == "happy":                                       # let go: every one of them softens
        for side, (ex, ey) in zip((-1, 1), eyes):
            pts = [(ex + math.cos(a) * er, ey - math.sin(a) * er * 0.9 + er * 0.3)
                   for a in (0.15, 0.8, 1.57, 2.34, 3.0)]
            pygame.draw.lines(surf, INK, False, pts, lw)
        mouth("smile")
        if style in ("focus", "intense"):
            pygame.draw.circle(surf, (250, 220, 120), (int(eyes[1][0]), int(eyes[1][1])), int(er * 1.5), 3)
        return
    if blink:
        for ex, ey in eyes:
            pygame.draw.line(surf, INK, (ex - er, ey), (ex + er, ey), lw)
        return
    if style == "worried":                                    # the Latch: wide eyes, brows up in the middle
        for side, (ex, ey) in zip((-1, 1), eyes):
            round_eye(ex, ey, 1.2, 0.38)
            _brow(surf, ex, ey, er, 0.7, -0.1, side, lw)
        mouth("wobble", 0.45)
        drop = [(cx + r * 0.75, cy - r * 0.55), (cx + r * 0.65, cy - r * 0.25), (cx + r * 0.85, cy - r * 0.25)]
        pygame.draw.polygon(surf, (150, 210, 255), drop)
        pygame.draw.circle(surf, (150, 210, 255), (int(cx + r * 0.75), int(cy - r * 0.25)), max(2, int(r * 0.1)))
    elif style == "stubborn":                                 # the Knot: heavy lids, dug in
        for side, (ex, ey) in zip((-1, 1), eyes):
            round_eye(ex, ey, 1.0, 0.5, dy=0.3)
            lid = pygame.Rect(0, 0, int(er * 2.4), int(er * 1.2))
            lid.midbottom = (int(ex), int(ey + 1))
            pygame.draw.rect(surf, INK, lid.move(0, -2))
            _brow(surf, ex, ey, er, -0.3, 0.1, side, lw + 1)
        mouth("frown", 0.42)
    elif style == "giddy":                                    # the Cap: sparkly eyes, a huge grin
        for side, (ex, ey) in zip((-1, 1), eyes):
            round_eye(ex, ey, 1.3, 0.6, dy=-0.2)
            pygame.draw.circle(surf, WHITE, (int(ex + er * 0.35), int(ey + er * 0.3)), max(1, int(er * 0.25)))
        mouth("grin", 0.62)
        for side, (ex, ey) in zip((-1, 1), eyes):
            pygame.draw.circle(surf, (255, 150, 170), (int(ex + side * er * 0.6), int(ey + er * 1.8)),
                               max(2, int(er * 0.55)))
    elif style == "stern":                                    # the Rime: frozen slits, level brows, frost
        for side, (ex, ey) in zip((-1, 1), eyes):
            pygame.draw.line(surf, INK, (ex - er, ey), (ex + er, ey), lw + 1)
            pygame.draw.line(surf, (220, 240, 255), (ex - er * 1.2, ey - er * 1.5), (ex + er * 1.2, ey - er * 1.5),
                             lw + 2)
            pygame.draw.line(surf, INK, (ex - er * 1.2, ey - er * 1.5), (ex + er * 1.2, ey - er * 1.5), 1)
        mouth("flat", 0.3)
    elif style == "fussy":                                    # the Hourglass: one brow up, an "o", eyes aside
        for side, (ex, ey) in zip((-1, 1), eyes):
            round_eye(ex, ey, 1.0, 0.5, dx=0.7)
            _brow(surf, ex, ey, er, 0.5 if side > 0 else -0.1, 0.9 if side > 0 else -0.1, side, lw)
        mouth("o", 0.45)
    elif style == "intense":                                  # the Focus: one squint, one big eye in a monocle
        (lx0, ly0), (rx0, ry0) = eyes
        pygame.draw.line(surf, INK, (lx0 - er, ly0 - er * 0.2), (lx0 + er, ly0 + er * 0.2), lw + 1)
        round_eye(rx0, ry0, 1.35, 0.4)
        pygame.draw.circle(surf, (250, 220, 120), (int(rx0), int(ry0)), int(er * 1.7), 3)
        pygame.draw.line(surf, (250, 220, 120), (rx0 + er * 1.2, ry0 + er * 1.2), (rx0 + er * 1.6, cy + r * 0.8), 2)
        mouth("flat", 0.35)
    elif style == "proud":                                    # the Beacon: chin up, beaming
        for side, (ex, ey) in zip((-1, 1), eyes):
            round_eye(ex, ey - er * 0.3, 1.1, 0.55, dy=-0.8)
            _brow(surf, ex, ey - er * 0.3, er, 0.4, 0.4, side, lw)
        mouth("smirk", 0.5)
    elif style == "dizzy":                                    # the Vane: spiral eyes, a wavy mouth
        t = pygame.time.get_ticks() / 1000.0
        for side, (ex, ey) in zip((-1, 1), eyes):
            pygame.draw.circle(surf, WHITE, (int(ex), int(ey)), int(er * 1.15))
            pts = [(ex + math.cos(a + t * 4 * side) * er * a / 10, ey + math.sin(a + t * 4 * side) * er * a / 10)
                   for a in [k * 0.5 for k in range(20)]]
            pygame.draw.lines(surf, INK, False, pts, 2)
            pygame.draw.circle(surf, INK, (int(ex), int(ey)), int(er * 1.15), max(1, int(er * 0.3)))
        mouth("wobble", 0.5)
    elif style == "strict":                                   # the Four-Keeper: square and cross
        for side, (ex, ey) in zip((-1, 1), eyes):
            rect = pygame.Rect(0, 0, int(er * 2), int(er * 2))
            rect.center = (int(ex), int(ey))
            pygame.draw.rect(surf, WHITE, rect)
            pygame.draw.rect(surf, INK, rect, max(1, int(er * 0.3)))
            pygame.draw.rect(surf, INK, (int(ex + lx * er * 0.4 - er * 0.4), int(ey + ly * er * 0.4 - er * 0.4),
                                         int(er * 0.9), int(er * 0.9)))
            _brow(surf, ex, ey, er, -0.5, 0.4, side, lw + 2)
        mouth("flat", 0.5)
    elif style == "haughty":                                  # the Five-Keeper: lids low, looking down its nose
        for side, (ex, ey) in zip((-1, 1), eyes):
            round_eye(ex, ey, 1.0, 0.5, dy=0.6)
            lid = pygame.Rect(0, 0, int(er * 2.4), int(er * 1.1))
            lid.midbottom = (int(ex), int(ey - er * 0.1))
            pygame.draw.rect(surf, INK, lid)
        mouth("smirk", 0.45)
    elif style == "melancholy":                               # the Stillwheel: droopy, quiet
        for side, (ex, ey) in zip((-1, 1), eyes):
            round_eye(ex, ey, 0.95, 0.5, dy=0.5)
            _brow(surf, ex, ey, er, 0.5, -0.4, side, lw)
        mouth("frown", 0.3, 0.5)
    else:
        draw_eyes(surf, cx, cy, r, look, mood, blink)


_PRISM_CACHE = {}


def _prism_fill(shape, r, phase, rot, sx, sy):
    """A shape-masked sheet of soft rainbow light: the inside of a prism."""
    key = (shape, int(r), int(phase * 12) % 72, round(rot, 2), round(sx, 2), round(sy, 2))
    img = _PRISM_CACHE.get(key)
    if img is not None:
        return img
    if len(_PRISM_CACHE) > 600:
        _PRISM_CACHE.clear()
    size = int(r * 3) + 4
    c = size / 2
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    band = max(3, int(r * 0.45))
    off = int(phase * 12) % 72 / 72 * band * 6
    for k in range(-size, size * 2, band):
        i = int((k + off) // band) % 6
        col = lighten(COLOR_RGB[RAINBOW[i]], 0.62)
        pygame.draw.polygon(img, col, [(k - off % band, 0), (k - off % band + band, 0),
                                       (k - off % band + band - size, size),
                                       (k - off % band - size, size)])
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    draw_body(mask, shape, c, c, r, (255, 255, 255, 255), None, 0, rot, sx, sy)
    img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    _PRISM_CACHE[key] = img
    return img


def _turn_step(shape, rot):
    """A body's turn, rounded so the same few pictures get reused: a circle
    looks the same at any turn; an n-gon repeats every 1/n of a turn."""
    if shape == "circle":
        return 0.0
    if isinstance(shape, int) and shape > 2:
        seg = TAU / shape
        return round((rot % seg) / seg * 12) / 12 * seg
    return round(rot, 2)


def draw_player(surf, shape, cx, cy, r, t, look=(0.0, 0.0), mood="plain", rot=0.0,
                sx=1.0, sy=1.0, shadow=True, blink=False):
    """You: a prism. Clear light with every colour drifting through it."""
    if PIXEL_CHARACTERS and r >= 6:
        _pixel_character(surf, shape, cx, cy, r, WHITE, look, mood, rot, sx, sy, shadow, blink, None,
                         prism=True, t=t)
        return
    if shadow:
        draw_shadow(surf, cx, cy + r * 1.05, r * 1.9 * sx, r * 0.55)
    body_rot = _turn_step(shape, rot)           # (a rolling body turns in small steps: the light is cached)
    draw_body(surf, shape, cx, cy, r, WHITE, None, 0, body_rot, sx, sy)
    img = _prism_fill(shape, r, t * 0.5, body_rot, sx, sy)
    surf.blit(img, (int(cx - img.get_width() / 2), int(cy - img.get_height() / 2)))
    draw_body(surf, shape, cx, cy, r, None, INK, 3, body_rot, sx, sy)
    pygame.draw.circle(surf, WHITE, (int(cx - r * 0.35), int(cy - r * 0.3)), max(2, int(r * 0.14)))
    fx, fy = face_center(shape, cx, cy, r)
    fy = cy + r - (cy + r - fy) * sy
    spin = rot if (shape == "circle" or isinstance(shape, int)) else 0.0
    draw_eyes(surf, fx, fy, r, look, mood, blink, spin)


def blink_now(t, seed=0):
    """True for a short moment every few seconds (different per seed)."""
    period = 3.1 + (seed % 5) * 0.37
    return ((t + seed * 0.71) % period) < 0.12


# -------------------------------------------------------------- backgrounds

_GRADS = {}


def gradient(size, top, bottom):
    key = (size, top, bottom)
    g = _GRADS.get(key)
    if g is None:
        w, h = size
        g = pygame.Surface(size)
        for y in range(h):
            pygame.draw.line(g, mix(top, bottom, y / max(1, h - 1)), (0, y), (w, y))
        _GRADS[key] = g
    return g


class Confetti:
    """Slowly drifting soft shapes behind everything."""

    SHAPES = ("triangle", "square", "circle", "pentagon", "diamond", "hexagon")

    def __init__(self, rect, n=24, seed=7, colors=None, soft=0.45, size=(6, 16)):
        self.rect = pygame.Rect(rect)
        rng = random.Random(seed)
        cols = colors or [COLOR_RGB[c] for c in COLORS]
        self.items = []
        for _ in range(n):
            self.items.append([
                rng.uniform(self.rect.left, self.rect.right),
                rng.uniform(self.rect.top, self.rect.bottom),
                rng.uniform(-6, 6), rng.uniform(8, 22),
                rng.uniform(0, TAU), rng.uniform(-0.8, 0.8),
                rng.uniform(*size), rng.choice(self.SHAPES),
                lighten(rng.choice(cols), soft)])

    def update(self, dt):
        r = self.rect
        for it in self.items:
            it[0] += it[2] * dt
            it[1] += it[3] * dt
            it[4] += it[5] * dt
            if it[1] - it[6] > r.bottom:
                it[1] = r.top - it[6]
            if it[0] < r.left - 20:
                it[0] = r.right + 10
            elif it[0] > r.right + 20:
                it[0] = r.left - 10

    def draw(self, surf):
        from .pixel import confetti_sprite
        for x, y, _vx, _vy, rot, _vr, size, shape, col in self.items:
            img = confetti_sprite(shape, size, col, rot)
            surf.blit(img, (int(x - img.get_width() / 2) // 2 * 2, int(y - img.get_height() / 2) // 2 * 2))


# ---------------------------------------------------------------- particles

class Particles:
    """Bits of colour and loose edges. Purely cosmetic."""

    def __init__(self):
        self.items = []

    def alive(self):
        return bool(self.items)

    def burst(self, x, y, color, n=10, speed=170, shapes=("circle", "triangle", "square"),
              size=(3, 6), rng=random):
        for _ in range(n):
            a = rng.uniform(0, TAU)
            v = rng.uniform(0.35, 1.0) * speed
            life = rng.uniform(0.45, 0.8)
            self.items.append({"k": "bit", "x": x, "y": y, "vx": math.cos(a) * v,
                               "vy": math.sin(a) * v - 60, "life": life, "max": life,
                               "c": color, "s": rng.choice(shapes),
                               "r": rng.uniform(*size), "rot": rng.uniform(0, TAU),
                               "vr": rng.uniform(-8, 8)})

    def edges(self, x, y, color, shape, r, rng=random):
        """A shape knocked loose: its sides fly apart as sticks."""
        pts = shape_points(shape, x, y, r) or regular_points(10, x, y, r)
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            out = math.atan2(my - y, mx - x)
            v = rng.uniform(120, 220)
            life = rng.uniform(0.6, 0.9)
            self.items.append({"k": "stick", "x": mx, "y": my,
                               "vx": math.cos(out) * v, "vy": math.sin(out) * v - 120,
                               "len": math.hypot(b[0] - a[0], b[1] - a[1]),
                               "rot": math.atan2(b[1] - a[1], b[0] - a[0]),
                               "vr": rng.uniform(-9, 9), "life": life, "max": life, "c": color})

    def ring(self, x, y, color, r0, r1, life=0.45):
        self.items.append({"k": "ring", "x": x, "y": y, "r0": r0, "r1": r1, "life": life,
                           "max": life, "c": color})

    def update(self, dt):
        keep = []
        for p in self.items:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            if p["k"] in ("bit", "stick"):
                p["vy"] += 520 * dt
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["rot"] += p["vr"] * dt
            keep.append(p)
        self.items = keep

    def draw(self, surf, ox=0.0, oy=0.0):
        """Draw, shifted by (ox, oy): particles made in world coordinates on
        a scrolling screen stay put in the world."""
        for p in self.items:
            f = p["life"] / p["max"]
            x, y = p["x"] + ox, p["y"] + oy
            if p["k"] == "bit":
                draw_body(surf, p["s"], x, y, max(1.5, p["r"] * (0.4 + 0.6 * f)),
                          p["c"], INK, 1, p["rot"])
            elif p["k"] == "stick":
                h = p["len"] / 2 * (0.5 + 0.5 * f)
                dx, dy = math.cos(p["rot"]) * h, math.sin(p["rot"]) * h
                a = (x - dx, y - dy)
                b = (x + dx, y + dy)
                pygame.draw.line(surf, INK, a, b, 7)
                pygame.draw.line(surf, p["c"], a, b, 4)
            else:
                rr = p["r0"] + (p["r1"] - p["r0"]) * ease_out(1 - f)
                pygame.draw.circle(surf, p["c"], (int(x), int(y)), int(rr),
                                   max(1, int(5 * f)))


# ------------------------------------------------------------------ overlays

_HATCH = {}


def hatch(surf, rect, color, alpha=90, gap=10, width=4):
    """Diagonal danger stripes, used for every enemy telegraph."""
    key = (rect.w, rect.h, color, alpha, gap, width)
    s = _HATCH.get(key)
    if s is None:
        s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        s.fill((*color, alpha // 3))
        for k in range(-rect.h, rect.w, gap):
            pygame.draw.line(s, (*color, alpha), (k, rect.h), (k + rect.h, 0), width)
        _HATCH[key] = s
    surf.blit(s, rect.topleft)


def tint(surf, rect, color, alpha):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((*color, max(0, min(255, int(alpha)))))
    surf.blit(s, rect.topleft)


# --------------------------------------------------------------------- doors

def _door_sprite(shape, r, wall, locked, glow):
    """A slab of bricks with a shaped hole, painted at half size."""
    from . import pixel
    rr = max(4, int(r / 2))
    w, h = int(rr * 2.7) + 2, int(rr * 3.1) + 2

    def build():
        p = pixel.Pix(w, h, seed=3)
        p.bricks(1, 1, w - 2, h - 2, lighten(wall, 0.3), bw=7, bh=3, rough=0.15)
        rp = pixel.ramp(wall)
        p.rect(1, 1, w - 2, 1, rp[4])
        p.rect(1, h - 2, w - 2, 1, rp[0])
        c = (w / 2, h / 2)
        hole = (255, 250, 226) if not locked else darken(wall, 0.55)
        pts = pixel.critter_points(shape, c[0], c[1], rr * 0.85)
        rim = pixel.critter_points(shape, c[0], c[1], rr * 0.85 + 1)
        if pts is None:
            p.disc(c[0], c[1], rr * 0.85 + 1, rp[0])
            p.disc(c[0], c[1], rr * 0.85, hole)
        else:
            p.poly(rim, rp[0])
            p.poly(pts, hole)
        if not locked:
            inner = pixel.critter_points(shape, c[0], c[1], rr * 0.5)
            if inner:
                p.poly(inner, (255, 255, 255))
            else:
                p.disc(c[0], c[1], rr * 0.5, (255, 255, 255))
        p.outline()
        return p.up(2)
    return pixel.cached(("door", shape, rr, tuple(wall), locked, glow), build)


def draw_door(surf, shape, cx, cy, r, wall, t=0.0, open_amount=0.0, locked=True):
    """A slab of wall with a shaped hole cut through it (pixel art). The hole
    glows once it is open to you."""
    img = _door_sprite(shape, r, wall, locked, 0)
    slab = img.get_rect(center=(int(cx), int(cy)))
    surf.blit(img, slab.topleft)
    if not locked and open_amount > 0:
        hole = mix((255, 250, 220), (255, 255, 255), 0.5 + 0.5 * math.sin(t * 3))
        for i in range(3):
            rr = r * (0.9 + 0.25 * ((t * 0.8 + i / 3) % 1))
            draw_body(surf, shape, cx, cy, rr, None, lighten(hole, 0.3), 2)
    return slab
