"""Curl: the Frost's game (in the vein of curling).

You're the stone. Aim with the arrows, hold Space to wind up, let go to
slide down the ice toward the rings. While you slide, hold Space to sweep:
the ice ahead gets slicker and you go further. A Frost local takes turns
with you, four stones each; whoever's closest to the middle scores one for
every stone nearer than the other side's best. Knock them out of the way if
you like: everyone's a marble here. Three ends. Nothing at stake.
"""

import math

import pygame

from . import sound
from .arcade import FIELD, ArcadeScreen
from .art import draw_critter
from .pixel import Pix, cached, mix
from .widgets import INK, WHITE, draw_text, font

STONE = 16
HOUSE = (FIELD.w // 2, 130)
RINGS = (74, 52, 30, 9)
START = (FIELD.w // 2, 560)
FRICTION, SWEPT = 95.0, 52.0                  # how fast the ice slows you (px/s per s), and when swept
POWER = (220.0, 420.0)
STONES = 4
ENDS = 3


class Stone:
    def __init__(self, mine):
        self.mine = mine
        self.x, self.y = START
        self.vx = self.vy = 0.0
        self.out = False
        self.rot = 0.0

    def moving(self):
        return math.hypot(self.vx, self.vy) > 2


class CurlScreen(ArcadeScreen):
    NAME = "Curl"
    ZONE = "frost"
    BEST = "curl_best"
    HELP = ("Slide down the ice to the rings. Hold Space while you slide to sweep: you'll go further. "
            "Closest to the middle scores, one for every stone nearer than their best.",)
    KEYS = ("<- ->: aim", "hold Space: wind up", "Space while sliding: sweep")

    def reset(self):
        self.end_no = 1
        self.you_pts = self.them_pts = 0
        self.rival = ((150, 200, 246), 11)         # a Frost local: icy blue, eleven sides
        self.new_end()

    def new_end(self):
        self.stones = []
        self.throws = 0                            # stones thrown this end (alternating, you first)
        self.phase = "aim"
        self.aim = 0.0
        self.charge = 0.0
        self.charging = False
        self.wait = 0.0
        self.end_words = None

    def mine_next(self):
        return self.throws % 2 == 0

    def status(self):
        return ("end %d of %d" % (self.end_no, ENDS), "you %d : %d them" % (self.you_pts, self.them_pts),
                "stones left: %d" % max(0, STONES - (self.throws + 1) // 2))

    def handle(self, ev):
        if self.over is None and self.phase in ("aim", "slide"):
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                if self.phase == "aim" and self.mine_next():
                    self.charging = True
                return super().handle(ev)
            if ev.type == pygame.KEYUP and ev.key in (pygame.K_SPACE, pygame.K_RETURN) and self.charging:
                self.charging = False
                self.throw(True, self.aim, POWER[0] + (POWER[1] - POWER[0]) * self.charge)
        return super().handle(ev)

    def throw(self, mine, aim, speed):
        s = Stone(mine)
        s.vx, s.vy = math.sin(aim) * speed, -math.cos(aim) * speed
        self.stones.append(s)
        self.throws += 1
        self.phase = "slide"
        self.charge = 0.0
        sound.play("step")

    def step(self, dt):
        if self.phase == "aim":
            if self.mine_next():
                self.aim = max(-0.22, min(0.22, self.aim + self.axis() * dt * 0.35))
                if self.charging:
                    self.charge = min(1.0, self.charge + dt * 0.6)
            else:
                self.wait += dt
                if self.wait > 0.8:
                    self.wait = 0.0
                    self._rival_throw()
        elif self.phase == "slide":
            sweeping = bool(self.held & {pygame.K_SPACE, pygame.K_RETURN}) and self.stones[-1].mine
            for _ in range(4):
                self._move(dt / 4, sweeping)
            if sweeping and int(self.t * 10) % 2 == 0:
                s = self.stones[-1]
                self.fx.burst(FIELD.x + s.x, FIELD.y + s.y - STONE - 6, WHITE, n=1, speed=60, shapes=("circle",))
            speed = max((math.hypot(s.vx, s.vy) for s in self.stones if not s.out), default=0.0)
            sound.roll(min(1.0, speed / 500) * 0.5)
            if not any(s.moving() for s in self.stones if not s.out):
                sound.roll(0)
                if self.throws >= STONES * 2:
                    self._score_end()
                else:
                    self.phase = "aim"
        elif self.phase == "scored":
            self.wait += dt
            if self.wait > 2.6:
                self.wait = 0.0
                if self.end_no >= ENDS:
                    self.score += 300 if self.you_pts > self.them_pts else 100
                    self.end()
                else:
                    self.end_no += 1
                    self.new_end()

    def _rival_throw(self):
        """The rival: knocks your best stone out if it's sitting pretty, else
        draws to the middle. Not perfect."""
        mine = [s for s in self.stones if s.mine and not s.out]
        best = min(mine, key=lambda s: self._dist(s), default=None)
        err = self.rng.uniform(-0.025, 0.025)
        if best is not None and self._dist(best) < RINGS[1] and self.rng.random() < 0.6:
            aim = math.atan2(best.x - START[0], START[1] - best.y) + err
            self.throw(False, aim, POWER[1] * 0.95)
        else:
            aim = err + math.atan2(HOUSE[0] - START[0], START[1] - HOUSE[1])
            d = START[1] - HOUSE[1]
            speed = math.sqrt(2 * FRICTION * d) * self.rng.uniform(0.95, 1.04)
            self.throw(False, aim, speed)

    def _dist(self, s):
        return math.hypot(s.x - HOUSE[0], s.y - HOUSE[1])

    def _move(self, dt, sweeping):
        live = [s for s in self.stones if not s.out]
        for i, s in enumerate(live):
            sp = math.hypot(s.vx, s.vy)
            if sp > 0:
                f = (SWEPT if (sweeping and s is self.stones[-1]) else FRICTION) * dt
                k = max(0.0, sp - f) / sp
                s.vx *= k
                s.vy *= k
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.rot += sp * dt / STONE
            if s.x < STONE or s.x > FIELD.w - STONE or s.y < STONE:       # off the ice: out
                s.out = True
                sound.play("loose", 0.4)
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if 0 < d < STONE * 2:
                    nx, ny = dx / d, dy / d
                    push = (STONE * 2 - d) / 2
                    a.x, a.y = a.x - nx * push, a.y - ny * push
                    b.x, b.y = b.x + nx * push, b.y + ny * push
                    rel = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny
                    if rel > 0:
                        a.vx, a.vy = a.vx - rel * nx * 0.95, a.vy - rel * ny * 0.95
                        b.vx, b.vy = b.vx + rel * nx * 0.95, b.vy + rel * ny * 0.95
                        sound.play("hit", min(1.0, rel / 300))
                        self.fx.burst(FIELD.x + (a.x + b.x) / 2, FIELD.y + (a.y + b.y) / 2, WHITE, n=5,
                                      speed=120, shapes=("circle",))

    def _score_end(self):
        live = [s for s in self.stones if not s.out and self._dist(s) < RINGS[0] + STONE]
        live.sort(key=self._dist)
        pts, who = 0, None
        if live:
            who = live[0].mine
            other = next((self._dist(s) for s in live if s.mine != who), 1e9)
            pts = sum(1 for s in live if s.mine == who and self._dist(s) < other)
        if who:
            self.you_pts += pts
            self.score += 200 * pts
            self.end_words = "You score %d!" % pts
            sound.play("fanfare", 0.6)
        elif who is False:
            self.them_pts += pts
            self.end_words = "They score %d." % pts
        else:
            self.end_words = "Nobody in the rings!"
        self.score += 25 * sum(1 for s in live if s.mine)          # a little something for every stone in
        self.phase = "scored"
        self.wait = 0.0

    def summary(self):
        return "You %d, them %d. %s" % (self.you_pts, self.them_pts,
                                       "You win the ice!" if self.you_pts > self.them_pts else "Good sliding.")

    def cheer(self):
        if self.over is not None:
            return "Again? Again!"
        if self.phase == "slide" and self.stones and self.stones[-1].mine:
            return "Sweep! Sweep!"
        return "Slide it in!"

    # -- drawing
    def draw_field(self, surf):
        ox, oy = FIELD.topleft
        surf.blit(_sheet(), (ox, oy))
        rival_col, rival_sides = self.rival
        for s in self.stones:
            if s.out:
                continue
            if s.mine:
                self.draw_you(surf, ox + s.x, oy + s.y, STONE, rot=s.rot)
            else:
                draw_critter(surf, rival_sides, ox + s.x, oy + s.y, STONE, rival_col, mood="happy", rot=s.rot,
                             shadow=False)
        if self.phase == "aim" and self.over is None:
            if self.mine_next():
                for k in range(1, 14):                         # the line you're aiming down
                    x = START[0] + math.sin(self.aim) * k * 32
                    y = START[1] - math.cos(self.aim) * k * 32
                    pygame.draw.circle(surf, WHITE, (int(ox + x), int(oy + y)), 3)
                self.draw_you(surf, ox + START[0], oy + START[1], STONE)
                bar = pygame.Rect(ox + FIELD.w - 40, oy + 420, 18, 160)     # wind-up meter
                pygame.draw.rect(surf, INK, bar.inflate(6, 6), border_radius=6)
                pygame.draw.rect(surf, (210, 230, 250), bar, border_radius=4)
                h = int(bar.h * self.charge)
                pygame.draw.rect(surf, mix((120, 200, 255), (255, 120, 140), self.charge),
                                 (bar.x, bar.bottom - h, bar.w, h), border_radius=4)
            else:
                draw_critter(surf, rival_sides, ox + START[0], oy + START[1], STONE, rival_col, mood="plain",
                             shadow=False)
        if self.phase == "scored" and self.end_words:
            draw_text(surf, font(34), self.end_words, (ox + FIELD.w // 2, oy + 300), WHITE, center=True, shadow=INK)
        # whose stones are left
        for k in range(STONES):
            mine_left = STONES - (self.throws + 1) // 2
            theirs_left = STONES - self.throws // 2
            if k < mine_left:
                self.draw_you(surf, ox + 20 + k * 22, oy + FIELD.h - 20, 8)
            if k < theirs_left:
                draw_critter(surf, rival_sides, ox + FIELD.w - 20 - k * 22, oy + FIELD.h - 20, 8, rival_col,
                             mood="plain", shadow=False, width=2)


def _sheet():
    """The ice: pale blue, scuffed, the rings at the far end in cold rainbow."""
    def build():
        w, h = FIELD.w // 2, FIELD.h // 2
        p = Pix(w, h, seed=5)
        p.vgrad(0, 0, w, h, (226, 240, 255), (200, 226, 250), steps=6)
        for _ in range(90):
            x, y = p.rng.randrange(w), p.rng.randrange(h)
            p.line((x, y), (x + p.rng.randint(-6, 6), y + p.rng.randint(-2, 2)), (236, 246, 255))
        hx, hy = HOUSE[0] // 2, HOUSE[1] // 2
        for r, c in zip(RINGS, ((120, 160, 240), (255, 255, 255), (240, 120, 150), (255, 255, 255))):
            p.disc(hx, hy, r // 2, c)
        p.disc(hx, hy, RINGS[3] // 2 + 1, (120, 160, 240))
        p.line((0, hy), (w, hy), (150, 180, 220))
        p.line((hx, 0), (hx, h), (150, 180, 220))
        p.line((0, (START[1] - 40) // 2), (w, (START[1] - 40) // 2), (240, 130, 150))
        p.line((0, hy + 60), (w, hy + 60), (170, 200, 240))             # the hog line, faint
        for _ in range(40):                                              # glints in the ice
            x, y = p.rng.randrange(6, w - 6), p.rng.randrange(4, h)
            p.px(x, y, (255, 255, 255))
            if p.rng.random() < 0.3:
                p.px(x - 1, y, (246, 252, 255))
                p.px(x + 1, y, (246, 252, 255))
        for side in (0, 1):                                              # snowbanks down both sides
            for y in range(0, h, 2):
                bump = 3 + int(2 * math.sin(y * 0.21 + side * 2) + 1.2 * math.sin(y * 0.07 + side))
                x0 = 0 if side == 0 else w - bump
                p.rect(x0, y, bump, 2, (250, 252, 255))
                p.px(bump if side == 0 else w - bump - 1, y, (184, 208, 236))
                p.px(bump if side == 0 else w - bump - 1, y + 1, (184, 208, 236))
        for x, y in ((3, 14), (w - 6, 40), (2, 120), (w - 5, 190), (3, 250)):    # little pines in the banks
            for k in range(5):
                p.rect(x - k // 2, y + k * 2, 1 + k, 2, (70, 140, 110) if k % 2 else (90, 160, 124))
            p.rect(x - 2, y, 5, 1, (255, 255, 255))
            p.px(x, y + 10, (110, 80, 60))
        p.rect(0, 0, w, 2, (140, 170, 210))
        return p.up(2)
    return cached(("curl_sheet",), build)
