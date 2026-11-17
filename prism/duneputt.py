"""Dune Putt: the Dunes' game (in the vein of mini golf).

You're the ball (of course you are). Six holes across the sand: aim with the
arrows, hold Space to wind up, let go to putt. Dunes slope the green and
carry you sideways, sand slows you right down, the oasis takes you back to
where you putted from (one stroke more), round rocks bounce you. The hole
is round: the only thing in the Dunes rounder than you. Under par scores
big; nothing's at stake.
"""

import math

import pygame

from . import sound
from .arcade import FIELD, ArcadeScreen
from .art import draw_body
from .consts import COLOR_RGB, RAINBOW
from .pixel import Pix, cached, mix
from .widgets import INK, WHITE, draw_text, font

BALL = 10
CUP = 13
FRICTION, SAND = 150.0, 560.0
SLOPE = 170.0
POWER = (120.0, 760.0)
MAX_STROKES = 7
W, H = FIELD.w, FIELD.h

# Each hole: par, tee, cup, walls (segments), dunes (rect, push x, push y),
# sand (rects), water (circles), rocks (circles)
HOLES = [
    {"par": 2, "tee": (230, 540), "cup": (230, 110), "walls": [],
     "dunes": [((60, 230, 340, 140), -1, 0)], "sand": [], "water": [], "rocks": []},
    {"par": 3, "tee": (100, 540), "cup": (110, 110),
     "walls": [((0, 330), (330, 330))], "dunes": [((340, 150, 110, 300), 0, 1)],
     "sand": [(30, 360, 120, 60)], "water": [], "rocks": []},
    {"par": 3, "tee": (230, 550), "cup": (230, 90), "walls": [],
     "dunes": [], "sand": [(60, 150, 100, 60), (300, 150, 100, 60)], "water": [(230, 310, 80)],
     "rocks": [(110, 420, 20), (350, 420, 20)]},
    {"par": 3, "tee": (230, 560), "cup": (350, 100), "walls": [],
     "dunes": [((0, 380, 460, 90), 1, 0)], "sand": [],
     "water": [], "rocks": [(150, 200, 22), (260, 270, 22), (330, 190, 18), (120, 320, 18), (230, 150, 16)]},
    {"par": 3, "tee": (80, 560), "cup": (380, 100), "walls": [((140, 470), (460, 470)), ((0, 250), (320, 250))],
     "dunes": [((160, 300, 300, 140), -1, 0), ((0, 120, 300, 120), 1, 0)], "sand": [(330, 300, 100, 90)],
     "water": [], "rocks": []},
    {"par": 4, "tee": (230, 560), "cup": (230, 200),
     "walls": [((230 + math.cos(a) * 110, 200 + math.sin(a) * 110),
                (230 + math.cos(a + 0.3) * 110, 200 + math.sin(a + 0.3) * 110))
               for a in [k * 0.3 + 2.0 for k in range(19)]],
     "dunes": [((0, 380, 230, 120), 1, -0.5)], "sand": [(280, 380, 120, 80)], "water": [(90, 180, 50)],
     "rocks": []},
]


def _seg_closest(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ln = dx * dx + dy * dy
    f = 0.0 if ln == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ln))
    return ax + dx * f, ay + dy * f


class DunePuttScreen(ArcadeScreen):
    NAME = "Dune Putt"
    ZONE = "dunes"
    BEST = "duneputt_best"
    HELP = ("Six holes across the sand. Dunes carry you sideways, sand slows you down, the oasis sends you "
            "back (one stroke more), rocks bounce you. Under par scores big.",)
    KEYS = ("<- ->: aim", "hold Space: wind up, let go", "Esc: back")

    def reset(self):
        self.hole_no = 0
        self.cards = []                           # strokes per hole
        self.next_hole()

    def next_hole(self):
        self.hole_no += 1
        self.hole = HOLES[(self.hole_no - 1) % len(HOLES)]
        self.x, self.y = self.hole["tee"]
        self.vx = self.vy = 0.0
        self.last = (self.x, self.y)
        self.strokes = 0
        cx, cy = self.hole["cup"]
        self.aim = math.atan2(cx - self.x, self.y - cy)
        self.charge = 0.0
        self.charging = False
        self.sunk = None                          # seconds since you dropped in
        self.rot = 0.0

    def status(self):
        total = sum(self.cards)
        par = sum(HOLES[i % len(HOLES)]["par"] for i in range(len(self.cards)))
        diff = total - par
        return ("hole %d of %d   par %d" % (self.hole_no, len(HOLES), self.hole["par"]),
                "strokes: %d" % self.strokes,
                "card: %s" % ("even" if diff == 0 else "%+d" % diff) if self.cards else "card: -")

    def moving(self):
        return math.hypot(self.vx, self.vy) > 4

    def handle(self, ev):
        if self.over is None and self.sunk is None and not self.moving():
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.charging = True
            elif ev.type == pygame.KEYUP and ev.key in (pygame.K_SPACE, pygame.K_RETURN) and self.charging:
                self.putt(POWER[0] + (POWER[1] - POWER[0]) * self.charge)
        return super().handle(ev)

    def putt(self, speed):
        self.charging = False
        self.charge = 0.0
        self.last = (self.x, self.y)
        self.vx, self.vy = math.sin(self.aim) * speed, -math.cos(self.aim) * speed
        self.strokes += 1
        sound.play("step")

    def step(self, dt):
        if self.sunk is not None:
            self.sunk += dt
            if self.sunk > 1.6:
                self._score_hole()
            return
        if not self.moving():
            self.aim += self.axis() * dt * 1.6
            if self.charging:
                self.charge = min(1.0, self.charge + dt * 0.7)
            if self.strokes >= MAX_STROKES:                    # picked up: on to the next
                self.pop("Picked up!", FIELD.x + self.x, FIELD.y + self.y - 30, WHITE)
                self.strokes += 1
                self._score_hole()
            return
        for _ in range(6):
            self._move(dt / 6)
            if self.sunk is not None:
                break
        sound.roll(min(1.0, math.hypot(self.vx, self.vy) / 700) * 0.5)

    def _move(self, dt):
        h = self.hole
        f = FRICTION
        for sx, sy, sw, sh in h["sand"]:
            if sx <= self.x <= sx + sw and sy <= self.y <= sy + sh:
                f = SAND
        for (dx0, dy0, dw, dh), px, py in h["dunes"]:
            if dx0 <= self.x <= dx0 + dw and dy0 <= self.y <= dy0 + dh:
                self.vx += px * SLOPE * dt
                self.vy += py * SLOPE * dt
        sp = math.hypot(self.vx, self.vy)
        if sp > 0:
            k = max(0.0, sp - f * dt) / sp
            self.vx *= k
            self.vy *= k
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += sp * dt / BALL
        # the edges of the green, and the walls
        if self.x < BALL or self.x > W - BALL:
            self.x = max(BALL, min(W - BALL, self.x))
            self.vx *= -0.8
            sound.play("hit", 0.3)
        if self.y < BALL or self.y > H - BALL:
            self.y = max(BALL, min(H - BALL, self.y))
            self.vy *= -0.8
            sound.play("hit", 0.3)
        for a, b in h["walls"]:
            cx, cy = _seg_closest(self.x, self.y, a, b)
            dx, dy = self.x - cx, self.y - cy
            d = math.hypot(dx, dy)
            if 0 < d < BALL + 3:
                nx, ny = dx / d, dy / d
                self.x, self.y = cx + nx * (BALL + 3), cy + ny * (BALL + 3)
                vn = self.vx * nx + self.vy * ny
                if vn < 0:
                    self.vx -= 1.8 * vn * nx
                    self.vy -= 1.8 * vn * ny
                    sound.play("hit", 0.3)
        for rx, ry, rr in h["rocks"]:
            dx, dy = self.x - rx, self.y - ry
            d = math.hypot(dx, dy)
            if 0 < d < BALL + rr:
                nx, ny = dx / d, dy / d
                self.x, self.y = rx + nx * (BALL + rr), ry + ny * (BALL + rr)
                vn = self.vx * nx + self.vy * ny
                if vn < 0:
                    self.vx -= 1.9 * vn * nx
                    self.vy -= 1.9 * vn * ny
                    sound.play("hit", 0.5)
        for wx, wy, wr in h["water"]:                       # splash: back where you putted from
            if math.hypot(self.x - wx, self.y - wy) < wr - 4:
                self.fx.burst(FIELD.x + self.x, FIELD.y + self.y, (120, 200, 240), n=10, speed=160,
                              shapes=("circle",))
                sound.play("loose", 0.6)
                self.pop("Splash! +1", FIELD.x + self.x, FIELD.y + self.y - 20, (120, 200, 240))
                self.x, self.y = self.last
                self.vx = self.vy = 0.0
                self.strokes += 1
                return
        cx, cy = h["cup"]
        d = math.hypot(self.x - cx, self.y - cy)
        if d < CUP - 2:
            if math.hypot(self.vx, self.vy) < 330:
                self.sunk = 0.0
                self.x, self.y = cx, cy
                self.vx = self.vy = 0.0
                sound.play("ascend", 0.7)
                for c in RAINBOW:
                    self.fx.burst(FIELD.x + cx, FIELD.y + cy, COLOR_RGB[c], n=3, speed=180, shapes=("circle",))
            else:                                            # too fast: it lips out
                self.vx += (self.x - cx) * 8
                self.vy += (self.y - cy) * 8

    def _score_hole(self):
        par = self.hole["par"]
        n = min(self.strokes, MAX_STROKES + 1)
        self.cards.append(n)
        pts = max(0, (par + 3 - n)) * 100 + (500 if n == 1 else 0)
        self.score += pts
        word = {1: "Hole in one!!", par - 2: "Eagle!", par - 1: "Birdie!", par: "Par!", par + 1: "Bogey."}.get(
            n, "In!" if n <= MAX_STROKES else "Picked up.")
        self.pop("%s +%d" % (word, pts), FIELD.centerx, FIELD.y + 260, WHITE)
        if self.hole_no >= len(HOLES):
            self.end()
        else:
            self.next_hole()

    def summary(self):
        total = sum(self.cards)
        par = sum(h["par"] for h in HOLES)
        return "%d strokes (par %d): %s" % (total, par, "under par!" if total < par else "lovely round.")

    def cheer(self):
        if self.over is not None:
            return "Again? Again!"
        if self.sunk is not None:
            return "In it goes!"
        return "Nice and easy..."

    # -- drawing
    def draw_field(self, surf):
        ox, oy = FIELD.topleft
        surf.blit(_course(self.hole_no - 1), (ox, oy))
        h = self.hole
        t = self.t
        for (dx0, dy0, dw, dh), px, py in h["dunes"]:            # the dunes' slope, in little arrows
            for k in range(int(dw / 46) * int(dh / 46) + 1):
                gx = dx0 + 23 + (k % max(1, int(dw / 46))) * 46
                gy = dy0 + 23 + (k // max(1, int(dw / 46))) * 46
                if gy > dy0 + dh:
                    break
                off = ((t * 18) % 14) - 7
                cx, cy = ox + gx + px * off, oy + gy + py * off
                pygame.draw.line(surf, (200, 150, 90), (cx - px * 6 - py * 5, cy - py * 6 - px * 5), (cx, cy), 2)
                pygame.draw.line(surf, (200, 150, 90), (cx - px * 6 + py * 5, cy - py * 6 + px * 5), (cx, cy), 2)
        for rx, ry, rr in h["rocks"]:
            pygame.draw.circle(surf, INK, (ox + rx, oy + ry + 2), rr + 2)
            pygame.draw.circle(surf, (190, 140, 100), (ox + rx, oy + ry), rr)
            pygame.draw.circle(surf, (220, 176, 130), (ox + rx - rr // 3, oy + ry - rr // 3), rr // 3)
        for a, b in h["walls"]:
            pygame.draw.line(surf, INK, (ox + a[0], oy + a[1] + 2), (ox + b[0], oy + b[1] + 2), 9)
            pygame.draw.line(surf, (230, 190, 130), (ox + a[0], oy + a[1]), (ox + b[0], oy + b[1]), 6)
        cx, cy = h["cup"]
        pygame.draw.circle(surf, INK, (ox + cx, oy + cy), CUP + 2)
        pygame.draw.circle(surf, (40, 30, 30), (ox + cx, oy + cy), CUP)
        if self.sunk is None:                                     # the flag
            pygame.draw.line(surf, INK, (ox + cx, oy + cy), (ox + cx, oy + cy - 46), 3)
            wave = math.sin(t * 5) * 3
            flag = [(ox + cx, oy + cy - 46), (ox + cx + 24, oy + cy - 40 + wave), (ox + cx, oy + cy - 32)]
            pygame.draw.polygon(surf, COLOR_RGB["M"], flag)
            pygame.draw.polygon(surf, INK, flag, 2)
        tx, ty = h["tee"]
        draw_body(surf, "square", ox + tx, oy + ty + 16, 6, (250, 236, 200), INK, 2)
        if self.sunk is not None:
            k = min(1.0, self.sunk / 0.4)
            if k < 1:
                self.draw_you(surf, ox + self.x, oy + self.y, BALL * (1 - k), rot=self.rot)
        else:
            if not self.moving() and self.over is None:
                for k in range(1, 9):
                    ax = self.x + math.sin(self.aim) * k * 22
                    ay = self.y - math.cos(self.aim) * k * 22
                    pygame.draw.circle(surf, WHITE, (int(ox + ax), int(oy + ay)), 3 if k < 8 else 5)
                if self.charging:
                    bar = pygame.Rect(ox + self.x - 30, oy + self.y + 20, 60, 10)
                    pygame.draw.rect(surf, INK, bar.inflate(4, 4), border_radius=5)
                    pygame.draw.rect(surf, mix((120, 220, 140), (255, 110, 120), self.charge),
                                     (bar.x, bar.y, int(bar.w * self.charge), bar.h), border_radius=5)
            self.draw_you(surf, ox + self.x, oy + self.y, BALL, rot=self.rot)
        draw_text(surf, font(20), "Hole %d   par %d" % (self.hole_no, h["par"]), (ox + 12, oy + 10), WHITE,
                  shadow=INK)


def _course(i):
    """One hole of the course, painted: mown turquoise felt in stripes, a
    sandstone rim with cacti and pebbles, rippled sand traps, the oasis
    with its palm, and the dunes' slopes banded toward their low side."""
    h = HOLES[i % len(HOLES)]

    def build():
        w2, h2 = W // 2, H // 2
        p = Pix(w2, h2, seed=i)
        felt_a, felt_b = (112, 200, 172), (128, 212, 184)
        for y in range(h2):                                       # mown stripes, on the diagonal
            for x in range(w2):
                p.px(x, y, felt_a if ((x + y) // 12) % 2 else felt_b)
        for _ in range(220):                                      # felt grain
            x, y = p.rng.randrange(w2), p.rng.randrange(h2)
            p.px(x, y, mix(p.get(x, y)[:3], (255, 255, 255), 0.18))
        for (dx0, dy0, dw, dh), px, py in h["dunes"]:              # dunes: sandy felt, darker to the low side
            for y in range(dy0 // 2, (dy0 + dh) // 2):
                for x in range(dx0 // 2, (dx0 + dw) // 2):
                    u = ((x * 2 - dx0) / max(1, dw) if px else (y * 2 - dy0) / max(1, dh))
                    u = u if (px > 0 or py > 0) else 1 - u
                    base = mix((176, 214, 160), (120, 176, 140), u)
                    p.px(x, y, base if ((x + y) // 12) % 2 else mix(base, (255, 255, 255), 0.06))
            for k in range(0, max(dw, dh) // 2, 7):                # ripple lines across the slope
                if px:
                    x = dx0 // 2 + k
                    if x < (dx0 + dw) // 2:
                        for y in range(dy0 // 2 + 2, (dy0 + dh) // 2 - 2):
                            if (y + k) % 5:
                                p.px(x + int(math.sin(y * 0.4) * 1.5), y, (150, 190, 140))
                else:
                    y = dy0 // 2 + k
                    if y < (dy0 + dh) // 2:
                        for x in range(dx0 // 2 + 2, (dx0 + dw) // 2 - 2):
                            if (x + k) % 5:
                                p.px(x, y + int(math.sin(x * 0.4) * 1.5), (150, 190, 140))
        for sx, sy, sw, sh in h["sand"]:                          # traps, rippled
            p.ellipse(sx // 2 - 1, sy // 2 - 1, sw // 2 + 2, sh // 2 + 2, (200, 164, 110))
            p.ellipse(sx // 2, sy // 2, sw // 2, sh // 2, (238, 210, 150))
            p.ellipse(sx // 2 + 2, sy // 2 + 1, sw // 2 - 4, sh // 2 - 3, (248, 226, 170))
            for k in range(3, sh // 2 - 2, 4):
                y = sy // 2 + k
                for x in range(sx // 2 + 4, sx // 2 + sw // 2 - 4):
                    c = p.get(x, y)
                    if c is not None and c[:3] == (248, 226, 170) and (x + k) % 3:
                        p.px(x, y + int(math.sin(x * 0.5 + k) * 1.2), (232, 200, 140))
        for wx, wy, wr in h["water"]:                             # the oasis
            cx, cy, r = wx // 2, wy // 2, wr // 2
            p.disc(cx, cy, r + 3, (92, 168, 104))
            p.disc(cx, cy, r + 1, (60, 130, 190))
            p.disc(cx, cy, r, (70, 170, 220))
            p.disc(cx - r // 4, cy - r // 4, r // 2, (110, 196, 236))
            for k in range(4):                                    # glints
                a = k * 1.7 + i
                p.rect(cx + math.cos(a) * r * 0.5, cy + math.sin(a) * r * 0.5, 3, 1, (220, 244, 255))
            for k in range(3):                                    # lily pads
                a = k * 2.1 + 0.5
                lx, ly = cx + math.cos(a) * r * 0.7, cy + math.sin(a) * r * 0.7
                p.disc(lx, ly, 2, (80, 170, 90))
                p.px(lx + 1, ly - 1, (255, 160, 200))
            # a palm on the shore: trunk, fronds, coconuts
            bx, by = cx + r + 1, cy + 2
            for k in range(12):
                p.rect(bx + int(math.sin(k * 0.25) * 2), by - k, 2, 1, (150, 104, 60) if k % 3 else (120, 80, 44))
            top = (bx + int(math.sin(3.0) * 2), by - 12)
            for a in (-2.6, -2.0, -1.2, -0.5, 0.1):
                for d in range(1, 9):
                    fx = top[0] + math.cos(a) * d
                    fy = top[1] + math.sin(a) * d + d * d * 0.06
                    p.px(fx, fy, (60, 150, 80))
                    p.px(fx, fy + 1, (40, 120, 64))
            p.disc(top[0], top[1] + 1, 1, (130, 84, 40))
        # the rim: sandstone blocks, with cacti and pebbles growing on it
        rim = (212, 166, 112)
        p.rect(0, 0, w2, 4, rim)
        p.rect(0, h2 - 4, w2, 4, rim)
        p.rect(0, 0, 4, h2, rim)
        p.rect(w2 - 4, 0, 4, h2, rim)
        for x in range(0, w2, 9):
            p.px(x, 1, (236, 196, 140))
            p.rect(x, 0, 1, 4, (176, 128, 84))
            p.rect(x + 4, h2 - 4, 1, 4, (176, 128, 84))
        for y in range(0, h2, 9):
            p.rect(0, y, 4, 1, (176, 128, 84))
            p.rect(w2 - 4, y + 4, 4, 1, (176, 128, 84))
        p.rect(4, 4, w2 - 8, 1, (80, 150, 130))                  # the felt's shadowed lip
        p.rect(4, 4, 1, h2 - 8, (80, 150, 130))
        for cx, cy in ((7, h2 - 12), (w2 - 9, 26), (w2 - 8, h2 - 60), (6, 40)):   # cacti in the corners
            p.rect(cx, cy, 3, 9, (70, 160, 90))
            p.rect(cx - 2, cy + 3, 2, 2, (70, 160, 90))
            p.rect(cx - 2, cy + 1, 1, 2, (70, 160, 90))
            p.rect(cx + 3, cy + 2, 2, 2, (70, 160, 90))
            p.rect(cx + 4, cy, 1, 2, (70, 160, 90))
            p.px(cx + 1, cy - 1, (255, 140, 190))
            p.px(cx + 1, cy + 4, (110, 200, 120))
        for _ in range(26):                                       # pebbles on the rim
            side = p.rng.randrange(4)
            t = p.rng.random()
            x, y = [(t * w2, 2), (t * w2, h2 - 2), (2, t * h2), (w2 - 2, t * h2)][side]
            p.px(x, y, p.rng.choice(((250, 220, 170), (180, 130, 90), (255, 200, 150))))
        return p.up(2)
    return cached(("duneputt_course", i % len(HOLES)), build)
