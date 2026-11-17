"""Small animated scenes for the rooms that aren't fights, so a choice is
shown rather than described: Oddities (events) and the Still Tile (rest).

Each scene is a function draw(surf, stage, t, ctx) where ctx holds:
    hover     the choice under the mouse (a preview), or None
    chosen    the choice made, or None
    u         0..1 progress of the chosen outcome's animation
    info      facts about the outcome (which colour, which facet, did it work)
    effects   what the choice actually did (floats up as chips at the end)
    form      the shape Tri is right now
"""

import math
import random

import pygame

from .art import draw_body, draw_eyes, draw_player, draw_poly, draw_shadow, ease_in_out, ease_out, mix
from .consts import COLOR_RGB, RAINBOW
from .scene import draw_facet, draw_tinter, glint_icon, heart_icon
from .widgets import INK, PAPER, WHITE, draw_colour_mark, draw_text, font

def effect_chips(effects):
    """What effects do, as pictures: [(icon, text, extra)]."""
    chips = []
    for eff in effects:
        kind = eff[0]
        if kind == "heal":
            chips.append(("heart", "+%d" % eff[1], None))
        elif kind == "hp":
            chips.append(("heart", "%d" % eff[1], None))
        elif kind == "maxhp":
            chips.append(("heart", "%+d max" % eff[1], None))
        elif kind == "cap":
            chips.append(("pip", "%+d" % eff[2], eff[1]))
        elif kind == "glint":
            chips.append(("glint", "%+d" % eff[1], None))
        elif kind == "facet":
            chips.append(("facet", "", eff[1]))
        elif kind == "gamble":
            chips.append(("dice", "%d%%" % (eff[1] * 100), None))
            chips += effect_chips(eff[2])
            chips.append(("or", "", None))
            chips += effect_chips(eff[3])
    return chips or [("walk", "", None)]


def draw_chip(surf, x, y, kind, text, extra=None):
    """An outcome as a picture: a heart, a glint, a colour pip, a facet..."""
    cx, cy = x + 10, y + 10
    if kind == "heart":
        heart_icon(surf, cx, cy, 9)
    elif kind == "glint":
        glint_icon(surf, cx, cy, 9)
    elif kind == "pip":
        col = COLOR_RGB[extra] if extra else COLOR_RGB[RAINBOW[int(pygame.time.get_ticks() / 400) % 6]]
        pygame.draw.circle(surf, col, (cx, cy), 8)
        pygame.draw.circle(surf, INK, (cx, cy), 8, 2)
        draw_colour_mark(surf, extra, cx, cy, 8)
    elif kind == "facet":
        draw_facet(surf, extra, cx, cy, 9)
    elif kind == "dice":
        r = pygame.Rect(cx - 8, cy - 8, 16, 16)
        pygame.draw.rect(surf, WHITE, r, border_radius=4)
        pygame.draw.rect(surf, INK, r, 2, border_radius=4)
        pygame.draw.circle(surf, INK, (cx - 3, cy - 3), 2)
        pygame.draw.circle(surf, INK, (cx + 3, cy + 3), 2)
    elif kind == "walk":
        pygame.draw.polygon(surf, INK, [(cx - 7, cy - 7), (cx + 8, cy), (cx - 7, cy + 7)])
    elif kind == "or":
        r = draw_text(surf, font(18), "or", (x, y + 3), INK)
        return r.right + 2
    w = 22
    if text:
        col = (200, 40, 80) if text.startswith("-") else INK
        r = draw_text(surf, font(22), text, (x + 22, y + 2), col)
        w = r.right - x + 6
    return x + w


# ------------------------------------------------------------------ shared

def _room(size, tiles):
    """The back wall of the Sorter in bricks, and its tiled floor (pixel art, cached)."""
    from . import board_art, pixel
    w, h = size

    def build():
        ground = h - 70
        wall = mix(tiles[1], (120, 90, 160), 0.12)
        p = pixel.Pix(w // 2, h // 2, seed=2)
        p.bricks(0, 0, w // 2, ground // 2, mix(wall, WHITE, 0.2), bw=17, bh=8, rough=0.2)
        img = p.up(2)
        floor = board_art.floor_tile(56, tiles[0], "tile")
        for gx in range(0, w, 56):
            img.blit(floor, (gx, ground + 2))
        pygame.draw.line(img, INK, (0, ground), (w, ground), 3)
        return img
    return pixel.cached(("vignette_room", size, tuple(tiles[0]), tuple(tiles[1])), build)


def _window(t):
    """A round window onto the Meadow, far below (painted small), with tiny
    circles rolling about in it: the reason for all of this."""
    from . import pixel
    p = pixel.Pix(56, 56)
    p.vgrad(0, 0, 56, 56, (130, 196, 255), (210, 240, 255), 4)
    p.disc(40, 13, 6, (255, 236, 140))
    p.ellipse(-15, 33, 85, 40, (104, 206, 96))
    p.ellipse(15, 39, 65, 35, (130, 220, 110))
    for i, c in enumerate(("Y", "R", "C")):
        x = (t * (9 + i * 3.5) + i * 25) % 75 - 10
        p.disc(x, 40 + i * 3, 2, COLOR_RGB[c])
    mask = pygame.Surface((56, 56), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (28, 28), 27)
    p.s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    p.ring(28, 28, 27, (190, 160, 120), 2)
    p.outline()
    return p.up(2)


def _floor(surf, stage, tiles=((255, 241, 222), (255, 230, 204))):
    """The back wall of the Sorter (bricks, with a round window onto the
    Meadow) and the floor in front of it. Returns the floor's height."""
    ground = stage.bottom - 70
    surf.blit(_room(stage.size, tiles), stage.topleft)
    t = pygame.time.get_ticks() / 1000.0
    surf.blit(_window(t), (stage.right - 174, stage.y + 26))
    return ground


def _tri(surf, ctx, x, ground, t, mood="plain", look=(1, 0), hop=0.0, r=30, rot=0.0, glow=None):
    if glow:
        size = int(r * 4)
        halo = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(5):
            pygame.draw.circle(halo, (*glow, 30 + i * 14), (size // 2, size // 2),
                               int(r * (2 - i * 0.22) + math.sin(t * 4) * 3))
        surf.blit(halo, (int(x - size / 2), int(ground - r - hop - size / 2)))
    draw_player(surf, ctx["form"], x, ground - r - hop, r, t, look=look, mood=mood, rot=rot)


def _arrow(surf, a, b, t):
    """A dotted hint of where a choice would take you."""
    n = 10
    for k in range(n):
        f = (k + (t * 2) % 1) / n
        x = a[0] + (b[0] - a[0]) * f
        y = a[1] + (b[1] - a[1]) * f - math.sin(f * math.pi) * 40
        pygame.draw.circle(surf, INK, (int(x), int(y) + 1), 5)
        pygame.draw.circle(surf, WHITE, (int(x), int(y)), 4)


def rise_outcome(surf, stage, ctx):
    """At the end of every scene, what actually happened floats up as chips."""
    u = ctx["u"]
    effects = ctx.get("effects") or []
    if u < 0.65 or not effects:
        return
    k = ease_out(min(1, (u - 0.65) / 0.35))
    chips = effect_chips(effects)
    w = sum(40 + font(22).size(txt)[0] for _, txt, _ in chips) + 16
    box = pygame.Rect(0, 0, w, 32)
    box.center = (stage.centerx, int(stage.y + 90 - 40 * k))
    pygame.draw.rect(surf, INK, box.move(0, 3), border_radius=16)
    pygame.draw.rect(surf, PAPER, box, border_radius=16)
    pygame.draw.rect(surf, INK, box, 2, border_radius=16)
    x = box.x + 10
    for kind, txt, extra in chips:
        x = draw_chip(surf, x, box.y + 6, kind, txt, extra) + 10


def _sparks(surf, x, y, t, col, n=8, rad=30, seed=0):
    rng = random.Random(seed)
    for i in range(n):
        a = rng.uniform(0, math.tau) + t * rng.uniform(1, 3)
        rr = rad * (0.5 + 0.5 * ((t * 1.7 + i / n) % 1))
        pygame.draw.circle(surf, col, (int(x + math.cos(a) * rr), int(y + math.sin(a) * rr)), 3)


def _walk_off(surf, ctx, ground, t, home):
    u = ctx["u"]
    x = home + ease_in_out(u) * 700
    _tri(surf, ctx, x, ground, t, hop=abs(math.sin(u * math.pi * 6)) * 10)


# ------------------------------------------------------------------ scenes

def draw_polisher(surf, cx, ground, t, scrub=0.0, mood="happy"):
    """The Polisher: a cheerful octagon in goggles, polishing cloth in hand.
    It buffs new facets onto shapes that want them."""
    r = 58
    cy = ground - r - 4
    bob = math.sin(t * 2.4) * 3
    draw_shadow(surf, cx, ground, 120, 22)
    draw_body(surf, 8, cx, cy + bob, r, (255, 214, 120), INK, 4, t * 0.05)
    draw_body(surf, 8, cx, cy + bob + 3, r * 0.8, None, (255, 236, 180), 3, t * 0.05)
    draw_eyes(surf, cx, cy + bob - 4, 46, (-1, 0.1), mood)
    for side in (-1, 1):                                    # goggles pushed up on its head
        pygame.draw.circle(surf, (150, 220, 255), (int(cx + side * 16), int(cy + bob - 38)), 11)
        pygame.draw.circle(surf, INK, (int(cx + side * 16), int(cy + bob - 38)), 11, 3)
    pygame.draw.line(surf, INK, (cx - 5, cy + bob - 38), (cx + 5, cy + bob - 38), 3)
    # the cloth, held out front (it flaps when scrubbing)
    hx = cx - r - 10 + math.sin(scrub * 40) * 16 * (1 if scrub else 0)
    hy = cy + bob + 10
    flap = math.sin(t * 6) * 6
    cloth = [(hx, hy), (hx - 34, hy - 6 + flap), (hx - 30, hy + 22 + flap), (hx + 2, hy + 24)]
    draw_poly(surf, cloth, (120, 220, 255), INK, 3)


def polisher(surf, stage, t, ctx):
    """The Polisher buffs a facet (a lasting bonus) onto you. It tickles."""
    ground = _floor(surf, stage)
    home = stage.x + 170
    cx = stage.x + 500
    chosen, u = ctx["chosen"], ctx["u"]
    polishing = chosen in ("polish", "polish2")
    scrub = u if polishing and 0.35 < u < 0.7 else 0.0
    draw_polisher(surf, cx, ground, t, scrub, "happy")
    rel = ctx["info"].get("relic")
    if polishing:
        x = home + ease_in_out(min(1, u / 0.35)) * (cx - 130 - home)
        giggle = math.sin(t * 30) * 3 if scrub else 0
        _tri(surf, ctx, x, ground, t, mood="happy" if u > 0.35 else "wow", hop=abs(giggle))
        if scrub:
            _sparks(surf, x, ground - 40, t * 3, (255, 250, 200), 12, 34, 2)
        if u > 0.6 and rel:                                   # the new facet, shining
            k = ease_out(min(1, (u - 0.6) / 0.3))
            draw_facet(surf, rel, x, ground - 70 - 30 * (1 - k), 10 + 4 * k, t)
    elif chosen == "leave":
        _walk_off(surf, ctx, ground, t, home)
    else:
        _tri(surf, ctx, home, ground, t, look=(1, -0.3))
        if ctx["hover"] in ("polish", "polish2"):
            _arrow(surf, (home + 30, ground - 40), (cx - 130, ground - 40), t)
    rise_outcome(surf, stage, ctx)


def trader(surf, stage, t, ctx):
    """A Drifting Tinter clunks up, full of light, wanting glint."""
    ground = _floor(surf, stage)
    home = stage.x + 170
    tx = stage.x + 500
    chosen, u = ctx["chosen"], ctx["u"]
    info = ctx["info"]
    if chosen == "leave":
        tx += ease_in_out(u) * 500
    bob = abs(math.sin(t * 3)) * 6
    tilt = 0.0
    if chosen == "buy" and 0.35 < u < 0.85:
        tilt = 0.5
    draw_tinter(surf, tx, ground - 80 - bob, 60, t + tilt, look=(-1, 0.2))
    if chosen in ("buy", "sample"):
        _tri(surf, ctx, home, ground, t, mood="happy" if u > 0.7 else "plain")
        if u < 0.4 and chosen == "buy":               # glint flies over
            for i in range(5):
                f = (u / 0.4 + i * 0.12) % 1
                x = home + (tx - home) * f
                glint_icon(surf, x, ground - 80 - math.sin(f * math.pi) * 60, 7)
        elif u < 0.85:                                # a stream of warm light pours on you
            for i in range(14):
                f = ((t * 2 + i / 14) % 1)
                x = tx - 50 + (home - tx + 50) * f
                y = ground - 120 - math.sin(f * math.pi) * 50 + f * 40
                pygame.draw.circle(surf, (255, 214, 72), (int(x), int(y)), 5)
    elif chosen == "change":                           # it overpaid you for looking
        _tri(surf, ctx, home, ground, t, mood="happy" if u > 0.5 else "wow")
        for i in range(6):
            f = min(1, max(0, u * 1.6 - i * 0.1))
            if 0 < f < 1:
                glint_icon(surf, tx + (home - tx) * f, ground - 90 - math.sin(f * math.pi) * 70, 7)
    elif chosen == "haggle":
        # back and forth... then the glint goes one way or the other
        ok = info.get("ok")
        x = home + ease_in_out(min(1, u / 0.3)) * (tx - 110 - home)
        mood = "wow" if u < 0.55 else ("happy" if ok else "plain")
        _tri(surf, ctx, x, ground, t, mood=mood, hop=abs(math.sin(u * 18)) * 6 if u < 0.55 else 0)
        if 0.3 < u < 0.55:
            for k in range(3):
                pygame.draw.circle(surf, INK, (int((x + tx) / 2 - 12 + k * 12),
                                               int(ground - 120 + math.sin(t * 8 + k) * 3)), 3)
        if u > 0.55:
            f = min(1.0, (u - 0.55) / 0.35)
            a, b = ((tx - 40, x) if ok else (x, tx - 40))
            for i in range(4):
                ff = min(1.0, max(0.0, f * 1.4 - i * 0.12))
                if 0 < ff < 1:
                    glint_icon(surf, a + (b - a) * ff, ground - 90 - math.sin(ff * math.pi) * 50, 6)
    elif chosen == "leave":
        _tri(surf, ctx, home, ground, t, look=(1, 0))
    else:
        _tri(surf, ctx, home, ground, t, look=(1, 0))
        if ctx["hover"] in ("buy", "haggle", "sample", "change"):
            _arrow(surf, (home + 30, ground - 40), (tx - 70, ground - 40), t)
    rise_outcome(surf, stage, ctx)


def well(surf, stage, t, ctx):
    """A Pool of Colour: loose colour swirling in a dip in the floor."""
    ground = _floor(surf, stage)
    home = stage.x + 170
    px = stage.x + 480
    chosen, u = ctx["chosen"], ctx["u"]
    col = ctx["info"].get("color")
    drain = ease_in_out(max(0, (u - 0.2) / 0.6)) if chosen == "drink" else 0.0
    pool = pygame.Rect(0, 0, 280, 70)
    pool.center = (px, ground + 30)
    pygame.draw.ellipse(surf, INK, pool.inflate(8, 8))
    pygame.draw.ellipse(surf, (250, 246, 255), pool)
    for i, c in enumerate(RAINBOW):
        a = t * 0.8 + i * math.tau / 6
        rr = (1 - drain) * 1.0
        blob = pygame.Rect(0, 0, int(70 * rr) + 1, int(26 * rr) + 1)
        blob.center = (int(px + math.cos(a) * 80 * rr), int(ground + 30 + math.sin(a) * 16 * rr))
        pygame.draw.ellipse(surf, COLOR_RGB[c], blob)
    if chosen == "drink":
        x = home + ease_in_out(min(1, u / 0.25)) * (px - 170 - home)
        glow = COLOR_RGB[col] if (col and u > 0.6) else None
        _tri(surf, ctx, x, ground, t, mood="wow" if u < 0.8 else "happy", glow=glow)
        if 0.2 < u < 0.85:                            # colour streams up into you
            for i in range(12):
                f = ((t * 1.6 + i / 12) % 1)
                sx = px + (x - px) * f
                sy = ground + 20 - (50 * f) - math.sin(f * math.pi) * 30
                pygame.draw.circle(surf, COLOR_RGB[RAINBOW[i % 6]], (int(sx), int(sy)), 5)
    elif chosen == "bathe":
        k = ease_in_out(min(1, u / 0.4))
        x = home + k * (px - home)
        y = ground - k * -14 + math.sin(t * 2) * 3 * k
        _tri(surf, ctx, x, y, t, mood="sleep" if u > 0.5 else "happy", hop=math.sin(k * math.pi) * 60)
    elif chosen == "leave":
        _walk_off(surf, ctx, ground, t, home)
    else:
        _tri(surf, ctx, home, ground, t, look=(1, 0.3))
        if ctx["hover"] in ("drink", "bathe"):
            _arrow(surf, (home + 30, ground - 40), (px - (150 if ctx["hover"] == "drink" else 0),
                                                    ground - 30), t)
    rise_outcome(surf, stage, ctx)


def rest(surf, stage, t, ctx):
    """A Still Tile: the one tile in the Sorter where nothing clicks."""
    ground = _floor(surf, stage, ((236, 248, 240), (222, 240, 228)))
    cx = stage.centerx
    tile = pygame.Rect(0, 0, 150, 40)
    tile.center = (cx, ground + 4)
    glow = 0.5 + 0.5 * math.sin(t * 1.5)
    pygame.draw.ellipse(surf, mix((200, 255, 220), WHITE, glow), tile.inflate(40, 18))
    pygame.draw.rect(surf, (150, 230, 170), tile, border_radius=10)
    pygame.draw.rect(surf, INK, tile, 3, border_radius=10)
    chosen, u = ctx["chosen"], ctx["u"]
    col = ctx["info"].get("color")
    if chosen == "heal":
        _tri(surf, ctx, cx, ground - 6, t, mood="sleep")
        for i in range(3):
            f = (t * 0.5 + i / 3) % 1
            draw_text(surf, font(28 + i * 4), "z", (cx + 40 + f * 40, ground - 90 - f * 80), INK)
    elif chosen == "focus":
        # light falls on you from far above and settles in as one more pip
        beam = pygame.Surface((120, ground - stage.y), pygame.SRCALPHA)
        beam.fill((*((255, 250, 200)), int(110 * min(1, u * 3))))
        surf.blit(beam, (cx - 60, stage.y))
        _tri(surf, ctx, cx, ground - 6, t, mood="wow" if u < 0.7 else "happy",
             glow=COLOR_RGB[col] if col and u > 0.5 else None)
    else:
        _tri(surf, ctx, cx, ground - 6, t, mood="sleep" if ctx["hover"] == "heal" else "plain",
             look=(0, -0.5) if ctx["hover"] == "focus" else (0, 0))
        if ctx["hover"] == "focus":
            _sparks(surf, cx, ground - 120, t, (255, 226, 92), 10, 40, 4)
    rise_outcome(surf, stage, ctx)


SCENES = {"polisher": polisher, "trader": trader, "well": well, "rest": rest}


def draw_scene(surf, stage, name, t, ctx):
    SCENES[name](surf, stage, t, ctx)

