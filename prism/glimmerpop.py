"""Glimmer Pop: the Glimmer Caves' game (in the vein of a bubble shooter).

Crystal shapes hang from the cave roof in colours. You're loaded into the
sling at the bottom, dyed a colour: aim with the arrows, Space to fly.
Bounce off the walls if you like. Where you stick, if three or more of the
same colour touch, they all round off and float away, and anything left
hanging by nothing drops too (worth more). Tab swaps you for the next
colour. Every few shots the roof settles a row lower; if it reaches the
sling, that's the game. Clear the roof for the next cave.
"""

import math

import pygame

from . import sound
from .arcade import FIELD, ArcadeScreen
from .art import draw_critter
from .consts import COLOR_RGB, RAINBOW
from .pixel import Pix, cached, mix
from .widgets import INK, WHITE, draw_colour_mark

R = 18                                   # a cell's radius
COLS = 12
ROW_H = R * 1.732
SHOT = 900.0
SLING = (FIELD.w // 2, FIELD.h - 52)
DEAD_Y = FIELD.h - 110                   # the roof reaching here ends the game
SETTLE = 8                               # shots between the roof settling a row
SHAPE_OF = {"R": "triangle", "Y": "diamond", "G": "pentagon", "C": "hexagon", "B": "square", "M": "circle"}


class GlimmerPopScreen(ArcadeScreen):
    NAME = "Glimmer Pop"
    ZONE = "caves"
    BEST = "glimmerpop_best"
    HELP = ("Fly up into the crystals. Three or more of one colour touching: they round off and float away, "
            "and anything left hanging drops too. The roof settles every few shots.",)
    KEYS = ("<- ->: aim", "Space: fly", "Tab: swap colours")

    def reset(self):
        self.level = 0
        self.next_level()

    def next_level(self):
        self.level += 1
        self.colors = list(RAINBOW[:min(6, 2 + self.level)])
        self.rng.shuffle(self.colors)
        self.cells = {}                              # (row, col) -> (colour, shape)
        self.drop = 0                                # rows the roof has settled
        for row in range(5 + min(3, self.level)):
            for col in range(self.cols_in(row)):
                c = self.rng.choice(self.colors)
                self.cells[(row, col)] = (c, SHAPE_OF[c])         # each colour its own shape: easy to read
        self.aim = 0.0
        self.shots = 0
        self.flying = None
        self.loaded = self._pick()
        self.next = self._pick()
        self.falling = []                            # [x, y, vx, vy, colour, shape, popped]

    def cols_in(self, row):
        return COLS if (row + self.drop) % 2 == 0 else COLS - 1

    def centre(self, row, col):
        off = R if (row + self.drop) % 2 else 0
        return R + 6 + col * 2 * R + off, R + 6 + (row + self.drop) * ROW_H

    def _pick(self):
        present = sorted({c for c, _s in self.cells.values()})
        return self.rng.choice(present or self.colors)

    def status(self):
        return ("cave %d" % self.level, "next settle in %d" % (SETTLE - self.shots % SETTLE),
                "crystals: %d" % len(self.cells))

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and self.over is None:
            if ev.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_UP) and self.flying is None:
                a = -math.pi / 2 + self.aim
                self.flying = [SLING[0], SLING[1], math.cos(a) * SHOT, math.sin(a) * SHOT, self.loaded]
                self.loaded, self.next = self.next, self._pick()
                sound.play("step")
                return True
            if ev.key == pygame.K_TAB and self.flying is None:
                self.loaded, self.next = self.next, self.loaded
                sound.play("ui", 0.5)
                return True
        return super().handle(ev)

    def step(self, dt):
        self.aim = max(-1.35, min(1.35, self.aim + self.axis() * dt * 1.5))
        for f in self.falling:
            f[3] += (-300 if f[6] else 900) * dt
            f[0] += f[2] * dt
            f[1] += f[3] * dt
        self.falling = [f for f in self.falling if -60 < f[1] < FIELD.h + 60]
        if self.flying is None:
            return
        for _ in range(6):
            if self._fly(dt / 6):
                break

    def _fly(self, dt):
        b = self.flying
        b[0] += b[2] * dt
        b[1] += b[3] * dt
        if b[0] < R:
            b[0], b[2] = R, abs(b[2])
            sound.play("tick", 0.3)
        elif b[0] > FIELD.w - R:
            b[0], b[2] = FIELD.w - R, -abs(b[2])
            sound.play("tick", 0.3)
        top = R + 6 + self.drop * ROW_H
        hit = b[1] <= top
        if not hit:
            for (row, col) in self.cells:
                x, y = self.centre(row, col)
                if math.hypot(b[0] - x, b[1] - y) < R * 1.8:
                    hit = True
                    break
        if hit:
            self._stick(b)
            return True
        return False

    def _stick(self, b):
        """Settle into the nearest free cell, then see what matches."""
        best, bd = None, 1e9
        for row in range(0, 20):
            for col in range(self.cols_in(row)):
                if (row, col) in self.cells:
                    continue
                x, y = self.centre(row, col)
                d = math.hypot(b[0] - x, b[1] - y)
                if d < bd and (row == 0 or self._touching(row, col)):
                    best, bd = (row, col), d
        self.flying = None
        if best is None:
            return
        self.cells[best] = (b[4], SHAPE_OF[b[4]])
        sound.play("hit", 0.4)
        group = self._group(best)
        if len(group) >= 3:
            for cell in group:
                c, s = self.cells.pop(cell)
                x, y = self.centre(*cell)
                self.falling.append([x, y, self.rng.uniform(-40, 40), -60, c, s, True])
            n = len(group)
            self.score += 10 * n
            self.pop("+%d" % (10 * n), FIELD.x + b[0], FIELD.y + b[1] - 20)
            sound.play("cast:" + b[4], 0.6)
            dropped = self._unhung()
            if dropped:
                bonus = 20 * (2 ** min(6, len(dropped)))
                self.score += bonus
                self.pop("Drop! +%d" % bonus, FIELD.x + b[0], FIELD.y + b[1] - 50, WHITE)
                sound.play("loose", 0.7)
        self.shots += 1
        if self.shots % SETTLE == 0:
            self.drop += 1
            sound.play("hit", 0.8)
            self.pop("The roof settles...", FIELD.centerx, FIELD.y + 120, (200, 170, 255))
        if not self.cells:
            bonus = 1000 * self.level
            self.score += bonus
            self.pop("Cave cleared! +%d" % bonus, FIELD.centerx, FIELD.y + 300, WHITE)
            sound.play("fanfare")
            self.next_level()
            return
        if any(self.centre(r, c)[1] + R > DEAD_Y for r, c in self.cells):
            self.end()

    def neighbours(self, row, col):
        odd = (row + self.drop) % 2
        around = [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, 1 if odd else -1), (1, 1 if odd else -1)]
        return [(row + dr, col + dc) for dr, dc in around]

    def _touching(self, row, col):
        return any(n in self.cells for n in self.neighbours(row, col))

    def _group(self, start):
        colour = self.cells[start][0]
        seen, todo = {start}, [start]
        while todo:
            cell = todo.pop()
            for n in self.neighbours(*cell):
                if n not in seen and n in self.cells and self.cells[n][0] == colour:
                    seen.add(n)
                    todo.append(n)
        return seen

    def _unhung(self):
        """Everything not hanging from the roof (through others) drops."""
        hung = {c for c in self.cells if c[0] == 0}
        todo = list(hung)
        while todo:
            cell = todo.pop()
            for n in self.neighbours(*cell):
                if n in self.cells and n not in hung:
                    hung.add(n)
                    todo.append(n)
        loose = [c for c in self.cells if c not in hung]
        for cell in loose:
            c, s = self.cells.pop(cell)
            x, y = self.centre(*cell)
            self.falling.append([x, y, self.rng.uniform(-60, 60), 0, c, s, False])
        return loose

    def summary(self):
        return "Cave %d. Glimmering." % self.level

    def cheer(self):
        return "Again? Again!" if self.over is not None else "Pop pop pop!"

    # -- drawing
    def draw_field(self, surf):
        ox, oy = FIELD.topleft
        surf.blit(_cave(), (ox, oy))
        roof = oy + self.drop * ROW_H
        if self.drop:                                         # the roof, settled lower
            pygame.draw.rect(surf, (50, 36, 84), (ox, oy, FIELD.w, int(self.drop * ROW_H)))
            for k in range(0, FIELD.w, 24):
                pygame.draw.polygon(surf, (50, 36, 84), [(ox + k, roof), (ox + k + 24, roof), (ox + k + 12, roof + 10)])
        pygame.draw.line(surf, (255, 140, 170), (ox, oy + DEAD_Y), (ox + FIELD.w, oy + DEAD_Y), 2)
        for (row, col), (c, shape) in self.cells.items():
            x, y = self.centre(row, col)
            draw_critter(surf, shape, ox + x, oy + y, R - 3, COLOR_RGB[c], mood="plain", shadow=False, width=2,
                         look=((self.flying[0] - x) / 300 if self.flying else 0, 0.6))
            draw_colour_mark(surf, c, ox + x + R * 0.5, oy + y - R * 0.5, 6)
        for x, y, vx, vy, c, shape, popped in self.falling:
            draw_critter(surf, "circle" if popped else shape, ox + x, oy + y, R - 3, COLOR_RGB[c],
                         mood="happy" if popped else "wow", shadow=False, width=2)
        # the sling, your aim, and you loaded in it
        sx, sy = ox + SLING[0], oy + SLING[1]
        if self.flying is None and self.over is None:
            a = -math.pi / 2 + self.aim
            px, py, vx, vy = SLING[0], SLING[1], math.cos(a), math.sin(a)
            for k in range(22):
                px += vx * 18
                py += vy * 18
                if px < R or px > FIELD.w - R:
                    vx = -vx
                if py < R + self.drop * ROW_H:
                    break
                pygame.draw.circle(surf, WHITE, (int(ox + px), int(oy + py)), 2 if k % 2 else 3)
        pygame.draw.arc(surf, INK, (sx - 30, sy - 8, 60, 40), math.pi, math.tau, 4)
        if self.flying is None:
            self.draw_you(surf, sx, sy, R - 3, color=COLOR_RGB[self.loaded])
            draw_colour_mark(surf, self.loaded, sx + 14, sy - 14, 7)
        else:
            b = self.flying
            self.draw_you(surf, ox + b[0], oy + b[1], R - 3, color=COLOR_RGB[b[4]], rot=b[1] / 20)
        self.draw_you(surf, sx + 70, sy + 14, 10, color=COLOR_RGB[self.next])
        pygame.draw.circle(surf, WHITE, (sx + 70, sy + 14), 15, 2)


def _cave():
    def build():
        w, h = FIELD.w // 2, FIELD.h // 2
        p = Pix(w, h, seed=8)
        p.vgrad(0, 0, w, h, (40, 28, 76), (90, 60, 140), steps=8)
        for k in range(9):                                     # stalagmites, far back
            x = 10 + k * 27
            hh = 30 + (k * 17) % 40
            p.poly([(x - 8, h), (x, h - hh), (x + 8, h)], (70, 50, 110))
        for _ in range(50):
            p.px(p.rng.randrange(w), p.rng.randrange(h), mix((200, 170, 255), (120, 230, 240), p.rng.random()))
        p.rect(0, 0, w, 3, (30, 20, 56))
        return p.up(2)
    return cached(("glimmer_cave",), build)
