"""Spore Drop: the Glow Grove's game (in the vein of Peggle).

You drop from a cap at the top, aim with the arrows, Space to let go. Down
you bounce through a field of little shapes. Every one you touch lights up
and grows a side; when you leave the field, every lit shape rounds off and
floats away. The sleepy ones in the level's colour are the ones that
matter: wake them all to clear the level (the more you've woken, the more
each is worth). A bouncy cap slides along the bottom: land in it for a free
drop. Ten drops. Nothing at stake.
"""

import math

import pygame

from . import sound
from .arcade import FIELD, ArcadeScreen
from .art import draw_body, draw_critter, lighten
from .consts import COLOR_NAMES, COLOR_RGB, RAINBOW
from .pixel import Pix, cached, mix
from .widgets import INK, WHITE

BALL = 11
GRAVITY = 560.0
SHOT = 560.0
PEG = 11
DROPS = 10
LAUNCH = (FIELD.w // 2, 46)
SHAPES = ("triangle", "square", "pentagon", "hexagon")


class Peg:
    def __init__(self, x, y, goal, color, shape):
        self.x, self.y = x, y
        self.goal, self.color, self.shape = goal, color, shape
        self.lit = False
        self.gone = 0.0                       # seconds since it rounded off and floated away (0: still here)


def layout(n, rng):
    """Where the shapes go, level n: arcs, rings, a diamond lattice, a spiral."""
    w = FIELD.w
    pts = []
    kind = n % 4
    if kind == 1:                                          # arcs
        for row in range(5):
            y = 160 + row * 78
            for k in range(9):
                x = 50 + k * (w - 100) / 8
                pts.append((x, y + math.sin(k / 8 * math.pi) * -22 * (1 if row % 2 else -1)))
    elif kind == 2:                                        # rings
        for cx, cy in ((w * 0.3, 240), (w * 0.7, 240), (w * 0.5, 420)):
            for k in range(12):
                a = k * math.tau / 12
                pts.append((cx + math.cos(a) * 70, cy + math.sin(a) * 70))
    elif kind == 3:                                        # a spiral
        for k in range(44):
            a = k * 0.42
            rr = 30 + k * 4.3
            pts.append((w / 2 + math.cos(a) * rr, 330 + math.sin(a) * rr * 0.85))
    else:                                                  # a diamond lattice
        for row in range(7):
            y = 150 + row * 56
            off = 0 if row % 2 else (w - 80) / 14
            for k in range(7):
                pts.append((40 + off + k * (w - 80) / 7, y))
    pts = [(x, y) for x, y in pts if 24 < x < w - 24 and 120 < y < 540]
    return pts


class SporeDropScreen(ArcadeScreen):
    NAME = "Spore Drop"
    ZONE = "grove"
    BEST = "sporedrop_best"
    HELP = ("Drop through the shapes. Everything you touch lights up and grows a side; when you leave, they "
            "all float away round. Wake every sleepy one in the level's colour to clear it.",
            "Land in the sliding cap for a free drop.")
    KEYS = ("<- ->: aim", "Space: drop", "Esc: back")

    def reset(self):
        self.level = 0
        self.drops = DROPS
        self.next_level()

    def next_level(self):
        self.level += 1
        self.goal_color = RAINBOW[(self.level * 2 + 1) % 6]
        pts = layout(self.level, self.rng)
        self.rng.shuffle(pts)
        goals = max(8, min(14, len(pts) // 3))
        self.pegs = []
        others = [c for c in RAINBOW if c != self.goal_color]
        for i, (x, y) in enumerate(pts):
            goal = i < goals
            color = self.goal_color if goal else self.rng.choice(others)
            self.pegs.append(Peg(x, y, goal, color, self.rng.choice(SHAPES)))
        self.aim = 0.0
        self.ball = None
        self.slow_t = 0.0
        self.bucket_x = FIELD.w / 2
        self.woken = 0
        self.pop("Level %d: wake the %s ones!" % (self.level, COLOR_NAMES[self.goal_color].lower()),
                 FIELD.centerx, FIELD.y + 300, COLOR_RGB[self.goal_color])

    def goals_left(self):
        return sum(1 for p in self.pegs if p.goal and not p.gone)

    def mult(self):
        woken = self.woken
        return 1 if woken < 4 else 2 if woken < 8 else 3 if woken < 11 else 5

    def status(self):
        return ("level %d" % self.level, "drops left: %d" % self.drops,
                "%s left: %d" % (COLOR_NAMES[self.goal_color].lower(), self.goals_left()), "x%d" % self.mult())

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and self.over is None:
            if ev.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_DOWN) and self.ball is None and self.drops > 0:
                self.shoot()
                return True
        return super().handle(ev)

    def shoot(self):
        a = math.pi / 2 + self.aim
        self.ball = [LAUNCH[0], LAUNCH[1] + 14, math.cos(a) * SHOT, math.sin(a) * SHOT]
        self.drops -= 1
        sound.play("step")

    def step(self, dt):
        if self.ball is None:
            self.aim = max(-1.35, min(1.35, self.aim - self.axis() * dt * 1.4))
        self.bucket_x = FIELD.w / 2 + math.sin(self.t * 0.8) * (FIELD.w / 2 - 50)
        for p in self.pegs:
            if p.gone:
                p.gone += dt
        self.pegs = [p for p in self.pegs if p.gone < 1.2]
        if self.ball is None:
            if self.goals_left() == 0 and not any(p.gone for p in self.pegs):
                self.clear_level()
            elif self.drops <= 0 and not any(p.gone for p in self.pegs):
                self.end()
            return
        for _ in range(4):
            self._move(dt / 4)
            if self.ball is None:
                break

    def _move(self, dt):
        b = self.ball
        b[3] += GRAVITY * dt
        b[0] += b[2] * dt
        b[1] += b[3] * dt
        if b[0] < BALL:
            b[0], b[2] = BALL, abs(b[2]) * 0.8
        elif b[0] > FIELD.w - BALL:
            b[0], b[2] = FIELD.w - BALL, -abs(b[2]) * 0.8
        if b[1] < BALL:
            b[1], b[3] = BALL, abs(b[3])
        for p in self.pegs:
            if p.gone:
                continue
            dx, dy = b[0] - p.x, b[1] - p.y
            d = math.hypot(dx, dy)
            if 0 < d < BALL + PEG:
                nx, ny = dx / d, dy / d
                b[0], b[1] = p.x + nx * (BALL + PEG), p.y + ny * (BALL + PEG)
                vn = b[2] * nx + b[3] * ny
                if vn < 0:
                    b[2] -= 1.75 * vn * nx
                    b[3] -= 1.75 * vn * ny
                if not p.lit:
                    p.lit = True
                    sound.play("cast:" + p.color, 0.4)
                    self.fx.burst(FIELD.x + p.x, FIELD.y + p.y, lighten(COLOR_RGB[p.color], 0.3), n=4, speed=90,
                                  shapes=("circle",))
        speed = math.hypot(b[2], b[3])
        self.slow_t = self.slow_t + dt if speed < 60 else 0.0
        if self.slow_t > 1.6:                              # stuck on something: clear what's lit now
            self._pop_lit()
            self.slow_t = 0.0
        if b[1] > FIELD.h - 20:                            # out the bottom: into the cap?
            if abs(b[0] - self.bucket_x) < 44:
                self.drops += 1
                self.pop("Free drop!", FIELD.x + b[0], FIELD.y + FIELD.h - 70, COLOR_RGB["G"])
                sound.play("ascend", 0.6)
            self.ball = None
            self._pop_lit()

    def _pop_lit(self):
        """Every shape you lit rounds off and floats away."""
        got = 0
        for p in self.pegs:
            if p.lit and not p.gone:
                p.gone = 0.001
                pts = 100 * self.mult() if p.goal else 10
                if p.goal:
                    self.woken += 1
                got += pts
                self.score += pts
        if got:
            self.pop("+%d" % got, FIELD.centerx, FIELD.y + 120)
            sound.play("loose", 0.6)

    def clear_level(self):
        bonus = 1000 * self.drops + 2000
        self.score += bonus
        self.pop("Spore party! +%d" % bonus, FIELD.centerx, FIELD.y + 260, WHITE)
        sound.play("fanfare")
        for c in RAINBOW:
            self.fx.burst(FIELD.centerx, FIELD.y + 300, COLOR_RGB[c], n=10, speed=320, shapes=("circle",))
        self.drops = DROPS
        self.next_level()

    def summary(self):
        return "Level %d, %d woken." % (self.level, self.woken)

    def cheer(self):
        if self.over is not None:
            return "Again? Again!"
        if self.ball is not None:
            return "Bounce bounce!"
        return "Wake them up!"

    # -- drawing
    def draw_field(self, surf):
        ox, oy = FIELD.topleft
        surf.blit(_field(), (ox, oy))
        # the sliding cap at the bottom
        bx = ox + self.bucket_x
        cap = pygame.Rect(0, 0, 88, 26)
        cap.midtop = (int(bx), oy + FIELD.h - 34)
        pygame.draw.ellipse(surf, INK, cap.inflate(6, 6))
        pygame.draw.ellipse(surf, (226, 64, 84), cap)
        for k in (-24, 0, 24):
            pygame.draw.circle(surf, WHITE, (int(bx + k), cap.y + 9), 5)
        for p in self.pegs:
            x, y = ox + p.x, oy + p.y
            col = COLOR_RGB[p.color]
            if p.gone:                                      # rounded off, floating away
                k = p.gone / 1.2
                draw_critter(surf, "circle", x, y - k * 60, PEG * (1 - k * 0.5), col, mood="happy", shadow=False)
                continue
            if p.lit:
                pygame.draw.circle(surf, lighten(col, 0.55), (int(x), int(y)), PEG + 6)
            if p.goal:
                sides = SHAPES.index(p.shape) + 3 + (1 if p.lit else 0)
                shape = p.shape if not p.lit else ({4: "square", 5: "pentagon", 6: "hexagon"}.get(sides, sides))
                draw_critter(surf, shape, x, y, PEG + 2, col, mood="happy" if p.lit else "sleep", shadow=False,
                             width=2)
            else:
                draw_body(surf, p.shape, x, y, PEG - 1, lighten(col, 0.35 if not p.lit else 0.05), INK, 2)
        # the launcher cap, and your aim
        lx, ly = ox + LAUNCH[0], oy + LAUNCH[1]
        pygame.draw.ellipse(surf, INK, (lx - 38, ly - 18, 76, 30))
        pygame.draw.ellipse(surf, (250, 110, 170), (lx - 36, ly - 17, 72, 26))
        for k in (-16, 0, 16):
            pygame.draw.circle(surf, WHITE, (int(lx + k), int(ly - 8)), 4)
        if self.ball is None and self.over is None:
            a = math.pi / 2 + self.aim
            px, py, vx, vy = LAUNCH[0], LAUNCH[1] + 14, math.cos(a) * SHOT, math.sin(a) * SHOT
            for k in range(26):                              # the aiming guide: the first of the drop
                for _ in range(3):
                    vy += GRAVITY / 90
                    px += vx / 90
                    py += vy / 90
                if any(math.hypot(px - p.x, py - p.y) < BALL + PEG for p in self.pegs if not p.gone):
                    break
                if k % 2 == 0:
                    pygame.draw.circle(surf, WHITE, (int(ox + px), int(oy + py)), 3)
            if self.drops > 0:
                self.draw_you(surf, lx, ly + 14, BALL)
        else:
            if self.ball is not None:
                b = self.ball
                self.draw_you(surf, ox + b[0], oy + b[1], BALL, rot=(b[0] + b[1]) / BALL)


def _field():
    """The Grove's board: a dusky glade, giant mushrooms far back, glowing spores."""
    def build():
        w, h = FIELD.w // 2, FIELD.h // 2
        p = Pix(w, h, seed=31)
        p.vgrad(0, 0, w, h, (60, 36, 100), (150, 80, 140), steps=8)
        for k in range(5):                                   # giant mushrooms, far back
            x = 20 + k * 48
            hh = 60 + (k * 37) % 50
            p.rect(x - 3, h - hh, 7, hh, (110, 70, 140))
            p.ellipse(x - 22, h - hh - 10, 44, 18, (130, 80, 160))
            p.ellipse(x - 20, h - hh - 10, 40, 10, (150, 100, 180))
        for _ in range(60):
            p.px(p.rng.randrange(w), p.rng.randrange(h), mix((255, 200, 240), (150, 255, 230), p.rng.random()))
        p.rect(0, 0, w, 2, (40, 24, 70))
        p.rect(0, 0, 2, h, (40, 24, 70))
        p.rect(w - 2, 0, 2, h, (40, 24, 70))
        return p.up(2)
    return cached(("sporedrop_field",), build)
