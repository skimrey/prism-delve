"""The story scenes: the intro, growing a side between floors, and the roll.

These are the only places in the game where anything moves smoothly instead
of in grid clicks, and the roll at the end is the only real rolling there is.
That contrast is the point: the grid is what Tri is escaping.
"""

import math
import random

import pygame

from .art import (Particles, blink_now, draw_body, draw_critter, draw_door, draw_eyes, draw_player,
                  draw_poly, draw_shadow, ease_in_out, ease_out, gradient, lighten, mix)
from .consts import COLOR_NAMES, COLOR_RGB, COLORS, FLOORS, FORMS, PATTERNS, RAINBOW, TOWERS, TWISTS, twist_name
from .scene import (GRASS, MEADOW_SKY, SCREEN, TITLE_SKY, Backdrop,
                    draw_pattern_icon, draw_portal, draw_tower, floor_style,
                    heading, keeper_kind, morph_points)
from .enemies import KINDS
from . import sound
from .screens import Screen
from .pixel import draw_morph
from .world import FRIEND_START, ROUND_ENOUGH, shape_of
from .towers_art import draw_tower_art
from .widgets import ACCENT, DIM, INK, PAPER, WHITE, draw_card, draw_text, draw_wrapped, font, wrap_text

ADVANCE_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT, pygame.K_KP_ENTER)
VOID = (24, 16, 52)            # the dark before the colours, on the first card
DOOR_SUCK = 3.2                # when the Round Door takes you in


# -------------------------------------------------------------------- intro

# (words, the scene that goes with them, stage colour)
STORY = [
    ("In the beginning there was only shape and colour.", "_void", "void"),
    ("Everything with corners lives in the Sorter: a tower of floors, and every door in it is "
     "cut for exactly one shape.", "_sorter", None),
    ("This is Tri. Tri is a triangle, and also a prism: light goes in white and comes out as "
     "colour.", "_tri", None),
    ("Corners catch, so everything in the Sorter moves in clicks. Only circles move smoothly. "
     "Circles roll out through the Round Door, down the Long Ramp, into the Meadow.", "_clicks",
     None),
    ("Tri wants to roll, and that takes more sides. Each floor's Keeper holds a spare one. At the "
     "very top waits the Stillwheel, the one circle that never rolled, keeping the Round Door "
     "shut.", "_keepers", "dusk"),
    ("And everywhere in between are the Set, who like every shape exactly as it was cut. They "
     "will try to knock Tri back into its slot.", "_set", "stage"),
]
STAGE_FILL = {"void": VOID, "dusk": (52, 40, 92), "stage": (70, 34, 96)}


class StoryScreen(Screen):
    """A few cards, each with a small moving picture. `then` runs at the end."""

    LAST = "Start climbing"

    def __init__(self, app, then, pages=STORY):
        super().__init__(app)
        self.then = then
        self.pages = pages
        self.page = 0
        self.page_t = 0.0
        self.backdrop = Backdrop(TITLE_SKY, seed=21, n=26, soft=0.3)
        self.next_btn = self.add((600, 560, 200, 46), "Next", self.advance, tag="next")
        self.add((160, 566, 140, 36), "Skip", self.finish, key=pygame.K_ESCAPE, tag="skip", small=True)

    def advance(self):
        if self.page >= len(self.pages) - 1:
            self.finish()
            return
        self.page += 1
        self.page_t = 0.0
        if self.page == len(self.pages) - 1:
            self.next_btn.label = self.LAST
        self.app.dirty = True

    def finish(self):
        self.app.meta.data["seen_intro"] = True
        self.app.meta.save()
        self.then()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in ADVANCE_KEYS:
            self.advance()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.button_at(ev.pos) is None:
            self.advance()
            return True
        return super().handle(ev)

    def update(self, dt):
        self.backdrop.update(dt)
        self.page_t += dt
        return super().update(dt)

    def draw(self, surf):
        self.backdrop.draw(surf)
        words, scene, fill = self.pages[self.page]
        stage = draw_card(surf, (130, 40, 700, 360), STAGE_FILL.get(fill, PAPER), 20)
        surf.set_clip(stage.inflate(-6, -6))
        getattr(self, scene)(surf, stage, self.page_t)
        surf.set_clip(None)
        f = font(28)
        lines = len(wrap_text(f, words, 660))
        band = pygame.Surface((700, lines * (f.get_height() + 3) + 12), pygame.SRCALPHA)   # a soft band so
        pygame.draw.rect(band, (*INK, 96), band.get_rect(), border_radius=16)       # the words read over
        surf.blit(band, (130, 404))                                                  # the confetti
        draw_wrapped(surf, font(28), words, (150, 412), 660, WHITE, 3, center=True, shadow=INK)
        n = len(self.pages)
        for i in range(n):
            c = WHITE if i == self.page else lighten(INK, 0.5)
            pygame.draw.circle(surf, c, (480 - (n - 1) * 12 + i * 24, 530), 6)
            pygame.draw.circle(surf, INK, (480 - (n - 1) * 12 + i * 24, 530), 6, 2)
        self.draw_buttons(surf)

    # each page is a little scene
    def _void(self, surf, r, t):
        """The beginning: a point of white light, a flash, rings of colour,
        and shapes flung out of it, settling into a slow spiral."""
        cx, cy = r.center
        rng = random.Random(1)
        bang = 0.9                                    # when the point bursts
        if t < bang:                                  # the point, gathering
            k = t / bang
            for i in range(5):
                pygame.draw.circle(surf, mix(VOID, WHITE, 0.15 * (i + 1)), (cx, cy),
                                   int((5 - i) * 6 * k + 2))
            pygame.draw.circle(surf, WHITE, (cx, cy), int(3 + 4 * k + math.sin(t * 30) * 1.5))
            return
        u = t - bang
        # the stars: tiny specks of every colour, twinkling
        for i in range(60):
            sx, sy = rng.uniform(r.x, r.right), rng.uniform(r.y, r.bottom)
            tw = 0.5 + 0.5 * math.sin(t * 3 + i)
            if tw > 0.3:
                pygame.draw.circle(surf, mix(VOID, COLOR_RGB[RAINBOW[i % 6]], tw), (int(sx), int(sy)), 2)
        # rings of colour rolling outward
        for i, c in enumerate(RAINBOW):
            rad = (u * 260 - i * 26)
            if 0 < rad < 520:
                pygame.draw.circle(surf, COLOR_RGB[c], (cx, cy), int(rad), max(2, int(8 - rad / 80)))
        # shapes flung out, then swinging into a spiral around the light
        for i in range(48):
            a = rng.uniform(0, math.tau)
            spin = rng.uniform(0.2, 0.5) * (1 if i % 2 else -1)
            home = 50 + (i % 8) * 22
            rad = home * ease_out(min(1, u / 1.4))
            a2 = a + spin * u
            x = cx + math.cos(a2) * rad * 1.45
            y = cy + math.sin(a2) * rad * 0.78
            shape = ("triangle", "square", "circle", "pentagon", "hexagon", "diamond")[i % 6]
            size = (6 + (i % 4) * 3) * min(1, u * 2)
            draw_body(surf, shape, x, y, size, COLOR_RGB[RAINBOW[i % 6]], INK, 2, a2 * 2)
        # the light itself, and a flash as it breaks open
        glow = 14 + 4 * math.sin(t * 4)
        for i in range(4):
            pygame.draw.circle(surf, mix(VOID, WHITE, 0.25 * (i + 1)), (cx, cy), int(glow * (4 - i) * 0.6))
        if u < 0.35:
            flash = pygame.Surface(r.size, pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(255 * (1 - u / 0.35))))
            surf.blit(flash, r.topleft)

    def _sorter(self, surf, r, t):
        draw_tower(surf, (r.centerx - 80, r.y + 20, 170, 330), 1, t)
        for i, shape in enumerate(("triangle", "square", "pentagon", "circle")):
            x = r.x + 70 + (i % 2) * 90 if i < 2 else r.right - 160 + (i % 2) * 90
            draw_door(surf, shape, x, r.centery, 26, (120, 100, 200) if i < 3 else (255, 170, 80),
                      t, 0, locked=True)

    def _tri(self, surf, r, t):
        cx, cy = r.centerx - 60, r.centery + 10
        # white light in
        pygame.draw.line(surf, INK, (r.x, cy - 40), (cx - 20, cy), 12)
        pygame.draw.line(surf, WHITE, (r.x, cy - 40), (cx - 20, cy), 8)
        # colour out, fanning
        for i, c in enumerate(COLORS):
            a = -0.35 + i * 0.14
            ln = 300 * ease_out(min(1, t / 1.2))
            end = (cx + 20 + math.cos(a) * ln, cy + math.sin(a) * ln)
            pygame.draw.line(surf, COLOR_RGB[c], (cx + 20, cy), end, 9)
        draw_player(surf, "triangle", cx, cy, 56, t, look=(1, 0), blink=blink_now(t, 2))

    def _clicks(self, surf, r, t):
        # bottom lane: a square clicks along by tipping over its corner
        ground = r.bottom - 50
        pygame.draw.line(surf, INK, (r.x, ground), (r.right, ground), 4)
        side = 50
        k = t * 1.1
        n, f = int(k), ease_in_out(min(1, (k % 1) * 1.6))
        x0 = r.x + 40 + (n % 11) * side            # left edge of the square at rest
        pivot = (x0 + side, ground)
        ang = f * math.pi / 2                       # clockwise on screen (y points down)
        cs, sn = math.cos(ang), math.sin(ang)
        pts = []
        for px, py in ((x0, ground - side), (x0 + side, ground - side), (x0 + side, ground),
                       (x0, ground)):
            dx, dy = px - pivot[0], py - pivot[1]
            pts.append((pivot[0] + dx * cs - dy * sn, pivot[1] + dx * sn + dy * cs))
        draw_poly(surf, pts, COLOR_RGB["R"], INK, 3)
        if f >= 1:
            draw_text(surf, font(26), "click", (x0 + side * 1.5, ground - side - 22), INK, center=True)
        draw_text(surf, font(22), "corners: click, click, click", (r.x + 16, ground + 10), DIM)
        # top lane: a circle rolls, smoothly, forever
        y2 = r.y + 110
        pygame.draw.line(surf, INK, (r.x, y2 + 32), (r.right, y2 + 32), 4)
        x = r.x + ((t * 180) % (r.w + 80)) - 40
        draw_player(surf, "circle", x, y2, 30, t, mood="happy", rot=(x - r.x) / 30)
        draw_text(surf, font(22), "no corners: rolls", (r.x + 16, y2 + 42), DIM)

    def _keepers(self, surf, r, t):
        """Three floors, three Keepers each holding a glowing spare side; the
        Stillwheel on top in front of the shut Round Door."""
        floors = ((1, "square", "Four-Keeper"), (2, "pentagon", "Five-Keeper"))
        for i, (act, shape, name) in enumerate(floors):
            style = floor_style(act)
            band = pygame.Rect(r.x + 20, r.bottom - 90 - i * 90, 420, 80)
            pygame.draw.rect(surf, lighten(style["sky"][0], 0.15), band, border_radius=10)
            pygame.draw.rect(surf, INK, band, 3, border_radius=10)
            kx = band.x + 90 + i * 40
            col = COLOR_RGB[RAINBOW[int(t * 0.8 + i * 2) % 6]]
            draw_critter(surf, shape, kx, band.centery + 6, 24, col, look=(1, 0),
                         face=("strict", "haughty")[i], mood="plain")
            # the spare side it holds, glowing
            glow = 0.5 + 0.5 * math.sin(t * 3 + i)
            a, b = (kx + 34, band.centery - 10), (kx + 80, band.centery - 30)
            pygame.draw.line(surf, mix((255, 240, 150), WHITE, glow), a, b, 14)
            pygame.draw.line(surf, INK, a, b, 3)
            draw_text(surf, font(20), name, (band.right - 14, band.y + 10), WHITE, right=True, shadow=INK)
        # the top: the Round Door, shut, and the Stillwheel in front of it
        top = pygame.Rect(r.x + 460, r.y + 24, 220, 310)
        pygame.draw.rect(surf, (40, 28, 76), top, border_radius=14)
        cx, cy = top.centerx, top.y + 110
        for i in range(6):
            rr = 64 - i * 9
            pygame.draw.circle(surf, COLOR_RGB[RAINBOW[(i + int(t * 2)) % 6]], (cx, cy), rr, 5)
        pygame.draw.circle(surf, (255, 250, 220), (cx, cy), 16)
        pygame.draw.line(surf, INK, (cx - 70, cy), (cx + 70, cy), 9)          # barred shut
        pygame.draw.line(surf, (200, 160, 110), (cx - 70, cy), (cx + 70, cy), 5)
        roll = math.sin(t * 0.9) * 0.15                                     # it rocks, but never rolls
        draw_critter(surf, "circle", cx, top.bottom - 70, 40, (150, 140, 170), look=(-0.6, 0.2),
                     rot=roll, face="melancholy", mood="plain")
        for i, c in enumerate(RAINBOW):
            a = t * 1.2 + i * math.tau / 6
            pygame.draw.circle(surf, COLOR_RGB[c], (int(cx + math.cos(a) * 54),
                                                    int(top.bottom - 70 + math.sin(a) * 20 + 24)), 5)
        draw_text(surf, font(22), "the Stillwheel", (cx, top.bottom - 16), WHITE, center=True, shadow=INK)

    def _set(self, surf, r, t):
        """The Set: squads marching in step out of the dark, stomping on the
        beat, between Tri and the Round Door."""
        ground = r.bottom - 40
        # spotlights on the dark stage
        for i, x in enumerate((r.x + 250, r.x + 450)):
            beam = pygame.Surface(r.size, pygame.SRCALPHA)
            sway = math.sin(t * 0.9 + i * 2) * 60
            pygame.draw.polygon(beam, (255, 240, 200, 38),
                                [(x - r.x + sway, 0), (x - r.x + sway + 30, 0),
                                 (x - r.x + 110, r.h), (x - r.x - 80, r.h)])
            surf.blit(beam, r.topleft)
        pygame.draw.rect(surf, (48, 22, 70), (r.x, ground, r.w, r.bottom - ground))
        pygame.draw.line(surf, INK, (r.x, ground), (r.right, ground), 4)
        door_x = r.right - 70
        draw_door(surf, "circle", door_x, ground - 80, 40, (255, 170, 80), t, 1.0, locked=False)
        # the beat: everyone steps together, a click every 0.6s
        beat = t / 0.6
        hop = abs(math.sin(beat * math.pi)) * 8
        march = min(4, int(beat)) * 14 + ease_in_out(min(1, beat % 1)) * 14 if beat < 4 else 56
        squads = (("circle", "G"), ("triangle", "B"), ("square", "R"))      # back row first
        for row, (shape, col) in enumerate(squads):
            depth = 2 - row
            for k in range(4):
                x = r.x + 540 - k * 60 - march + depth * 22
                y = ground - 26 - depth * 54 - hop * (1 if (k + row) % 2 == 0 else 0.6)
                draw_critter(surf, shape, x, y, 22, COLOR_RGB[col], look=(-1, 0.1),
                             sx=1 + hop * 0.01, sy=1 - hop * 0.01, mark=("sprout", "horn", "feet")[row])
        draw_player(surf, "triangle", r.x + 70, ground - 28, 26, t, look=(1, -0.2),
                    mood="wow" if int(beat) % 4 == 3 else "plain", blink=blink_now(t, 5))
        # a shout, now and then
        lines = ("Back in your slot!", "Stay as you were cut!", "Hole-maker!")
        n = int(t / 1.8)
        if (t % 1.8) < 1.3:
            text = lines[n % 3]
            f = font(20)
            w = f.size(text)[0] + 20
            box = pygame.Rect(r.x + 300 - w // 2 + (n % 3) * 60, r.y + 24 + (n % 2) * 30, w, 30)
            pygame.draw.rect(surf, WHITE, box, border_radius=10)
            pygame.draw.rect(surf, INK, box, 2, border_radius=10)
            draw_text(surf, f, text, box.center, INK, center=True)


# -------------------------------------------------------------- tower intro

def _bubble(surf, text, anchor, width=260, size=20, clamp=None):
    """A speech bubble whose tail points at `anchor` (it sits above it)."""
    from .widgets import wrap_text
    f = font(size)
    lines = wrap_text(f, text, width)
    w = max(f.size(line)[0] for line in lines) + 22
    h = len(lines) * (f.get_height() + 2) + 14
    box = pygame.Rect(0, 0, w, h)
    box.midbottom = (int(anchor[0]), int(anchor[1]) - 12)
    if clamp is not None:
        box.clamp_ip(clamp)
    tail = [(anchor[0] - 8, box.bottom - 2), (anchor[0] + 8, box.bottom - 2), anchor]
    pygame.draw.polygon(surf, INK, [(x, y + 2) for x, y in tail])
    pygame.draw.rect(surf, WHITE, box, border_radius=12)
    pygame.draw.rect(surf, INK, box, 2, border_radius=12)
    pygame.draw.polygon(surf, WHITE, tail)
    y = box.y + 7
    for line in lines:
        draw_text(surf, f, line, (box.centerx, y + f.get_height() // 2), INK, center=True)
        y += f.get_height() + 2


class TowerIntroScreen(StoryScreen):
    """The first time you go in through a tower's window: who asked you to
    come, what's different as a sphere, and who keeps the window shut. The
    cards come from the tower's data (consts.TOWERS[id]["intro"])."""

    LAST = "Up we go!"

    def __init__(self, app, tower, then):
        self.tower = tower
        self.data = TOWERS[tower]
        from .world import your_sides
        self.you = shape_of(your_sides(app.meta.data, getattr(app, "hub_rescued", None)))
        super().__init__(app, then, pages=self.data["intro"])

    def finish(self):
        seen = self.app.meta.data.setdefault("towers_seen", [])
        if self.tower not in seen:
            seen.append(self.tower)
        self.app.meta.save()
        self.then()

    def _sky(self, surf, r):
        top, bottom = self.data["sky"]
        surf.blit(gradient(r.size, top, bottom), r.topleft)

    def _asker(self, surf, r, t):
        """The tower, painted; the friend at its window, waving; you, down
        in the grass, looking up."""
        self._sky(surf, r)
        ground = r.bottom - 40
        pygame.draw.rect(surf, GRASS, (r.x, ground, r.w, r.bottom - ground))
        pygame.draw.line(surf, INK, (r.x, ground), (r.right, ground), 3)
        friend = self.data["friend"]
        win, rr = draw_tower_art(surf, self.tower, r.centerx + 70, ground + 2, 2, t,
                                 friend=(friend["was"], COLOR_RGB[friend["color"]]))
        if (t % 5.0) > 0.6:
            _bubble(surf, self.data["plea"], (win[0] - 30, win[1] - rr - 4), width=230,
                    clamp=r.inflate(-16, -16))
        x = r.x + 120 + math.sin(t * 2.2) * 14                   # you, rocking on the spot
        draw_player(surf, self.you, x, ground - 30, 30, t, look=(0.7, -0.8), mood="happy",
                    rot=math.sin(t * 2.2) * 0.6)
        draw_text(surf, font(20), "a %s, at the window" % friend["was"], (win[0] + rr + 14, win[1] + 10),
                  WHITE, shadow=INK)

    def _mini_board(self, surf, r, cols, rows, size, special=None, holes=()):
        """A little strip of this tower's floor, in the same pixel tiles as a fight."""
        from . import board_art
        material = board_art.material_for(self.tower)
        x0 = r.centerx - cols * size // 2
        y0 = r.y + 70
        frame = int(self.t * 6)
        for gy in range(rows):
            for gx in range(cols):
                tile = board_art.floor_tile(size, self.data["tiles"][(gx + gy) % 2], material, (gx + gy) % 3)
                surf.blit(tile, (x0 + gx * size, y0 + gy * size))
        for a, b in holes:
            for tile in (a, b):
                surf.blit(board_art.hole_tile(size, 0, frame, sea=self.tower == "lighthouse"), (x0 + tile[0] * size, y0 + tile[1] * size))
        for (gx, gy), kind in (special or {}).items():
            surf.blit(board_art.special_tile(size, kind, frame), (x0 + gx * size, y0 + gy * size))
        return x0, y0

    def _sphere(self, surf, r, t):
        """Two rows of tiles. Top: how the old you moved, a click a beat.
        Bottom: a sphere rolls until a shape stops it, and bumps it along."""
        pygame.draw.rect(surf, lighten(self.data["wall"], 0.55), r)
        size, n = 56, 9
        x0, y0 = self._mini_board(surf, r, n, 1, size)
        y1 = y0 + 154
        from . import board_art
        for gx in range(n):
            tile = board_art.floor_tile(size, self.data["tiles"][(gx + 1) % 2], board_art.material_for(self.tower),
                                        gx % 3)
            surf.blit(tile, (x0 + gx * size, y1))
        loop = t % 5.0
        cy_top, cy_low = y0 + size // 2, y1 + size // 2
        step = min(n - 1, int(loop / 0.55))
        hop = abs(math.sin((loop % 0.55) / 0.55 * math.pi)) * 8 if step < n - 1 else 0
        draw_player(surf, "triangle", x0 + step * size + size // 2, cy_top - hop, 20, t, look=(1, 0),
                    shadow=False)
        draw_text(surf, font(20), "before: click, click, click (one tile a beat)", (x0, y0 - 30), INK)
        draw_text(surf, font(20), "now: ROLL until something stops you", (x0, y1 - 30), INK)
        stop_at, shape_at = 5, 6
        roll_t = ease_in_out(min(1.0, max(0.0, (loop - 0.5) / 1.1)))
        px = x0 + size // 2 + roll_t * stop_at * size
        bumped = loop > 1.6
        push = ease_out(min(1.0, (loop - 1.6) / 0.3)) if bumped else 0.0
        ex = x0 + size // 2 + (shape_at + push) * size
        squash = 1 + 0.25 * max(0.0, 1 - (loop - 1.6) / 0.25) if bumped else 1.0
        draw_critter(surf, "square", ex, cy_low, 20, COLOR_RGB["R"], look=(-1, 0),
                     mood="hurt" if 1.6 < loop < 2.6 else "cross", sx=1 / squash, sy=squash, shadow=False)
        draw_player(surf, self.you, px, cy_low, 22, t, look=(1, 0), mood="happy",
                    rot=roll_t * stop_at * size / 22, shadow=False)
        if bumped and loop < 3.2:
            u = loop - 1.6
            draw_text(surf, font(34), "bump! -2", (ex - 10, cy_low - 44 - u * 18), COLOR_RGB["R"],
                      center=True, shadow=INK)
        draw_text(surf, font(18), "you still cast, in every pattern you know", (r.centerx, r.bottom - 26),
                  lighten(INK, 0.3), center=True)

    # one little scenario per twist: (start, direction, special tiles, holes, a shape in the way)
    # one little scenario per twist: (start, direction, special tiles, holes, a shape in the way and its colour)
    TWIST_DEMOS = {
        "holes": ((0, 0), (1, 0), {}, (((4, 0), (2, 2)),), None),
        "springs": ((0, 1), (1, 0), {(3, 1): "spring"}, (), ((4, 1), "R")),
        "snow": ((0, 1), (1, 0), {(2, 1): "snow", (3, 1): "snow", (4, 1): "snow", (5, 1): "snow"}, (),
                 ((8, 1), "R")),
        "pools": ((0, 1), (1, 0), {(3, 1): "pool:B"}, (), ((7, 1), "Y")),
        "bends": ((0, 2), (1, 0), {(4, 2): "bend/", (4, 0): "bend\\"}, (), None),
        "currents": None, "gusts": None,
    }

    def _twist(self, surf, r, t):
        """This tower's special tiles, shown on a strip of its floor: a
        sphere rolls through, for real (the same rules as a fight)."""
        from .combat_ui import _along
        from .rules import bump_damage, roll_info
        from .state import Board, GameState, Player
        pygame.draw.rect(surf, lighten(self.data["wall"], 0.55), r)
        twists = self.data.get("twists") or ("holes",)
        loop = 5.0
        twist = twists[int(t / loop) % len(twists)]
        u = t % loop
        info = TWISTS[twist]
        draw_text(surf, font(22), "%s: %s" % (twist_name(twist, self.tower), info["short"]), (r.centerx, r.y + 30), INK,
                  center=True)
        if self.TWIST_DEMOS[twist] is None:
            self._flow_demo(surf, r, t, u, twist)
            return
        start, (dx, dy), special, holes, foe = self.TWIST_DEMOS[twist]
        cols, rows, size = 9, 3, 56
        key = (self.tower, twist)
        if getattr(self, "_demo_key", None) != key:
            st = GameState(Board(cols, rows, portals=holes, tiles=special), Player())
            st.player.x, st.player.y = start
            st.player.rolls = True
            if foe:
                st.add_enemy("pawn", foe[0][0], foe[0][1], foe[1], 9, "square")
            ri = roll_info(st, dx, dy)
            words = None
            if ri["bumped"] is not None:
                dmg, c = bump_damage(ri, ri["bumped"])
                words = ("absorbed" if c == ri["bumped"].color else "bump -%d%s" % (
                    dmg, {"B": ", stunned!", "G": ", shoved twice!", "R": "!"}.get(c, "!")), c)
            self._demo = ([start] + ri["tiles"], ri["jumps"], ri["hops"], words)
            self._demo_key = key
        path, jumps, hops, words = self._demo
        x0, y0 = self._mini_board(surf, r, cols, rows, size, special, holes)

        def centre(tile):
            return x0 + tile[0] * size + size // 2, y0 + tile[1] * size + size // 2
        roll_time = 0.22 * len(path) + 0.6 * len(jumps)
        f = min(1.0, max(0.0, (u - 0.4) / roll_time))
        gx, gy, grow = _along(path, jumps, f)
        cx, cy = centre((gx, gy))
        lift = 0.0
        for a, b in hops:                                       # flung over: up in an arc
            if min(a[0], b[0]) <= gx <= max(a[0], b[0]) and min(a[1], b[1]) <= gy <= max(a[1], b[1]):
                span = abs(b[0] - a[0]) + abs(b[1] - a[1])
                lift = math.sin(math.pi * min(1.0, (abs(gx - a[0]) + abs(gy - a[1])) / span)) * 60
        if foe:
            fx, fy = centre(foe[0])
            hit = words is not None and f >= 1.0
            draw_critter(surf, "square", fx + (12 if hit and u - 0.4 - roll_time < 0.3 else 0), fy, 19,
                         COLOR_RGB[foe[1]], look=(-1, 0), mood="hurt" if hit else "cross", shadow=False)
            if hit and words:
                draw_text(surf, font(26), words[0], (fx, fy - 44), COLOR_RGB[words[1]] if words[1] else WHITE,
                          center=True, shadow=INK)
        if grow > 0.05:
            snow = sum(1 for i, tile in enumerate(path) if special.get(tuple(tile)) == "snow"
                       and f * (len(path) - 1) >= i)
            dyed = next((special[tuple(tile)][5:] for i, tile in enumerate(path)
                         if special.get(tuple(tile), "").startswith("pool:") and f * (len(path) - 1) >= i), None)
            rad = 21 * grow + snow * 2.5
            if dyed:
                pygame.draw.circle(surf, COLOR_RGB[dyed], (int(cx), int(cy - lift)), int(rad + 6))
            if snow:
                pygame.draw.circle(surf, (246, 250, 255), (int(cx), int(cy - lift)), int(rad + 4))
                pygame.draw.circle(surf, INK, (int(cx), int(cy - lift)), int(rad + 4), 2)
            draw_player(surf, self.you, cx, cy - lift, 21 * grow, t, look=(dx, dy), mood="happy",
                        rot=f * len(path) * 2.5, shadow=False)
        for i, tile in enumerate(path):                         # what happened where, as it rolls by
            kind = special.get(tuple(tile))
            passed = f * (len(path) - 1) >= i
            if not passed or not kind:
                continue
            tx, ty = centre(tile)
            word = {"spring": "boing!", "snow": "+1", "bend/": "turn!", "bend\\": "turn!"}.get(kind)
            col = INK
            if kind.startswith("pool:"):
                word, col = "dyed %s!" % COLOR_NAMES[kind[5:]].lower(), COLOR_RGB[kind[5:]]
            draw_text(surf, font(20), word, (tx, ty - 40), col, center=True, shadow=WHITE)
        foot = {"bends": "Beams turn at facets too: yours, and theirs"}.get(twist, "the Set just step over them")
        draw_text(surf, font(18), foot, (r.centerx, r.bottom - 26), lighten(INK, 0.3), center=True)

    def _flow_demo(self, surf, r, t, u, twist):
        """Currents and gusts: whoever ends a beat on them gets carried. A
        square stands on one, beat after beat, and drifts into a wall."""
        cols, rows, size = 9, 3, 56
        step = 1 if twist == "currents" else 2
        lane = {(k, 1): "%s:1,0" % twist[:-1] for k in range(1, 8)}
        x0, y0 = self._mini_board(surf, r, cols, rows, size, lane)
        beat = int(u / 0.9)
        frac = min(1.0, (u % 0.9) / 0.35)
        pos = min(8, 1 + beat * step)
        prev = min(8, 1 + max(0, beat - 1) * step)
        x = prev + (pos - prev) * ease_in_out(frac) if beat else 1
        cx, cy = x0 + x * size + size // 2, y0 + size + size // 2
        draw_critter(surf, "square", cx, cy, 19, COLOR_RGB["R"], look=(1, 0),
                     mood="wow" if pos < 8 else "hurt", shadow=False)
        draw_player(surf, self.you, x0 + size // 2 + min(3, beat) * 0 + size * 0, y0 + size // 2, 21, t,
                    look=(1, 0.5), mood="happy", shadow=False)
        draw_text(surf, font(20), "beat %d" % (beat + 1), (x0 + 4 * size, y0 + 3 * size + 20), INK, center=True)
        draw_text(surf, font(18), "it carries you too: end your beats off it, or ride it", (r.centerx, r.bottom - 26),
                  lighten(INK, 0.3), center=True)

    GUARDS = {                       # how each Keeper looks on its card: colour, mark, prop
        "latch": ((224, 90, 200), "frame", "bolt"), "knot": ((140, 160, 70), "sprout", "roots"),
        "cap": ((240, 120, 110), None, "cap"), "rime": ((150, 200, 240), "frame", "icicles"),
        "hour": ((230, 190, 110), None, "sand"), "focus": ((170, 130, 240), None, "monocle"),
        "beacon": ((250, 190, 90), None, "lamp"), "vane": ((140, 150, 180), None, "arrow"),
    }

    def _guardian(self, surf, r, t):
        """Inside, by the window: the one who asked, and the Keeper in front
        of it, who means well."""
        from . import board_art
        from .banter import KEEPER
        boss = self.data["boss"]
        friend = self.data["friend"]
        ground = r.bottom - 40
        material = board_art.material_for(self.tower)
        wall = self.data["wall"]
        tile = board_art.wall_block(56, lighten(wall, 0.25), material)
        for gy in range(r.y - 10, ground, 46):                          # the wall, in the tower's stuff
            for gx in range(r.x - 28 * ((gy // 46) % 2), r.right, 56):
                surf.blit(tile, (gx, gy))
        shade_band = pygame.Surface((r.w, ground - r.y), pygame.SRCALPHA)
        shade_band.fill((*lighten(wall, 0.6), 90))
        surf.blit(shade_band, r.topleft)
        floor = board_art.floor_tile(56, self.data["tiles"][0], material)
        for gx in range(r.x, r.right, 56):
            surf.blit(floor, (gx, ground))
        pygame.draw.line(surf, INK, (r.x, ground), (r.right, ground), 3)
        # the window, with the sky (and the Meadow) through it
        wx, wy, wr = r.right - 150, r.y + 110, 70
        pygame.draw.circle(surf, INK, (wx, wy), wr + 8)
        pygame.draw.circle(surf, lighten(wall, 0.45), (wx, wy), wr + 5)
        sky = gradient((wr * 2, wr * 2), *MEADOW_SKY).copy()
        pygame.draw.rect(sky, GRASS, (0, int(wr * 1.3), wr * 2, wr))
        sky = sky.convert_alpha()
        mask = pygame.Surface((wr * 2, wr * 2), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (wr, wr), wr)
        sky.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(sky, (wx - wr, wy - wr))
        stuck = self.tower in ("hollow", "icicle", "toadstool")
        bob = abs(math.sin(t * (8 if self.tower == "toadstool" else 1.7))) * (14 if self.tower == "toadstool" else 4)
        draw_critter(surf, friend["was"], wx, wy + 18 - bob, 30, COLOR_RGB[friend["color"]], look=(-0.8, 0.3),
                     mood="wow" if stuck else "happy", rot=0.3 if self.tower == "hollow" else 0.0, shadow=False)
        if self.tower == "icicle":                                       # frozen in a block of ice
            ice = pygame.Surface((80, 80), pygame.SRCALPHA)
            ice.fill((200, 230, 255, 110))
            pygame.draw.rect(ice, (255, 255, 255, 200), ice.get_rect(), 3)
            surf.blit(ice, (wx - 40, wy - 22))
        if boss == "latch":
            pygame.draw.line(surf, INK, (wx - wr - 14, wy), (wx + wr + 14, wy), 12)
            pygame.draw.line(surf, (220, 180, 110), (wx - wr - 14, wy), (wx + wr + 14, wy), 7)
        # the Keeper, pacing to and fro, meaning well
        col, mark, prop = self.GUARDS.get(boss, ((200, 120, 220), None, None))
        kind = KINDS[boss]
        pace = math.sin(t * 1.2)
        lx = r.x + 240 + pace * 70
        bob = abs(math.sin(t * 4.8)) * 5
        ky = ground - 52 - bob
        if prop == "roots":
            for k in range(6):
                a = math.pi * (0.12 + 0.76 * k / 5)
                pts = [(lx + math.cos(a) * (48 + j * 14), min(ground + 10, ky + 30 + math.sin(a) * j * 6))
                       for j in range(5)]
                pygame.draw.lines(surf, INK, False, pts, 9)
                pygame.draw.lines(surf, (150, 104, 60), False, pts, 5)
        draw_critter(surf, kind["shape"], lx, ky, 48, col, look=(0.9 if pace > 0 else -0.4, -0.5),
                     mood="plain", mark=mark, face=kind.get("face"))
        _keeper_prop(surf, prop, lx, ky, 48, t)
        if (t % 4.0) > 0.5:
            _bubble(surf, KEEPER[boss]["intro"], (lx, ky - 60), width=260, clamp=r.inflate(-16, -16))
        f = font(20)
        tag = pygame.Rect(0, 0, f.size(kind["label"])[0] + 22, f.get_height() + 6)
        tag.center = (int(lx), ground + 18)
        pygame.draw.rect(surf, INK, tag.move(0, 2), border_radius=tag.h // 2)
        pygame.draw.rect(surf, col, tag, border_radius=tag.h // 2)
        pygame.draw.rect(surf, INK, tag, 2, border_radius=tag.h // 2)
        draw_text(surf, f, kind["label"], tag.center, WHITE, center=True, shadow=INK)


def _keeper_prop(surf, prop, x, y, r, t):
    """The little thing each Keeper carries (drawn over its head or by its side)."""
    from . import pixel
    k = 2
    p = pixel.Pix(40, 30)
    if prop == "cap":                                     # a spotted mushroom cap for a hat
        p.ellipse(4, 6, 32, 14, (226, 64, 84))
        p.ellipse(6, 6, 28, 8, (250, 110, 120))
        for dx in (10, 19, 27):
            p.rect(dx, 9, 3, 2, (255, 255, 255))
        p.outline()
        img = p.up(k)
        surf.blit(img, (x - img.get_width() // 2, y - r - 22))
    elif prop == "icicles":
        for i in range(6):
            p.poly([(6 + i * 5, 4), (10 + i * 5, 4), (8 + i * 5, 10 + (i % 3) * 4)], (220, 240, 255))
        p.rect(4, 2, 32, 3, (255, 255, 255))
        p.outline()
        img = p.up(k)
        surf.blit(img, (x - img.get_width() // 2, y - r - 12))
    elif prop == "sand":                                  # an hourglass, held up
        p.poly([(12, 2), (28, 2), (20, 14)], (250, 230, 180))
        p.poly([(12, 26), (28, 26), (20, 14)], (250, 230, 180))
        fill = (t * 0.2) % 1.0
        p.poly([(20 - 6 * (1 - fill), 26 - 10 * fill), (20 + 6 * (1 - fill), 26 - 10 * fill), (28, 26), (12, 26)],
               (230, 180, 90))
        p.rect(10, 0, 20, 2, (150, 100, 60))
        p.rect(10, 27, 20, 2, (150, 100, 60))
        p.outline()
        img = p.up(k)
        surf.blit(img, (x + r - 6, y - 20))
    elif prop == "monocle":
        p.ring(20, 15, 8, (250, 220, 120), 2)
        p.disc(20, 15, 6, (200, 230, 255, 160))
        p.px(17, 12, (255, 255, 255))
        p.outline()
        img = p.up(k)
        surf.blit(img, (x - img.get_width() // 2 + 18, y - img.get_height() // 2 - 4))
    elif prop == "lamp":                                  # glowing, on top
        glow = pygame.Surface((120, 120), pygame.SRCALPHA)
        a = int(70 + 40 * math.sin(t * 3))
        pygame.draw.circle(glow, (255, 230, 150, a), (60, 60), 50)
        surf.blit(glow, (x - 60, y - r - 70))
        p.rect(14, 10, 12, 14, (255, 222, 130))
        p.rect(12, 8, 16, 3, (60, 60, 80))
        p.rect(12, 24, 16, 3, (60, 60, 80))
        p.outline()
        img = p.up(k)
        surf.blit(img, (x - img.get_width() // 2, y - r - 44))
    elif prop == "arrow":                                 # a weathervane arrow, turning
        a = math.sin(t * 1.5) * 1.2
        cx, cy = x, y - r - 26
        tip = (cx + math.cos(a) * 30, cy + math.sin(a) * 6)
        tail = (cx - math.cos(a) * 30, cy - math.sin(a) * 6)
        pygame.draw.line(surf, INK, (x, y - r + 4), (cx, cy), 4)
        pygame.draw.line(surf, INK, tail, tip, 6)
        pygame.draw.line(surf, (120, 130, 160), tail, tip, 3)
        pygame.draw.circle(surf, (250, 210, 90), (int(tip[0]), int(tip[1])), 6)
        pygame.draw.circle(surf, INK, (int(tip[0]), int(tip[1])), 6, 2)


# ------------------------------------------------------------------ ascend

def floor_tiles(surf, ground, tiles):
    """The Sorter's floor seen from the side: a band of tiles below `ground`."""
    pygame.draw.rect(surf, tiles[1], (0, ground, 960, 640 - ground))
    for gx in range(0, 960, 60):
        for row, gy in enumerate(range(ground + 8, 640, 60)):
            pygame.draw.rect(surf, tiles[0], (gx + 4 + (row % 2) * 30, gy, 52, 52), border_radius=8)
    pygame.draw.line(surf, INK, (0, ground), (960, ground), 4)


class AscendScreen(Screen):
    """Between floors: the Keeper gives up its spare side, you grow it, and
    you slot through the door you now fit."""

    GROW_AT, SLOT_AT, DONE_AT = 1.3, 2.5, 3.8

    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.new_act = self.run.act
        self.old_act = self.new_act - 1
        self.old_form = FORMS[self.old_act]
        self.new_form = FORMS[self.new_act]
        self.fx = Particles()
        self.sparked = False
        self.add((380, 560, 200, 46), "Climb", self.advance, key=None, tag="climb")

    def advance(self):
        if self.t < self.DONE_AT:
            self.t = self.DONE_AT
            return
        self.app.enter_floor()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in ADVANCE_KEYS + (pygame.K_ESCAPE,):
            self.advance()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.button_at(ev.pos) is None:
            self.advance()
            return True
        return super().handle(ev)

    def update(self, dt):
        self.fx.update(dt)
        if not self.sparked and self.t >= self.GROW_AT:
            self.sparked = True
            sound.play("ascend")
            for c in COLORS:
                self.fx.burst(380, 300, COLOR_RGB[c], n=5, speed=220)
        return super().update(dt)

    def draw(self, surf):
        t = self.t
        old, new = floor_style(self.old_act), floor_style(self.new_act)
        k = ease_in_out((t - self.SLOT_AT) / 1.2)
        top = mix(old["sky"][0], new["sky"][0], k)
        bot = mix(old["sky"][1], new["sky"][1], k)
        surf.blit(gradient(SCREEN, top, bot), (0, 0))
        ground = 380
        floor_tiles(surf, ground, old["tiles"])
        # the Keeper, dazed, and the side it gives up
        keeper = KINDS[keeper_kind(self.old_act)]
        kx = 170
        draw_critter(surf, keeper["shape"], kx, ground - 62, 58, lighten(COLOR_RGB["M"], 0.2),
                     mood="sleep" if t > 0.6 else "hurt", look=(1, 0))
        # the door, cut for the new form
        door_x = 760
        draw_door(surf, self.new_form["shape"], door_x, ground - 70, 48, old["wall"], t,
                  1.0, locked=t < self.GROW_AT)
        if t >= self.GROW_AT:                        # you fit now: the door opens up in light
            draw_portal(surf, door_x, ground - 70, 44 * min(1.0, (t - self.GROW_AT) / 0.5),
                        self.t, self.new_form["shape"], 1.0)
        # Tri
        px, py = 400, ground - 46
        if t < self.GROW_AT:
            # the loose edge floats over from the Keeper
            f = ease_in_out(t / self.GROW_AT)
            ex, ey = kx + (px - kx) * f, ground - 140 - math.sin(f * math.pi) * 90
            spin = t * 5
            dx, dy = math.cos(spin) * 34, math.sin(spin) * 34
            pygame.draw.circle(surf, (255, 250, 200), (int(ex), int(ey)), 30 + int(4 * math.sin(t * 9)))
            pygame.draw.line(surf, INK, (ex - dx, ey - dy), (ex + dx, ey + dy), 16)
            pygame.draw.line(surf, (255, 226, 92), (ex - dx, ey - dy), (ex + dx, ey + dy), 9)
        if t < self.SLOT_AT:
            grow = ease_out((t - self.GROW_AT) / 0.8) if t > self.GROW_AT else 0.0
            pts = morph_points(self.old_form["shape"], self.new_form["shape"], grow, px, py, 40)
            draw_shadow(surf, px, ground - 2, 76, 18)
            draw_morph(surf, pts, px, py, 40, self.t, "wow" if t > self.GROW_AT else "plain")
        else:
            f = ease_in_out((t - self.SLOT_AT) / 1.0)
            x = px + (door_x - px) * f
            hop = abs(math.sin(f * math.pi * 3)) * 30 * (1 - f)
            scale = 1 - 0.35 * max(0, (f - 0.7) / 0.3)
            draw_player(surf, self.new_form["shape"], x, py - hop, 40 * scale, t, look=(1, 0),
                        mood="happy" if f >= 1 else "plain")
        self.fx.draw(surf)
        # words
        if t >= self.GROW_AT:
            heading(surf, "Tri is a %s now." % self.new_form["name"], (480, 70), 52, center=True)
        else:
            heading(surf, "The Keeper lets go of its spare side.", (480, 70), 40, center=True)
        if t >= self.DONE_AT:
            card = draw_card(surf, (160, 420, 640, 120))
            gift = getattr(self.run, "gift", None)
            text_x = card.x + 20
            if gift:
                # the pattern this form brings, drawn big
                box = pygame.Rect(card.x + 16, card.y + 14, 92, 92)
                pygame.draw.rect(surf, (255, 244, 210), box, border_radius=12)
                pygame.draw.rect(surf, INK, box, 3, border_radius=12)
                draw_pattern_icon(surf, gift, box.centerx, box.centery, 9,
                                  COLOR_RGB[RAINBOW[int(self.t * 3) % 6]])
                draw_text(surf, font(26), "New pattern: %s" % PATTERNS[gift]["name"],
                          (card.x + 124, card.y + 16), ACCENT)
                text_x = card.x + 124
            heal = getattr(self.run, "door_heal", 0)
            perk = self.new_form["perk"] + (" The door's light mends %d HP." % heal if heal else "")
            draw_wrapped(surf, font(22), perk, (text_x, card.y + 46), card.right - text_x - 16, INK)
            draw_text(surf, font(20), "Next: the %s" % FLOORS[self.new_act]["name"],
                      (card.right - 16, card.bottom - 24), DIM, right=True)
        self.draw_buttons(surf)


def _thunk(sides, r, rot):
    """How far a polygon rides up on a corner as it rolls (0 for a circle)."""
    if not sides or not isinstance(sides, int):
        return 0.0
    seg = math.tau / sides
    return r * (1 - math.cos(math.pi / sides)) * abs(math.sin((rot % seg) / seg * math.pi))


# -------------------------------------------------------------------- roll

RAMP = [(60, 140), (880, 420), (90, 700), (880, 980), (90, 1260), (700, 1520)]
MEADOW_Y = 1520
BALL_R = 30


class RollScreen(Screen):
    """The ending. The Round Door grows you the last few sides you need (each
    corner splits into two softer ones, over and over); then, for the
    first time in the game, something moves smoothly: you roll, all the way
    down the Long Ramp, into the Meadow (meadow.MeadowScreen), where you
    steer yourself."""

    PHASES = ("door", "ramp")

    def __init__(self, app):
        super().__init__(app)
        self.fx = Particles()
        self.phase = "door"
        self.phase_t = 0.0
        self.s = 0.0            # distance along the ramp
        self.v = 120.0
        self.rot = 0.0
        self.shaved = 0
        self.hummed = False
        self.seglen = [math.dist(RAMP[i], RAMP[i + 1]) for i in range(len(RAMP) - 1)]
        rng = random.Random(8)
        self.flowers = [(rng.uniform(0, 960), rng.uniform(30, 200), COLOR_RGB[rng.choice(COLORS)],
                         rng.uniform(4, 8)) for _ in range(70)]
        self.clouds = [(rng.uniform(0, 960), rng.uniform(0, MEADOW_Y - 300), rng.uniform(30, 60))
                       for _ in range(14)]
        self.add((380, 580, 200, 44), "Continue", self.advance, tag="continue")

    def advance(self):
        if self.phase == "door":
            self._to("ramp")
        else:
            self.app.show_meadow()

    def _to(self, phase):
        self.phase = phase
        self.phase_t = 0.0

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in ADVANCE_KEYS + (pygame.K_ESCAPE,):
            self.advance()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.button_at(ev.pos) is None:
            self.advance()
            return True
        return super().handle(ev)

    def ball(self):
        """(x, y, direction) on the ramp at distance s."""
        s = self.s
        for i, ln in enumerate(self.seglen):
            if s <= ln or i == len(self.seglen) - 1:
                a, b = RAMP[i], RAMP[i + 1]
                f = min(1.0, s / ln)
                x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                dx, dy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
                nx, ny = dy, -dx
                if ny > 0:
                    nx, ny = -nx, -ny
                return x + nx * (BALL_R + 2), y + ny * (BALL_R + 2), (1 if dx > 0 else -1)
            s -= ln
        return RAMP[-1][0], RAMP[-1][1] - BALL_R, 1

    def update(self, dt):
        self.phase_t += dt
        self.fx.update(dt)
        if self.phase == "door":
            if not self.hummed:
                self.hummed = True
                sound.play("door")
            steps = int(max(0.0, self.phase_t - 0.6) / 0.42)
            if steps > self.shaved and steps <= 5:
                sound.play("step")
                self.shaved = steps       # more sides: a ring of light, sparks of it flying
                self.fx.ring(510, 352, COLOR_RGB[RAINBOW[steps % 6]], 20, 120, 0.5)
                for c in RAINBOW[:3]:
                    self.fx.burst(510, 352, COLOR_RGB[c], n=3, speed=300, shapes=("circle",),
                                  size=(3, 6))
            if self.phase_t > DOOR_SUCK + 0.8:
                self._to("ramp")
        elif self.phase == "ramp":
            sound.roll(self.v / 760.0)
            self.v = min(760.0, self.v + 300 * dt)
            self.s += self.v * dt
            _, _, d = self.ball()
            self.rot += d * self.v * dt / BALL_R
            if self.s >= sum(self.seglen):
                self.app.show_meadow()
                return True
        return super().update(dt)

    # -- drawing
    def draw(self, surf):
        getattr(self, "draw_" + self.phase)(surf)
        self.fx.draw(surf)
        self.draw_buttons(surf)

    def draw_door(self, surf):
        """The Round Door, on the roof of the Sorter, under the stars. It gives
        you sides until you lose count, then takes you in."""
        t = self.phase_t
        surf.blit(gradient(SCREEN, VOID, (88, 40, 120)), (0, 0))
        rng = random.Random(3)
        for i in range(90):                                   # stars, every colour
            sx, sy = rng.uniform(0, 960), rng.uniform(0, 420)
            tw = 0.5 + 0.5 * math.sin(self.t * 2.5 + i)
            pygame.draw.circle(surf, mix(VOID, COLOR_RGB[RAINBOW[i % 6]] if i % 4 else WHITE, tw),
                               (int(sx), int(sy)), 1 + (i % 3 == 0))
        floor_tiles(surf, 400, FLOORS[3]["tiles"])
        cx, cy = 620, 270
        power = 0.6 + min(1.0, t / 3.0) * 0.7
        draw_portal(surf, cx, cy, 120, self.t, "circle", power)
        # you: walking up, then growing sides, then round, then drawn in
        shaves = [5, 6, 7, 8, 9, ROUND_ENOUGH]        # round enough, not round: that comes later
        step = min(5, int(max(0.0, t - 0.6) / 0.42))
        sides, nxt = shaves[step], shaves[min(5, step + 1)]
        grow = ease_out((max(0.0, t - 0.6) % 0.42) / 0.3)
        pull = ease_in_out(max(0.0, (t - DOOR_SUCK) / 0.6))
        x = 380 + min(1, t / 0.6) * 130 + pull * (cx - 510)
        y = 352 - pull * (352 - cy)
        size = 44 * (1 - 0.85 * pull)
        if t < DOOR_SUCK:
            pts = morph_points(sides, nxt, grow if nxt != sides else 1, x, y, size)
            draw_shadow(surf, x, y + 46, 80, 18)
            draw_morph(surf, pts, x, y, 44, self.t, "wow")
        else:
            draw_player(surf, ROUND_ENOUGH, x, y, max(4, size), self.t, mood="happy", rot=pull * 12)
        heading(surf, "The Round Door doesn't need you to be a circle.", (480, 50), 34, center=True)
        if t > 1.2:
            heading(surf, "Only round enough to fit. It does the rest.", (480, 92), 34, center=True)
        if t > DOOR_SUCK + 0.5:                               # through: a white flash
            k = min(1.0, (t - DOOR_SUCK - 0.5) / 0.3)
            flash = pygame.Surface(SCREEN, pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(255 * k)))
            surf.blit(flash, (0, 0))

    def _camera(self, by):
        return max(0.0, min(MEADOW_Y - 420.0, by - 260.0))

    def draw_world(self, surf, cam):
        surf.blit(gradient(SCREEN, *MEADOW_SKY), (0, 0))
        for cx, cy, cr in self.clouds:
            y = cy - cam * 0.6
            for dx in (-cr, 0, cr):
                pygame.draw.circle(surf, WHITE, (int(cx + dx), int(y + (0 if dx == 0 else 10))),
                                   int(cr * (1 if dx == 0 else 0.75)))
        # the Sorter you climbed, standing at the top of the ramp: floors 5, 4, 3
        for k, act in enumerate((3, 2, 1)):
            style = floor_style(act)
            fr = pygame.Rect(-70, 150 + k * 460 - cam, 120, 460)
            pygame.draw.rect(surf, lighten(style["sky"][0], 0.2), fr)
            pygame.draw.rect(surf, INK, fr, 4)
            for w in range(3):
                draw_body(surf, style["door"], 10, fr.y + 90 + w * 140, 14,
                          lighten(style["wall"], 0.3), INK, 2)
        roof = [(-90, 150 - cam), (70, 150 - cam), (-10, 60 - cam)]
        draw_poly(surf, roof, (255, 236, 170), INK, 3)
        pygame.draw.circle(surf, (255, 255, 220), (20, int(118 - cam)), 22)
        pygame.draw.circle(surf, INK, (20, int(118 - cam)), 22, 3)
        # the Long Ramp: a rainbow band
        for i in range(len(RAMP) - 1):
            a, b = RAMP[i], RAMP[i + 1]
            band = [(a[0], a[1] - cam), (b[0], b[1] - cam), (b[0], b[1] - cam + 18), (a[0], a[1] - cam + 18)]
            draw_poly(surf, band, COLOR_RGB[COLORS[i % 6]], INK, 3)
            post = pygame.Rect(0, 0, 14, 60)
            post.midtop = (int(b[0]), int(b[1] - cam + 10))
            pygame.draw.rect(surf, lighten(INK, 0.4), post)
        # the meadow
        gy = MEADOW_Y - cam
        pygame.draw.rect(surf, GRASS, (0, gy, 960, 640))
        pygame.draw.line(surf, INK, (0, gy), (960, gy), 4)
        for fx, fy, col, fr in self.flowers:
            pygame.draw.circle(surf, col, (int(fx), int(gy + fy)), int(fr))
            pygame.draw.circle(surf, INK, (int(fx), int(gy + fy)), int(fr), 2)
        return gy

    def draw_ramp(self, surf):
        bx, by, _ = self.ball()
        cam = self._camera(by)
        self.draw_world(surf, cam)
        draw_player(surf, ROUND_ENOUGH, bx, by - cam - _thunk(ROUND_ENOUGH, BALL_R, self.rot), BALL_R, self.t, mood="happy", rot=self.rot)
        if self.phase_t > 0.6:
            heading(surf, "Tri rolled.", (480, 60), 56, center=True)
        if self.phase_t < 0.5:                                # out of the flash
            flash = pygame.Surface(SCREEN, pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(255 * (1 - self.phase_t / 0.5))))
            surf.blit(flash, (0, 0))


# ------------------------------------------------------------------ rescue

# Out of a tower's window and down its outside: a zigzag of ramps (planks on
# the Leaning Tower, branches on the Hollow Tree), then the grass.
DOWN = [(520, 250), (880, 470), (110, 760), (880, 1050), (240, 1330), (960, 1500)]
DOWN_GROUND = 1500


class RescueScreen(Screen):
    """Up at the window of another tower: the one who asked. Nobody sands
    anyone down. You both go out of the window and roll down the outside;
    you roll smoothly, it goes ka-thunk, ka-thunk, and every few bumps it
    grows another side. By the bottom it's nearly round: round enough. It
    happens because it wanted it; nobody else in the tower has to go."""

    WINDOW_T, OUT_T = 1.0, 2.2

    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.tid = self.run.tower
        self.tower = TOWERS[self.tid]
        from .world import your_sides
        data = app.meta.data
        pretend = getattr(app, "hub_rescued", None)
        now = set(data.get("friends", []) if pretend is None else pretend) | {self.tid}
        self.again = bool(getattr(self.run, "again", False))   # its friend's already out: a climb for fun
        self.you_before = your_sides(data, now if self.again else now - {self.tid})
        self.you_after = your_sides(data, now)          # helping rounds you out too
        self.GUARD_LOOK = TowerIntroScreen.GUARDS.get(self.tower["boss"], ((224, 90, 200), None, None))
        self.friend = self.tower["friend"]
        self.sides = {"triangle": 3, "square": 4, "diamond": 4, "pentagon": 5, "hexagon": 6}.get(
            self.friend["was"], 6)
        self.start_sides = self.sides
        self.fx = Particles()
        self.phase = "window"
        self.phase_t = 0.0
        self.s = 0.0                     # your distance down the ramps
        self.v = 140.0
        self.fs = -90.0                  # its distance (it follows you out)
        self.fv = 140.0
        self.thunks = 0
        self.pops = []                   # "+1 side" words floating up: [x, y, age]
        self.freed = self.tid != "hollow" or self.again   # the square is stuck until you bump it loose
        self.seglen = [math.dist(DOWN[i], DOWN[i + 1]) for i in range(len(DOWN) - 1)]
        self.length = sum(self.seglen)
        rng = random.Random(len(self.tid))
        self.flowers = [(rng.uniform(0, 960), rng.uniform(20, 120), COLOR_RGB[rng.choice(COLORS)],
                         rng.uniform(4, 8)) for _ in range(50)]
        self.add((380, 580, 200, 44), "Continue", self.advance, tag="continue")
        sound.play("door")

    def advance(self):
        if self.phase != "landed" or self.phase_t < 1.0:
            self._land()
            self.phase_t = 1.0
            return
        if self.again:                                   # back out by its door
            from .world import World, plan_of
            data = self.app.meta.data
            pretend = getattr(self.app, "hub_rescued", None)
            world = World(plan_of(data), data.get("friends", []) if pretend is None else pretend)
            zone = next((z for z in world.zones if z.tower == self.tid), None)
            self.app.show_hub(start_x=(zone.wall - 260) if zone else None)
            return
        self._save_sides()
        from .meadow import friend_home
        home = friend_home(self.tid, self.app) - 90
        if self.you_after == 0 and not self.app.meta.data.get("finale_seen"):   # that was the last one:
            from .finale import FinaleScreen                                     # the Grand Roll
            self.app.replace(FinaleScreen(self.app, then=lambda: self.app.show_hub(start_x=home)))
            return
        self.app.show_hub(start_x=home)

    def _save_sides(self):
        sides = self.app.meta.data.setdefault("sides", {})
        sides[self.tid] = max(sides.get(self.tid, 0), self.sides)
        self.app.meta.save()

    def _land(self):
        if self.phase != "landed":
            self.phase = "landed"
            self.phase_t = 0.0
            if not self.again:
                self.sides = max(self.sides, FRIEND_START)
            self.s, self.fs = self.length + 160, self.length + 60
            sound.play("fanfare", 0.8)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in ADVANCE_KEYS + (pygame.K_ESCAPE,):
            self.advance()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.button_at(ev.pos) is None:
            self.advance()
            return True
        return super().handle(ev)

    # -- where things are on the way down
    def on_ramp(self, s, r):
        """(x, y, travel direction) of a ball of radius r at distance s down the ramps."""
        if s >= self.length:                          # on the grass, rolling out
            return min(940.0, DOWN[-1][0] - 200 + (s - self.length)), DOWN_GROUND - r, 1
        s = max(0.0, s)
        for i, ln in enumerate(self.seglen):
            if s <= ln or i == len(self.seglen) - 1:
                a, b = DOWN[i], DOWN[i + 1]
                f = min(1.0, s / ln)
                dx, dy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
                nx, ny = dy, -dx
                if ny > 0:
                    nx, ny = -nx, -ny
                return (a[0] + (b[0] - a[0]) * f + nx * (r + 3), a[1] + (b[1] - a[1]) * f + ny * (r + 3),
                        1 if dx > 0 else -1)
            s -= ln
        return DOWN[-1][0], DOWN_GROUND - r, 1

    def update(self, dt):
        self.phase_t += dt
        self.fx.update(dt)
        for p in self.pops:
            p[2] += dt
        self.pops = [p for p in self.pops if p[2] < 1.2]
        if self.phase == "window":
            if not self.freed and self.phase_t > self.WINDOW_T:
                self.freed = True                     # bonk: the square pops out of the knothole
                sound.play("hit")
                sound.play("loose", 0.7)
                for c in ("G", "Y"):
                    self.fx.burst(700, 300, COLOR_RGB[c], n=8, speed=220, shapes=("circle",))
            if self.phase_t > self.OUT_T:
                self.phase, self.phase_t = "down", 0.0
        elif self.phase == "down":
            self.v = min(700.0, self.v + 300 * dt)
            self.s += self.v * dt
            sound.roll(self.v / 760.0)
            if self.again:                                # just you this time: all the way down
                if self.s >= self.length + 60:
                    sound.roll(0)
                    self._land()
                return super().update(dt)
            before = self._corner(self.fs)
            self.fv = min(640.0, self.fv + 260 * dt)
            self.fs += self.fv * dt
            if self._corner(self.fs) > before and self.fs > 0:       # ka-thunk: over a corner
                self.thunks += 1
                sound.play("step", 0.8)
                x, y, _d = self.on_ramp(self.fs, self._r())
                self.fx.burst(x, y + self._r(), WHITE, n=3, speed=80, shapes=("circle",))
                due = self.start_sides + int((FRIEND_START - self.start_sides) * min(1.0, self.fs / (self.length * 0.9)))
                if self.sides < due:
                    self.sides += 1                                 # bump by bump, a side at a time
                    sound.play("ascend", 0.35)
                    self.pops.append([x, y - 30, 0.0])
                    self.fx.ring(x, y, COLOR_RGB[RAINBOW[self.sides % 6]], 10, 46, 0.5)
            if self.fs >= self.length + 60:
                sound.roll(0)
                self._land()
        return super().update(dt)

    def _r(self):
        return 26.0

    def _corner(self, s):
        """How many corners it has rolled over by distance s (it has `sides` of them a turn)."""
        return int(max(0.0, s) / (math.tau * self._r()) * self.sides)

    # -- drawing
    def draw(self, surf):
        getattr(self, "draw_" + ("window" if self.phase == "window" else "down"))(surf)
        self.fx.draw(surf, 0, -self._cam() if self.phase != "window" else 0)   # (particles live in the world)
        self.draw_buttons(surf)

    def _cam(self):
        _x, yy, _d = self.on_ramp(self.s, 28)
        _x, fyy, _d = self.on_ramp(self.fs, self._r())
        return max(0.0, min(DOWN_GROUND + 140 - 640.0, max(yy, fyy) - 330))

    def draw_window(self, surf):
        """Inside, at the window: you roll up; it's there (stuck, in the Hollow
        Tree, until you bump it out); its guardian stands aside, letting go."""
        from .banter import KEEPER
        t = self.phase_t
        surf.blit(gradient(SCREEN, *self.tower["sky"]), (0, 0))
        floor_tiles(surf, 400, self.tower["tiles"])
        wx, wy, wr = 700, 270, 110
        pygame.draw.circle(surf, INK, (wx, wy), wr + 8)
        view = gradient((wr * 2, wr * 2), *MEADOW_SKY).copy()
        pygame.draw.rect(view, GRASS, (0, int(wr * 1.35), wr * 2, wr))
        mask = pygame.Surface((wr * 2, wr * 2), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (wr, wr), wr)
        view = view.convert_alpha()
        view.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(view, (wx - wr, wy - wr))
        pygame.draw.circle(surf, lighten(self.tower["wall"], 0.2), (wx, wy), wr + 4, 8)
        col = COLOR_RGB[self.friend["color"]]
        out = ease_in_out(max(0.0, (t - 1.5) / (self.OUT_T - 1.5)))      # both hop out, over the sill
        if self.again:
            pass                                          # nobody at the window now: it's out already
        elif not self.freed:
            wig = math.sin(t * 10) * 0.06
            draw_critter(surf, self.friend["was"], wx - 40, wy + 60, 34, col, look=(-0.8, 0.2),
                         mood="wow", rot=0.35 + wig, shadow=False)
        else:
            hop = abs(math.sin(t * 7)) * 16 * (1 - out)
            fx = wx - 60 + out * 140
            fy = 352 - hop - out * 90
            draw_critter(surf, self.friend["was"], fx, fy, 30, col, look=(-0.6, -0.2), mood="happy",
                         shadow=out < 0.1)
        you = ease_out(min(1.0, t / self.WINDOW_T))
        yx = 140 + you * 380 + out * 220
        yy = 352 - out * 110
        draw_player(surf, shape_of(self.you_before), yx, yy, 28, self.t, mood="happy", rot=yx / 28)
        # the guardian, stepping aside
        boss = self.tower["boss"]
        gx = 170 - you * 60
        draw_critter(surf, KINDS[boss]["shape"], gx, 340, 40,
                     self.GUARD_LOOK[0], look=(1, -0.3), mood="sleep" if t < 0.6 else "happy",
                     mark=self.GUARD_LOOK[1], face=KINDS[boss].get("face"))
        if t > 0.5:
            line = KEEPER[boss].get("again", "Again? Go on, then.") if self.again else KEEPER[boss]["loose"]
            _bubble(surf, line, (gx + 10, 290), width=240, clamp=pygame.Rect(8, 8, 944, 380))
        heading(surf, "Up at the window", (480, 40), 44, center=True)

    def draw_down(self, surf):
        """Outside: the tower, the ramps down its side, and the two of you,
        rolling: smoothly, and ka-thunk."""
        landed = self.phase == "landed"
        t = self.phase_t
        yx, yy, yd = self.on_ramp(self.s, 28)
        fxx, fyy, fd = self.on_ramp(self.fs, self._r())
        cam = self._cam()
        from .pixel import sky_up
        from .towers_art import tower_canvas
        from .world import ZONES
        zone = ZONES[self.tower["zone"]]
        surf.blit(sky_up(*zone["sky"]), (0, 0))
        wild = self.tid == "hollow"
        # the tower you came out of: its painting at the top, its lower floors running down
        canvas, meta = tower_canvas(self.tid, True)
        k = 4
        wx, wy = meta["win"]
        w, h = meta["size"]
        left = 485 - (wx + 0.5) * k
        top = 230 - cam - (wy + 0.5) * k
        strip = canvas.subsurface((0, h - 44, w, 16))
        strip = pygame.transform.scale(strip, (w * k, 16 * k))
        y = top + (h - 28) * k
        while y < DOWN_GROUND - cam:
            if y > -80:
                surf.blit(strip, (int(left), int(y)))
            y += 16 * k
        if top + h * k > -10:
            surf.blit(pygame.transform.scale(canvas, (w * k, (h - 28) * k)), (int(left), int(top)),
                      (0, 0, w * k, (h - 28) * k))
        # the ramps: planks (the Leaning Tower), branches (the Hollow Tree), the tower's colours elsewhere
        for i in range(len(DOWN) - 1):
            a, b = DOWN[i], DOWN[i + 1]
            band = [(a[0], a[1] - cam), (b[0], b[1] - cam), (b[0], b[1] - cam + 16), (a[0], a[1] - cam + 16)]
            if wild:
                fill = (150, 104, 60)
            elif self.tid == "leaning":
                fill = COLOR_RGB[RAINBOW[i % 6]]
            else:
                fill = lighten(self.tower["accent"], 0.25 * (i % 2))
            draw_poly(surf, band, fill, INK, 3)
            if wild:
                for k2 in range(1, 4):
                    lx = a[0] + (b[0] - a[0]) * k2 / 4
                    ly = a[1] + (b[1] - a[1]) * k2 / 4 - cam
                    pygame.draw.circle(surf, (90, 190, 80), (int(lx), int(ly - 4)), 9)
                    pygame.draw.circle(surf, INK, (int(lx), int(ly - 4)), 9, 2)
        # the grass at the bottom
        gy = DOWN_GROUND - cam
        ground = zone["ground"][1]
        pygame.draw.rect(surf, ground, (0, gy, 960, 700))
        pygame.draw.rect(surf, zone["ground"][0], (0, gy, 960, 8))
        pygame.draw.line(surf, INK, (0, gy), (960, gy), 4)
        for fx, fy, c, fr in self.flowers:
            pygame.draw.circle(surf, c, (int(fx), int(gy + fy)), int(fr))
            pygame.draw.circle(surf, INK, (int(fx), int(gy + fy)), int(fr), 2)
        # the two of you
        rot = self.s / 28
        you = self.you_after if landed else self.you_before
        draw_player(surf, shape_of(you), yx, yy - cam - (0 if landed else _thunk(you, 28, rot)), 28, self.t, mood="happy", rot=rot)
        if not self.again:
            self._draw_friend(surf, fxx, fyy - cam, landed, t)
        for x, y, age in self.pops:
            k = age / 1.2
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):          # inked round, to read on any sky
                draw_text(surf, font(28), "+1 side", (x + ox, y - cam - 40 * k + oy), INK, center=True)
            draw_text(surf, font(28), "+1 side", (x, y - cam - 40 * k), COLOR_RGB["Y"], center=True)
        if self.again and not landed:
            heading(surf, "Wheeee...", (480, 40), 40, center=True)
        elif self.again:
            self._again_card(surf)
        elif not landed:
            heading(surf, "Ka-thunk, ka-thunk...", (480, 40), 40, center=True)
            f = font(22)
            label = "%d sides" % self.sides
            pill = pygame.Rect(0, 0, f.size(label)[0] + 28, f.get_height() + 8)
            pill.center = (480, 88)
            pygame.draw.rect(surf, INK, pill, border_radius=pill.h // 2)
            draw_text(surf, f, label, pill.center, WHITE, center=True)
        else:
            card = draw_card(surf, (170, 372, 620, 196))
            draw_text(surf, font(36), "It asked. You came.", (480, 402), INK, center=True)
            words = ("It isn't perfectly round, and it doesn't need to be: every bump on the way down "
                     "gave it another side. Round enough to roll.")
            draw_wrapped(surf, font(20), words, (card.x + 20, card.y + 56), card.w - 40, INK, center=True)
            if self.you_after == 0:
                mine = "And you: round. All the way round, at last."
            else:
                mine = "And you: %d sides, now %d. Helping rounds you out too." % (self.you_before,
                                                                                  self.you_after)
            draw_player(surf, shape_of(self.you_after), card.x + 40, card.y + 112, 12, self.t, shadow=False)
            draw_text(surf, font(20), mine, (card.centerx + 10, card.y + 112), COLOR_RGB["M"], center=True)
            draw_text(surf, font(20), self.tower.get("after", ""), (card.centerx, card.bottom - 44),
                      ACCENT, center=True)
            draw_text(surf, font(20), self._next_words(), (card.centerx, card.bottom - 20), INK, center=True)

    def _again_card(self, surf):
        """Landed after a climb just for fun: how many times now, and who's waving."""
        from .banter import KEEPER
        card = draw_card(surf, (170, 372, 620, 196))
        draw_text(surf, font(36), "Up and down again!", (480, 402), INK, center=True)
        words = ("The floors shuffle every time you go in, so no two climbs are the same. "
                 "Come back whenever you like.")
        draw_wrapped(surf, font(20), words, (card.x + 20, card.y + 56), card.w - 40, INK, center=True)
        n = self.app.meta.data.get("tower_climbs", {}).get(self.tid, 1)
        draw_text(surf, font(22), "Times up %s: %d" % (self.tower["name"].replace("The ", "the "), n), (480, card.y + 120),
                  COLOR_RGB["M"], center=True)
        label = KINDS[self.tower["boss"]]["label"]
        draw_text(surf, font(20), '%s, from the window: "%s"' % (label, KEEPER[self.tower["boss"]].get(
            "wave", "Come again!")), (480, card.bottom - 30), ACCENT, center=True)

    def _next_words(self):
        """What the open door leads to now."""
        from .world import World, plan_of
        data = self.app.meta.data
        pretend = getattr(self.app, "hub_rescued", None)
        world = World(plan_of(data), set(pretend if pretend is not None else data.get("friends", [])) | {self.tid})
        nxt = world.next_zone_after(self.tid)
        if nxt is None:
            return "That's everyone who asked. For now."
        return "Through its door: %s. It'll be there, running the game." % nxt["name"]

    def _draw_friend(self, surf, x, y, landed, t):
        """Rolling as a polygon: it rides up on each corner, then thunks down."""
        r = self._r()
        n = self.sides
        ang = max(0.0, self.fs) / r
        seg = math.tau / n
        lift = r * (1 - math.cos(math.pi / n)) * abs(math.sin((ang % seg) / seg * math.pi))
        if landed:
            ang = 0.0
            lift = abs(math.sin(t * 5)) * 14 * max(0.0, 1 - t / 3)
        col = COLOR_RGB[self.friend["color"]]
        draw_shadow(surf, x, y + r, r * 1.8, r * 0.5)
        draw_body(surf, n, x, y - lift, r, col, INK, 3, ang)
        draw_body(surf, self.friend["was"], x, y - lift, r * 0.5, None, lighten(col, 0.45), 2, ang * 0.2)
        draw_eyes(surf, x, y - lift - 2, r, (1, 0), "happy" if landed else "wow")
