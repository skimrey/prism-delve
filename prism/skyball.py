"""Sky Ball: the Windy Heights' game (in the vein of skee-ball).

Roll up the lane, off the little ramp at the end, and fly. Where you come
down, you drop into a ring: the smaller the ring, the more it's worth, and
the two tiny holes up in the corners are worth the most. The wind is
different every throw (the streamer shows which way and how hard), so lean
into it. Aim with the arrows, hold Space to wind up, let go. Nine throws.
Nothing at stake.
"""

import math

import pygame

from . import sound
from .arcade import FIELD, ArcadeScreen
from .consts import COLOR_RGB, RAINBOW
from .pixel import Pix, cached, mix
from .widgets import INK, WHITE, draw_text, font

BALL = 12
LAUNCH_Y = FIELD.h - 60
RAMP_Y = FIELD.h - 250                      # the lip of the ramp: off you fly
TARGET = (FIELD.w // 2, 190)
RINGS = ((22, 50), (48, 40), (74, 30), (100, 20), (126, 10))
CORNERS = ((70, 96), (FIELD.w - 70, 96))
CORNER_R, CORNER_PTS = 17, 100
THROWS = 9


class SkyBallScreen(ArcadeScreen):
    NAME = "Sky Ball"
    ZONE = "heights"
    BEST = "skyball_best"
    HELP = ("Roll up and off the ramp; come down in a ring. Smaller rings, more points; the tiny corner "
            "holes most of all. The wind changes every throw: watch the streamer.",)
    KEYS = ("<- ->: aim", "hold Space: wind up", "Esc: back")

    def reset(self):
        self.throws = THROWS
        self.landed = []                       # where throws came down: (x, y, points)
        self.new_throw()

    def new_throw(self):
        self.x, self.y = FIELD.w / 2, LAUNCH_Y
        self.vx = self.vy = 0.0
        self.aim = 0.0
        self.charge = 0.0
        self.phase = "aim"                     # aim -> windup -> rolling -> flying -> done
        self.z = self.vz = 0.0
        self.wait = 0.0
        self.wind = self.rng.uniform(-1.0, 1.0) * (0.4 + 0.15 * (THROWS - self.throws))
        self.rot = 0.0

    def status(self):
        return ("throws left: %d" % self.throws, "wind: %s %d" % ("<-" if self.wind < 0 else "->",
                                                                  round(abs(self.wind) * 10)))

    def handle(self, ev):
        if self.over is None:
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_SPACE, pygame.K_RETURN) and self.phase == "aim":
                self.phase = "windup"
            elif ev.type == pygame.KEYUP and ev.key in (pygame.K_SPACE, pygame.K_RETURN) and self.phase == "windup":
                speed = 380 + 360 * self.charge
                self.vx, self.vy = math.sin(self.aim) * speed, -math.cos(self.aim) * speed
                self.phase = "rolling"
                self.throws -= 1
                sound.play("step")
        return super().handle(ev)

    def step(self, dt):
        if self.phase in ("aim", "windup"):
            self.aim = max(-0.3, min(0.3, self.aim + self.axis() * dt * 0.4))
            if self.phase == "windup":
                self.charge = min(1.0, self.charge + dt * 0.7)
            return
        if self.phase == "rolling":
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.vx *= math.exp(-0.4 * dt)
            self.vy *= math.exp(-0.4 * dt)
            self.rot += math.hypot(self.vx, self.vy) * dt / BALL
            sound.roll(0.4)
            if self.y <= RAMP_Y:                                # off the ramp: fly!
                self.phase = "flying"
                self.vz = 230 + (-self.vy) * 0.25
                sound.roll(0)
                sound.play("step", 0.8)
            return
        if self.phase == "flying":
            self.vx += self.wind * 200 * dt
            self.x += self.vx * dt
            self.y += self.vy * dt * 0.75
            self.vz -= 900 * dt
            self.z += self.vz * dt
            self.rot += 8 * dt
            if self.z <= 0:
                self.z = 0
                self._land()
            return
        if self.phase == "done":
            self.wait += dt
            if self.wait > 1.2:
                if self.throws <= 0:
                    self.end()
                else:
                    self.new_throw()

    def _land(self):
        pts = 0
        for cx, cy in CORNERS:
            if math.hypot(self.x - cx, self.y - cy) < CORNER_R:
                pts = CORNER_PTS
        if not pts:
            d = math.hypot(self.x - TARGET[0], self.y - TARGET[1])
            for r, value in RINGS:
                if d < r:
                    pts = value
                    break
        self.score += pts
        self.landed.append((self.x, self.y, pts))
        self.phase = "done"
        self.wait = 0.0
        if pts:
            sound.play("ascend" if pts < 100 else "fanfare", 0.6)
            self.pop("+%d" % pts, FIELD.x + self.x, FIELD.y + self.y - 24, WHITE if pts >= 50 else None)
            for c in RAINBOW[:3 + pts // 25]:
                self.fx.burst(FIELD.x + self.x, FIELD.y + self.y, COLOR_RGB[c], n=3, speed=160, shapes=("circle",))
        else:
            sound.play("loose", 0.4)
            self.pop("off into the sky!", FIELD.x + self.x, FIELD.y + self.y - 24, (200, 220, 255))

    def summary(self):
        hits = sum(1 for _x, _y, p in self.landed if p)
        return "%d of %d in the rings." % (hits, THROWS)

    def cheer(self):
        if self.over is not None:
            return "Again? Again!"
        return {"aim": "Mind the wind!", "windup": "Wind up...", "rolling": "Go go go!",
                "flying": "Wheeeee!", "done": "Ooh!"}[self.phase]

    # -- drawing
    def draw_field(self, surf):
        ox, oy = FIELD.topleft
        t = self.t
        surf.blit(_heights(), (ox, oy))
        for x, y, p in self.landed[-6:]:                       # where the last throws came down
            pygame.draw.circle(surf, (255, 255, 255), (int(ox + x), int(oy + y)), 3)
        # the wind streamer
        sx, sy = ox + FIELD.w - 60, oy + 250
        pygame.draw.line(surf, INK, (sx, sy), (sx, sy - 60), 3)
        for k in range(6):
            wave = math.sin(t * 8 + k) * 3
            px = sx + self.wind * 14 * (k + 1)
            pygame.draw.circle(surf, COLOR_RGB[RAINBOW[k]], (int(px), int(sy - 56 + wave + abs(self.wind) * k * 1.5)), 5)
        draw_text(surf, font(16), "wind", (sx, sy + 12), INK, center=True)
        # you
        if self.phase in ("aim", "windup"):
            for k in range(1, 9):
                ax = self.x + math.sin(self.aim) * k * 26
                ay = self.y - math.cos(self.aim) * k * 26
                pygame.draw.circle(surf, WHITE, (int(ox + ax), int(oy + ay)), 3)
            bar = pygame.Rect(ox + 30, oy + FIELD.h - 190, 18, 150)
            pygame.draw.rect(surf, INK, bar.inflate(6, 6), border_radius=6)
            pygame.draw.rect(surf, (236, 246, 255), bar, border_radius=4)
            h = int(bar.h * self.charge)
            pygame.draw.rect(surf, mix((120, 200, 255), (255, 120, 140), self.charge),
                             (bar.x, bar.bottom - h, bar.w, h), border_radius=4)
        if self.phase != "done" or self.wait < 0.4:
            lift = self.z
            scale = 1 + lift / 300
            if lift > 0:                                         # your shadow on the board
                sh = pygame.Surface((40, 14), pygame.SRCALPHA)
                pygame.draw.ellipse(sh, (*INK, 70), sh.get_rect())
                surf.blit(sh, (ox + self.x - 20, oy + self.y - 7))
            r = BALL * scale * (1 - (min(1.0, self.wait / 0.4) if self.phase == "done" else 0))
            if r > 1:
                self.draw_you(surf, ox + self.x, oy + self.y - lift * 0.6, r, rot=self.rot)


def _heights():
    """A floating island: the lane and its ramp, the board of rings, the sky all round."""
    def build():
        w, h = FIELD.w // 2, FIELD.h // 2
        p = Pix(w, h, seed=4)
        p.vgrad(0, 0, w, h, (120, 180, 250), (226, 244, 255), steps=7)
        for k in range(5):                                     # clouds drifting past below
            p.ellipse(p.rng.randrange(w) - 20, p.rng.randrange(h), 60, 16, (255, 255, 255))
        # the board: a round island, rings in rainbow, two tiny corner holes
        tx, ty = TARGET[0] // 2, TARGET[1] // 2
        p.disc(tx, ty + 4, 76, (90, 170, 90))
        p.disc(tx, ty, 74, (130, 210, 110))
        for (r, _v), c in zip(reversed(RINGS), ("M", "B", "C", "G", "Y")):
            p.disc(tx, ty, r // 2 + 1, (40, 30, 60))
            p.disc(tx, ty, r // 2, mix(COLOR_RGB[c], (255, 255, 255), 0.25))
        p.disc(tx, ty, RINGS[0][0] // 2, COLOR_RGB["R"])
        p.disc(tx, ty, 3, (40, 30, 60))
        for cx, cy in CORNERS:
            p.disc(cx // 2, cy // 2, CORNER_R // 2 + 3, (130, 210, 110))
            p.disc(cx // 2, cy // 2, CORNER_R // 2 + 1, (40, 30, 60))
            p.disc(cx // 2, cy // 2, CORNER_R // 2, (255, 214, 90))
        # the lane, up to the ramp
        lane = (w // 2 - 40, RAMP_Y // 2, 80, h - RAMP_Y // 2)
        p.rect(*lane, (200, 170, 130))
        for y in range(RAMP_Y // 2, h, 5):
            p.line((lane[0], y), (lane[0] + lane[2], y), (184, 152, 112))
        p.rect(lane[0], RAMP_Y // 2, lane[2], 6, (240, 210, 160))          # the ramp's lip
        p.rect(lane[0], RAMP_Y // 2 + 6, lane[2], 2, (150, 120, 90))
        p.rect(lane[0] - 3, RAMP_Y // 2, 3, h, (150, 120, 90))
        p.rect(lane[0] + lane[2], RAMP_Y // 2, 3, h, (150, 120, 90))
        return p.up(2)
    return cached(("skyball_bg",), build)
