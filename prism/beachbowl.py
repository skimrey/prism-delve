"""Beach Bowl: the Coast's game (in the vein of bowling).

You roll until you hit something. That's the whole game, and you're very
good at it. Ten little sandcastles stand at the end of a boardwalk lane:
slide along the start with the arrows, hold Space to wind up (and lean with
the arrows while you do, for a curve), let go to roll. Knock them all down
in one go for a strike. Five frames, two rolls each, the usual bowling
sums. Nothing at stake; the sandcastles build themselves back up.
"""

import math

import pygame

from . import sound
from .arcade import FIELD, ArcadeScreen
from .art import draw_body
from .consts import COLOR_RGB, RAINBOW
from .pixel import Pix, cached, mix
from .widgets import INK, WHITE, draw_text, font

LANE_W, LANE_L = 1.0, 10.0                 # the lane, in "lane units" (x across -0.5..0.5, y away)
BALL, PIN = 0.11, 0.06
PIN_Y = 8.4
PIN_SPACING = 0.2
FRAMES = 5
HORIZON, DROP, SPREAD, DIST = FIELD.y + 160, 820.0, 720.0, 2.0
SHAPES = ("triangle", "square", "pentagon", "diamond")


CAM = [0.0]                                 # how far up the lane the view has followed you


def project(x, y):
    """Lane coordinates to the screen: (x, y, pixels per lane unit). Near
    is at the bottom, the pins far up the boardwalk; the view follows you."""
    y = max(-1.5, y - CAM[0])
    k = SPREAD / (y + DIST)
    return FIELD.centerx + x * k, HORIZON + DROP / (y + DIST), k


class Pin:
    def __init__(self, x, y, i):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.down = 0.0                         # how far over it's toppled (0 standing, 1 flat)
        self.i = i

    @property
    def standing(self):
        return self.down < 0.5


class BeachBowlScreen(ArcadeScreen):
    NAME = "Beach Bowl"
    ZONE = "coast"
    BEST = "beachbowl_best"
    HELP = ("Roll until you hit something: ten sandcastles at the end of the boardwalk. Lean while you "
            "wind up for a curve. All ten at once is a strike.",)
    KEYS = ("<- ->: where to start", "hold Space: wind up", "<- -> while winding: lean")

    def reset(self):
        CAM[0] = 0.0
        self.frame = 1
        self.roll_no = 1                      # 1 or 2 (3 in the last frame, after a strike or spare)
        self.rolls = []                       # pins knocked, roll by roll
        self.set_pins()
        self.new_ball()

    def set_pins(self):
        self.pins = []
        i = 0
        for row in range(4):
            for k in range(row + 1):
                x = (k - row / 2) * PIN_SPACING
                self.pins.append(Pin(x, PIN_Y + row * PIN_SPACING * 0.87, i))
                i += 1

    def new_ball(self):
        self.bx, self.by = 0.0, 0.4
        self.bvx = self.bvy = 0.0
        self.curve = 0.0
        self.lean = 0.0
        self.phase = "aim"                     # aim -> windup -> rolling -> settle
        self.charge = 0.0
        self.wait = 0.0
        self.standing_before = sum(1 for p in self.pins if p.standing)
        self.gutter = False
        self.rot = 0.0

    def status(self):
        return ("frame %d of %d" % (self.frame, FRAMES), "roll %d" % self.roll_no,
                "pins standing: %d" % sum(1 for p in self.pins if p.standing))

    def handle(self, ev):
        if self.over is None:
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_SPACE, pygame.K_RETURN) and self.phase == "aim":
                self.phase = "windup"
            elif ev.type == pygame.KEYUP and ev.key in (pygame.K_SPACE, pygame.K_RETURN) and self.phase == "windup":
                self.bvy = 4.0 + 7.0 * self.charge
                self.curve = self.lean * 0.9
                self.phase = "rolling"
                sound.play("step")
        return super().handle(ev)

    def step(self, dt):
        if self.phase == "aim":
            self.bx = max(-0.42, min(0.42, self.bx + self.axis() * dt * 0.6))
        elif self.phase == "windup":
            self.charge = min(1.0, self.charge + dt * 0.8)
            self.lean = max(-1.0, min(1.0, self.lean + self.axis() * dt * 2.0))
        target = max(0.0, min(PIN_Y - 3.2, self.by - 1.2)) if self.phase in ("rolling", "settle") else 0.0
        CAM[0] += (target - CAM[0]) * min(1.0, dt * (4 if target else 2.5))
        if self.phase == "rolling":
            for _ in range(6):
                self._move(dt / 6)
            sound.roll(min(1.0, self.bvy / 11) * 0.5)
            moving = abs(self.bvy) > 0.05 or any(math.hypot(p.vx, p.vy) > 0.05 for p in self.pins)
            if self.by > LANE_L + 1.5 or (not moving and self.by > PIN_Y - 1):
                self.phase = "settle"
                self.wait = 0.0
                sound.roll(0)
        elif self.phase == "settle":
            for p in self.pins:                       # toppling pins finish falling
                if p.down > 0:
                    p.down = min(1.0, p.down + dt * 3)
            self.wait += dt
            if self.wait > 1.4:
                self._tally()

    def _move(self, dt):
        if not self.gutter:
            self.bvx += self.curve * dt * (1 if self.by > 4 else 0.3)
        self.bx += self.bvx * dt
        self.by += self.bvy * dt
        self.rot += self.bvy * dt / BALL * 0.3
        if abs(self.bx) > LANE_W / 2 and not self.gutter:            # in the gutter: straight on, past the pins
            self.gutter = True
            self.bx = math.copysign(LANE_W / 2 + 0.06, self.bx)
            self.bvx = 0.0
            sound.play("tick", 0.6)
        for p in self.pins:
            if p.down >= 1:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= math.exp(-2.5 * dt)
            p.vy *= math.exp(-2.5 * dt)
            if p.down > 0:
                p.down = min(1.0, p.down + dt * 4)
            if not self.gutter:
                self._hit(self.bx, self.by, BALL, p, ball=True)
        for i, a in enumerate(self.pins):                 # pins knock pins
            for b in self.pins[i + 1:]:
                if a.down >= 1 and b.down >= 1:
                    continue
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if 0 < d < PIN * 2:
                    nx, ny = dx / d, dy / d
                    rel = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny
                    push = (PIN * 2 - d) / 2
                    a.x, a.y, b.x, b.y = a.x - nx * push, a.y - ny * push, b.x + nx * push, b.y + ny * push
                    if rel > 0:
                        a.vx, a.vy = a.vx - rel * nx, a.vy - rel * ny
                        b.vx, b.vy = b.vx + rel * nx, b.vy + rel * ny
                        for p in (a, b):
                            if p.down == 0 and math.hypot(p.vx, p.vy) > 0.4:
                                p.down = 0.01
                                sound.play("hit", 0.35)

    def _hit(self, x, y, r, p, ball=False):
        dx, dy = p.x - x, p.y - y
        d = math.hypot(dx, dy)
        if 0 < d < r + PIN:
            nx, ny = dx / d, dy / d
            p.x, p.y = x + nx * (r + PIN), y + ny * (r + PIN)
            rel = self.bvx * nx + self.bvy * ny
            if rel > 0:
                p.vx += nx * rel * 1.6
                p.vy += ny * rel * 1.6
                self.bvx -= nx * rel * 0.25
                self.bvy -= ny * rel * 0.25
                if p.down == 0:
                    p.down = 0.01
                    sound.play("hit", 0.6)
                    self.fx.burst(*project(p.x, p.y)[:2], (250, 226, 170), n=4, speed=100, shapes=("square",))

    def _tally(self):
        standing = sum(1 for p in self.pins if p.standing)
        knocked = self.standing_before - standing
        self.rolls.append(knocked)
        last = self.frame == FRAMES
        words = None
        if self.roll_no == 1 and standing == 0:
            words = "STRIKE!"
        elif self.roll_no == 2 and standing == 0:
            words = "Spare!"
        elif knocked == 0:
            words = "Gutter!" if self.gutter else "Missed!"
        if words:
            self.pop(words, FIELD.centerx, FIELD.y + 260, WHITE if standing == 0 else (200, 220, 255))
            if standing == 0:
                sound.play("fanfare", 0.6)
                for c in RAINBOW:
                    self.fx.burst(FIELD.centerx, FIELD.y + 200, COLOR_RGB[c], n=5, speed=260, shapes=("circle",))
        frame_done = (standing == 0 and not last) or self.roll_no >= 2 and not last
        if last:
            # the last frame: a third roll after a strike or spare
            first = self.rolls[-self.roll_no] if self.roll_no <= len(self.rolls) else 0
            extra = (self.roll_no == 1 and standing == 0) or (self.roll_no == 2 and (first == 10 or standing == 0))
            if self.roll_no >= 3 or (self.roll_no == 2 and not extra):
                self.score = self.total()
                self.end()
                return
            self.roll_no += 1
            if standing == 0:
                self.set_pins()
            else:
                self.pins = [p for p in self.pins if p.standing]
        elif frame_done:
            self.frame += 1
            self.roll_no = 1
            self.set_pins()
        else:
            self.roll_no += 1
            self.pins = [p for p in self.pins if p.standing]
        self.score = self.total()
        self.new_ball()

    def total(self):
        """Bowling sums: a strike adds the next two rolls, a spare the next one."""
        rolls, score, i = self.rolls, 0, 0
        for f in range(FRAMES):
            if i >= len(rolls):
                break
            if rolls[i] == 10:
                score += 10 + sum(rolls[i + 1:i + 3])
                i += 1
            elif i + 1 < len(rolls) and rolls[i] + rolls[i + 1] == 10:
                score += 10 + sum(rolls[i + 2:i + 3])
                i += 2
            else:
                score += sum(rolls[i:i + 2])
                i += 2
        return score * 10

    def summary(self):
        return "%d pins, %d strikes." % (sum(self.rolls), sum(1 for r in self.rolls if r == 10))

    def cheer(self):
        if self.over is not None:
            return "Again? Again!"
        return {"aim": "Line it up...", "windup": "Wind up!", "rolling": "Rooollll!", "settle": "Ooh!"}[self.phase]

    # -- drawing
    def draw_field(self, surf):
        surf.set_clip(FIELD)
        self._draw_lane(surf)
        surf.set_clip(None)
        self._sheet(surf)

    def _draw_lane(self, surf):
        surf.blit(_boardwalk(), FIELD.topleft)
        # the lane: planks in perspective, and the gutters
        for y0 in range(int(CAM[0]) - 1, int(LANE_L) + 2):
            y1 = y0 + 1
            for side, x0, x1, col in ((-1, -0.5, 0.5, (236, 206, 150)), (0, -0.62, -0.5, (150, 120, 100)),
                                      (1, 0.5, 0.62, (150, 120, 100))):
                pts = [project(x0, y0)[:2], project(x1, y0)[:2], project(x1, y1)[:2], project(x0, y1)[:2]]
                c = col if y0 % 2 or side else mix(col, (255, 255, 255), 0.12)
                pygame.draw.polygon(surf, c, pts)
        for k in range(1, 8):                                  # board seams
            x = -0.5 + k / 8
            pygame.draw.line(surf, (210, 176, 120), project(x, CAM[0] - 1)[:2], project(x, LANE_L + 1)[:2], 1)
        for k in range(5):                                     # aiming arrows
            x = (k - 2) * 0.12
            ax, ay, kk = project(x, 4.5)
            kk = min(kk, 120)                                  # don't loom when you roll over them
            pygame.draw.polygon(surf, (200, 90, 90), [(ax, ay - kk * 0.2), (ax - kk * 0.04, ay), (ax + kk * 0.04, ay)])
        pygame.draw.line(surf, INK, project(-0.5, CAM[0] - 1)[:2], project(-0.5, LANE_L + 1)[:2], 2)
        pygame.draw.line(surf, INK, project(0.5, CAM[0] - 1)[:2], project(0.5, LANE_L + 1)[:2], 2)
        # pins, far ones first
        for p in sorted(self.pins, key=lambda p: -p.y):
            if p.down >= 1 and self.phase != "settle":
                continue
            sx, sy, k = project(p.x, p.y)
            size = max(4, k * PIN * 2.3)
            col = COLOR_RGB[RAINBOW[p.i % 6]]
            if p.down < 0.5:
                draw_body(surf, SHAPES[p.i % 4], sx, sy - size, size, (250, 226, 170), INK, 2)
                pygame.draw.rect(surf, col, (sx - size * 0.5, sy - size * 2.1, size, size * 0.35))
                pygame.draw.line(surf, INK, (sx, sy - size * 2.1), (sx, sy - size * 2.7), 2)
                pygame.draw.polygon(surf, col, [(sx, sy - size * 2.7), (sx + size * 0.6, sy - size * 2.5),
                                                (sx, sy - size * 2.3)])
            else:                                              # knocked over: lying flat, crumbling
                rect = pygame.Rect(0, 0, int(size * 2.2), int(size * 0.8))
                rect.center = (int(sx), int(sy - size * 0.3))
                pygame.draw.ellipse(surf, (250, 226, 170), rect)
                pygame.draw.ellipse(surf, INK, rect, 2)
        # you
        if self.by < LANE_L + 1.5:
            sx, sy, k = project(self.bx, self.by)
            r = max(4, k * BALL * 2.0)
            self.draw_you(surf, sx, sy - r, r, rot=self.rot)
        if self.phase in ("aim", "windup"):
            sx, sy, k = project(self.bx, self.by)
            for d in range(1, 6):                               # where you're pointing
                tx, ty, _k = project(self.bx + self.lean * 0.03 * d * d, self.by + d * 1.6)
                pygame.draw.circle(surf, WHITE, (int(tx), int(ty)), 3)
            bar = pygame.Rect(FIELD.right - 40, FIELD.y + 420, 18, 160)
            pygame.draw.rect(surf, INK, bar.inflate(6, 6), border_radius=6)
            pygame.draw.rect(surf, (250, 236, 210), bar, border_radius=4)
            h = int(bar.h * self.charge)
            pygame.draw.rect(surf, mix((120, 200, 255), (255, 120, 140), self.charge),
                             (bar.x, bar.bottom - h, bar.w, h), border_radius=4)
            if self.phase == "windup":
                draw_text(surf, font(18), "lean %+d" % round(self.lean * 5), (FIELD.right - 50, FIELD.y + 396), WHITE,
                          center=True, shadow=INK)

    def _sheet(self, surf):
        x0, y0 = FIELD.x + 12, FIELD.y + 10
        rolls = list(self.rolls)
        i = 0
        for f in range(FRAMES):
            box = pygame.Rect(x0 + f * 56, y0, 52, 40)
            pygame.draw.rect(surf, (255, 250, 238), box, border_radius=6)
            pygame.draw.rect(surf, INK, box, 2, border_radius=6)
            marks = []
            if i < len(rolls):
                if rolls[i] == 10 and f < FRAMES - 1:
                    marks, i = ["X"], i + 1
                else:
                    a = rolls[i]
                    marks.append("X" if a == 10 else str(a) if a else "-")
                    if i + 1 < len(rolls):
                        b = rolls[i + 1]
                        marks.append("/" if a + b == 10 and a != 10 else "X" if b == 10 else str(b) if b else "-")
                    i += 2 if f < FRAMES - 1 else len(rolls)
            draw_text(surf, font(18), " ".join(marks), box.center, INK, center=True)


def _boardwalk():
    """The Coast behind the lane: sea, sky, a little sun, the boardwalk."""
    def build():
        w, h = FIELD.w // 2, FIELD.h // 2
        p = Pix(w, h, seed=2)
        p.vgrad(0, 0, w, 80, (110, 150, 230), (255, 200, 170), steps=6)
        p.disc(w - 40, 40, 14, (255, 230, 170))
        p.rect(0, 70, w, 10, (80, 150, 220))
        for x in range(0, w, 6):
            p.px(x + (x // 6) % 3, 72, (220, 240, 255))
        p.rect(0, 80, w, h - 80, (200, 164, 120))
        for y in range(84, h, 6):
            p.line((0, y), (w, y), (180, 146, 104))
        return p.up(2)
    return cached(("beachbowl_bg",), build)
