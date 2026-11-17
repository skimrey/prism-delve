"""Roll-Off: the spheres' favourite game, played in the Meadow.

A bowl painted in rings, floating over a soft pool of colour. Everyone rolls
onto it; the last one still on it wins the round. Falling off is the best
part (you land in the colour pool with a splash, and bounce right back for
the next round), so nobody minds losing.

Two ways to play (the host offers both):
    bump   steer your own marble (arrows) and dash (Space) into the others.
           The bowl slowly shrinks, so every round ends.
    tilt   tip the whole bowl (arrows). Every marble rolls downhill; yours
           grips a little better than theirs. Roll everyone else off.

Drawn in 3D with a small perspective projection: the bowl is a tilted disc,
marbles are shaded spheres with shadows. Everything else is the same 2D
shapes-and-ink style as the rest of the game.
"""

import math
import random

import pygame

from . import sound
from .art import Particles, draw_critter, draw_player, ease_out, lighten, mix
from .consts import COLOR_RGB, RAINBOW
from .scene import heading
from .world import shape_of
from .screens import Screen
from .widgets import INK, PAPER, WHITE, draw_card, draw_text, draw_wrapped, font

ARENA_R = 6.0                  # bowl radius (world units)
MARBLE_R = 0.62
PITCH = math.radians(38)       # how steeply the camera looks down at the bowl
DIST = 15.0
FOCAL = 760.0
CENTER = (480, 300)
POOL_Z = -4.5                  # the colour pool far below
SHRINK_AFTER, SHRINK_RATE, MIN_R = 10.0, 0.35, 1.5
FLOAT_R = 9.0                  # where splashed marbles bob about in the pool...
FLOAT_SLOTS = (0.12, math.pi - 0.12, -0.22, math.pi + 0.22, 0.36, math.pi - 0.36)   # ...either side
DASH, DASH_COOLDOWN = 7.5, 1.0
MAX_TILT = 0.28
TILT_GRIP, TILT_CLIMB = 2.6, 3.5  # tilt: how well you grip; how hard they scramble uphill

FALL_LINES = ("Wheeeee!", "Splash time!", "Best part!", "Whoops-a-roll!", "Again! Again!",
              "Weeeeee!")
BUMP_LINES = ("Boop!", "Bonk!", "Hee!", "Gotcha!", "Oof, nice one!")
WIN_LINES = ("Yay!", "Still on!", "Wobbly... but on!", "Hee hee!")
CHEER_LINES = ("Everybody back on!", "Again! Again!", "That was the best one!", "Rematch!")


NAMES = {"R": "Red", "Y": "Yellow", "G": "Green", "C": "Cyan", "B": "Blue", "M": "Magenta"}
REGULARS = (("Y", "triangle"), ("R", "square"), ("G", "pentagon"))
REGULAR_SIDES = {("Y", "triangle"): 20, ("R", "square"): 24, ("G", "pentagon"): 14}


def rivals(rescued=()):
    """Who's playing today: three regulars from the Meadow, plus whoever you
    brought out of the towers. (name, colour, what it used to be)"""
    from .consts import TOWERS
    out = [(NAMES[c], c, was) for c, was in REGULARS]
    for tid in sorted(rescued):
        f = TOWERS[tid]["friend"]
        out.append((NAMES[f["color"]], f["color"], f["was"]))
    return out[:5]


PX = 3                          # the arena's pixels are 3x3 screen pixels
LOW_W, LOW_H = 320, 214
THEMES = {                      # each zone's bowl: sky, pool, side, rings; and how it plays
    "meadow": {"sky": ((112, 196, 255), (214, 244, 255)), "pool": (200, 236, 255), "side": (150, 120, 200),
               "rings": [(255, 160, 170), (255, 226, 140), (160, 230, 170), (150, 226, 246), (170, 180, 255),
                         (230, 170, 246)],
               "blobs": [(255, 150, 160), (255, 220, 130), (150, 220, 160), (140, 220, 240), (160, 170, 250),
                         (220, 160, 240)], "grip": 1.0, "bounce": 1.05},
    "grove": {"sky": ((70, 44, 120), (236, 140, 190)), "pool": (110, 70, 150), "side": (240, 228, 206),
              "rings": [(226, 64, 84), (240, 90, 104), (226, 64, 84), (240, 90, 104), (226, 64, 84)],
              "blobs": [(150, 255, 230), (255, 190, 240), (220, 255, 160)], "grip": 1.0, "bounce": 1.4,
              "spots": True},
    "frost": {"sky": ((140, 190, 246), (238, 246, 255)), "pool": (214, 236, 255), "side": (120, 170, 220),
              "rings": [(200, 230, 250), (230, 244, 255), (190, 222, 246), (240, 248, 255), (210, 236, 252)],
              "blobs": [(255, 255, 255), (200, 230, 255)], "grip": 0.35, "bounce": 1.05, "sparkle": True},
    "coast": {"sky": ((96, 136, 226), (255, 198, 160)), "pool": (70, 150, 220), "side": (200, 160, 110),
              "rings": [(250, 226, 170), (240, 210, 150), (255, 200, 200), (250, 226, 170), (230, 200, 150)],
              "blobs": [(120, 200, 240), (240, 250, 255)], "grip": 1.2, "bounce": 1.05},
}


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sky(sky):
    from .pixel import Pix, cached

    def build():
        p = Pix(LOW_W, LOW_H)
        p.vgrad(0, 0, LOW_W, LOW_H, sky[0], sky[1], steps=9)
        return p.s
    return cached(("rolloff_sky", sky), build)


def project(x, y, z):
    """World (x right, y away from you, z up) to the screen. Returns
    (screen x, screen y, pixels per world unit at that depth)."""
    c, s = math.cos(PITCH), math.sin(PITCH)
    depth = y * c - z * s + DIST
    up = y * s + z * c
    k = FOCAL / max(1.0, depth)
    return CENTER[0] + x * k, CENTER[1] - up * k, k


class Marble:
    def __init__(self, name, color, was=None, player=False):
        self.name, self.color, self.was, self.player = name, color, was, player
        self.sides = 0               # 0: a circle
        self.x = self.y = self.vx = self.vy = 0.0
        self.z = 0.0                 # height of the bottom above the bowl's surface (falling: negative)
        self.vz = 0.0
        self.falling = False
        self.out = False
        self.phase = 0.0
        self.dash_cd = 0.0
        self.wins = 0
        self.say = None              # (line, seconds left)
        self.think_t = 0.0
        self.aim = (0.0, 0.0)
        self.float_to = (0.0, 0.0)   # where it paddles to in the pool, after a splash

    @property
    def alive(self):
        return not self.falling and not self.out

    def speak(self, line, secs=1.4):
        self.say = (line, secs)


class RollOffScreen(Screen):
    """Pick a game, then play rounds until you've had enough (Esc)."""

    def __init__(self, app, friends=None, back=None, theme="meadow"):
        super().__init__(app)
        self.theme = theme if theme in THEMES else "meadow"
        self.look = THEMES[self.theme]
        self.low_bg = pygame.Surface((LOW_W, LOW_H))
        self.low_bowl = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
        self.back = back or app.show_hub
        self.rng = random.Random(len(app.meta.data.get("friends", [])) + 7)
        self.marbles = [Marble("You", None, player=True)] + [Marble(n, c, w)
                                                             for n, c, w in (friends or rivals())]
        from .world import your_sides
        self.marbles[0].sides = your_sides(app.meta.data, getattr(app, "hub_rescued", None))
        for m in self.marbles[1:]:                     # everyone as round as they've got
            m.sides = REGULAR_SIDES.get((m.color, m.was), 12)
        self.you = self.marbles[0]
        self.mode = None             # None while choosing, then "bump" or "tilt"
        self.fx = Particles()
        self.pool_fx = Particles()   # splashes down in the pool (drawn under the bowl)
        self.keys = set()
        self.tilt = [0.0, 0.0]
        self.round_t = 0.0
        self.radius = ARENA_R
        self.over = None             # [winners, seconds since the round ended]
        self.rounds = 0
        self.pick_buttons()

    # -- choosing a game
    def pick_buttons(self):
        self.buttons = []
        self.add((150, 470, 300, 50), "Bump! (steer your marble)", lambda: self.start("bump"),
                 key=pygame.K_1, tag="mode:bump")
        self.add((510, 470, 300, 50), "Tilt! (tip the bowl)", lambda: self.start("tilt"),
                 key=pygame.K_2, tag="mode:tilt")
        self.add((380, 560, 200, 40), "Back to the Meadow", self.leave, key=pygame.K_ESCAPE, tag="back")

    def start(self, mode):
        self.mode = mode
        self.buttons = []
        self.add((820, 14, 120, 34), "Leave", self.leave, tag="back", small=True)
        self.new_round()

    def leave(self):
        sound.roll(0)
        self.back()

    def new_round(self):
        """Everyone bounces back onto the bowl, spread around the rim."""
        self.radius = ARENA_R
        self.round_t = 0.0
        self.over = None
        self.tilt = [0.0, 0.0]
        n = len(self.marbles)
        spin = self.rng.uniform(0, math.tau)
        for i, m in enumerate(self.marbles):
            a = spin + i * math.tau / n
            rad = ARENA_R * (0.55 if self.mode == "bump" else 0.35)
            m.x, m.y = math.cos(a) * rad, math.sin(a) * rad
            m.vx = m.vy = 0.0
            m.z, m.vz = 3.0 + i * 0.6, 0.0          # they drop in from above
            m.falling = m.out = False
            m.dash_cd = 0.5
        sound.play("group")

    # -- input
    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if self.mode is not None and ev.key == pygame.K_ESCAPE:
                self.leave()
                return True
            if self.mode is not None and ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                if (self.over and self.over[1] > 1.0) or (self.you.out and not self.over):
                    self.rounds += 1          # again! (or, once you've splashed, skip the wait)
                    self.new_round()
                elif self.mode == "bump":
                    self.dash(self.you)
                return True
            if ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
                          pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s):
                self.keys.add(ev.key)
                return True
        elif ev.type == pygame.KEYUP:
            self.keys.discard(ev.key)
            return True
        return super().handle(ev)

    def stick(self):
        k = self.keys
        x = (1 if k & {pygame.K_RIGHT, pygame.K_d} else 0) - (1 if k & {pygame.K_LEFT, pygame.K_a} else 0)
        y = (1 if k & {pygame.K_UP, pygame.K_w} else 0) - (1 if k & {pygame.K_DOWN, pygame.K_s} else 0)
        n = math.hypot(x, y)
        return (x / n, y / n) if n else (0.0, 0.0)

    def dash(self, m, direction=None):
        if m.dash_cd > 0 or not m.alive or m.z > 0.05:
            return
        dx, dy = direction or (self.stick() if m.player else m.aim)
        if (dx, dy) == (0.0, 0.0):
            sp = math.hypot(m.vx, m.vy)
            if sp < 0.1:
                return
            dx, dy = m.vx / sp, m.vy / sp
        m.vx += dx * DASH
        m.vy += dy * DASH
        m.dash_cd = DASH_COOLDOWN
        sound.play("step")

    # -- the bowl's surface
    def surface_z(self, x, y):
        return -(self.tilt[0] * x + self.tilt[1] * y)     # arrows lower that side: things roll that way

    # -- simulation
    def update(self, dt):
        super().update(dt)
        self.fx.update(dt)
        self.pool_fx.update(dt)
        if self.mode is None:
            return True
        dt = min(dt, 0.04)
        self.round_t += dt
        stick = self.stick()
        if self.mode == "tilt":
            target = (0.0, 0.0) if self.over else (stick[0] * MAX_TILT, stick[1] * MAX_TILT)
            for i in (0, 1):
                self.tilt[i] += (target[i] - self.tilt[i]) * min(1.0, dt * 3)
        elif self.round_t > SHRINK_AFTER and self.radius > MIN_R and not self.over:
            old = self.radius
            self.radius = max(MIN_R, self.radius - SHRINK_RATE * dt)
            if int(old * 4) != int(self.radius * 4):           # the rim crumbles a little
                a = self.rng.uniform(0, math.tau)
                sx, sy, _k = project(math.cos(a) * old, math.sin(a) * old, 0)
                self.fx.burst(sx, sy, lighten(COLOR_RGB[RAINBOW[0]], 0.3), n=4, speed=90,
                              shapes=("square",))
        for m in self.marbles:
            self._move(m, dt, stick)
        self._collide()
        alive = [m for m in self.marbles if m.alive]
        loudest = max((math.hypot(m.vx, m.vy) for m in alive), default=0.0)
        sound.roll(min(1.0, loudest / 8.0) * 0.7)
        if self.over is None:
            done = (len(alive) <= 1 if self.mode == "bump"
                    else (not self.you.alive or all(not m.alive for m in self.marbles if not m.player)))
            if done and all(m.z <= 0.05 for m in alive):
                # bump: the last one on wins. tilt: you win if you're the one left;
                # if you splash first, everyone still on the bowl wins together
                winners = alive
                if self.mode == "tilt" and self.you.alive:
                    winners = [self.you]
                self.over = [winners, 0.0]
                for w in winners:
                    w.wins += 1
                sound.play("fanfare" if self.you in winners else "group", 0.8)
                for m in self.marbles:
                    if not m.player:
                        m.speak(self.rng.choice(WIN_LINES if m in winners else CHEER_LINES), 2.5)
        else:
            self.over[1] += dt
        for m in self.marbles:
            if m.say is not None:
                m.say = (m.say[0], m.say[1] - dt) if m.say[1] > dt else None
        return True

    def _move(self, m, dt, stick):
        if m.out:
            tx, ty = m.float_to
            m.x += (tx - m.x) * min(1.0, dt * 1.5)
            m.y += (ty - m.y) * min(1.0, dt * 1.5)
            return
        m.dash_cd = max(0.0, m.dash_cd - dt)
        if m.falling:                                     # off the edge: down to the pool
            m.vz -= 22 * dt
            m.z += m.vz * dt
            m.x += m.vx * dt * 0.6
            m.y += m.vy * dt * 0.6
            if m.z < POOL_Z:
                m.out = True
                sx, sy, k = project(m.x, m.y, POOL_Z)
                for c in RAINBOW:
                    self.pool_fx.ring(sx, sy, COLOR_RGB[c], 4, k * 1.4, 0.7)
                self.pool_fx.burst(sx, sy, WHITE, n=8, speed=160, shapes=("circle",))
                sound.play("loose", 0.7)
                # then paddle out to where everyone can see you (left or right of the bowl)
                taken = {o.float_to for o in self.marbles if o.out and o is not m}
                near = 0 if m.x >= 0 else 1
                slots = FLOAT_SLOTS[near::2] + FLOAT_SLOTS[1 - near::2]
                a = next((a for a in slots if _slot(a) not in taken), slots[0])
                m.float_to = _slot(a)
            return
        if m.z > 0:                                        # dropping in at the start of a round
            m.vz -= 22 * dt
            m.z = max(0.0, m.z + m.vz * dt)
            if m.z == 0:
                m.vz = 0.0
                sound.play("step", 0.4)
            return
        ax = ay = 0.0
        grip = 2.2 * self.look["grip"]
        if self.mode == "bump":
            if m.player:
                ax, ay = stick[0] * 11.0, stick[1] * 11.0
            else:
                ax, ay = self._think(m, dt)
        else:
            # the bowl is tipped: everyone rolls downhill; you grip a bit better
            ax, ay = self.tilt[0] * 26.0, self.tilt[1] * 26.0
            grip = TILT_GRIP if m.player else 1.4
            if not m.player:                               # they try to scramble back uphill
                d = max(0.01, math.hypot(m.x, m.y))
                ax -= m.x / d * TILT_CLIMB * min(1.0, d / 2)
                ay -= m.y / d * TILT_CLIMB * min(1.0, d / 2)
                ax += math.sin(self.t * 1.3 + m.wins + len(m.name)) * 1.2
                ay += math.cos(self.t * 1.1 + len(m.name)) * 1.2
        m.vx += ax * dt
        m.vy += ay * dt
        decay = math.exp(-grip * dt)
        m.vx *= decay
        m.vy *= decay
        sp = math.hypot(m.vx, m.vy)
        if sp > 11.0:
            m.vx, m.vy = m.vx / sp * 11.0, m.vy / sp * 11.0
        m.x += m.vx * dt
        m.y += m.vy * dt
        m.phase += sp * dt / MARBLE_R
        if math.hypot(m.x, m.y) > self.radius:            # over the edge!
            m.falling = True
            m.vz = 2.0
            m.speak(self.rng.choice(FALL_LINES) if not m.player else "Wheee!", 1.6)
            sound.play("talk")

    def _think(self, m, dt):
        """Someone else's marble: chase the nearest one, don't roll off yourself,
        dash when it's lined up. They play to win, and they love to lose."""
        m.think_t -= dt
        others = [o for o in self.marbles if o is not m and o.alive]
        if not others:
            return 0.0, 0.0
        target = min(others, key=lambda o: math.hypot(o.x - m.x, o.y - m.y))
        dx, dy = target.x - m.x, target.y - m.y
        d = max(0.01, math.hypot(dx, dy))
        ax, ay = dx / d, dy / d
        edge = math.hypot(m.x, m.y) / self.radius
        if edge > 0.72:                                    # too close to the edge: back to the middle
            pull = (edge - 0.72) * 4
            ax -= m.x / max(0.01, math.hypot(m.x, m.y)) * pull
            ay -= m.y / max(0.01, math.hypot(m.x, m.y)) * pull
        if m.think_t <= 0:
            m.think_t = self.rng.uniform(0.3, 0.8)
            m.aim = (ax + self.rng.uniform(-0.3, 0.3), ay + self.rng.uniform(-0.3, 0.3))
            if d < 2.6 and self.rng.random() < 0.5:
                self.dash(m, (dx / d, dy / d))
        n = max(0.01, math.hypot(*m.aim))
        return m.aim[0] / n * 8.5, m.aim[1] / n * 8.5

    def _collide(self):
        live = [m for m in self.marbles if m.alive and m.z <= 0.05]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if 0 < d < MARBLE_R * 2:
                    nx, ny = dx / d, dy / d
                    push = (MARBLE_R * 2 - d) / 2
                    a.x -= nx * push
                    a.y -= ny * push
                    b.x += nx * push
                    b.y += ny * push
                    rel = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny
                    if rel > 0:                            # a bounce: swap speeds along the hit
                        imp = rel * self.look["bounce"]
                        a.vx -= imp * nx
                        a.vy -= imp * ny
                        b.vx += imp * nx
                        b.vy += imp * ny
                        if rel > 3:
                            sound.play("hit", min(1.0, rel / 10))
                            sx, sy, _k = project((a.x + b.x) / 2, (a.y + b.y) / 2, MARBLE_R)
                            self.fx.burst(sx, sy, WHITE, n=5, speed=150, shapes=("circle",))
                            speaker = b if not b.player else a
                            if not speaker.player and self.rng.random() < 0.35:
                                speaker.speak(self.rng.choice(BUMP_LINES))

    # -- drawing (the arena is painted at a third of the size and scaled up: pixel art)
    def draw(self, surf):
        t = self.t
        look = self.look
        L = self.low_bg
        L.blit(_sky(look["sky"]), (0, 0))
        self._pool(L, t)
        surf.blit(pygame.transform.scale(L, (LOW_W * PX, LOW_H * PX)), (0, 0))
        behind = [m for m in self.marbles if (m.falling or m.out) and m.y > 0]
        for m in sorted(behind, key=lambda m: -m.y):
            self._marble(surf, m)
        for m in self.marbles:                             # splashed out: bobbing in the pool
            if m.out:
                self._floater(surf, m, t)
        self.pool_fx.draw(surf)
        B = self.low_bowl
        B.fill((0, 0, 0, 0))
        self._bowl(B)
        surf.blit(pygame.transform.scale(B, (LOW_W * PX, LOW_H * PX)), (0, 0))
        front = [m for m in self.marbles if m not in behind and not m.out]
        for m in sorted(front, key=lambda m: -m.y):       # far ones first
            self._marble(surf, m)
        self.fx.draw(surf)
        for m in self.marbles:
            self._bubble(surf, m)
        if self.mode is None:
            self._menu(surf)
        else:
            self._hud(surf)
        self.draw_buttons(surf)

    def _pool(self, L, t):
        look = self.look
        pts = []
        for i in range(48):
            a = i * math.tau / 48
            sx, sy, _k = project(math.cos(a) * 16, math.sin(a) * 16, POOL_Z)
            pts.append((sx / PX, sy / PX))
        pygame.draw.polygon(L, look["pool"], pts)
        for i in range(30):                                # little glints on the water
            a = i * 2.4 + t * 0.2
            sx, sy, _k = project(math.cos(a) * (4 + i % 11), math.sin(a) * (4 + i % 11), POOL_Z)
            if (i + int(t * 3)) % 5 == 0:
                L.set_at((int(sx / PX), int(sy / PX)), (255, 255, 255))
        for j, c in enumerate(look["blobs"]):
            a0 = t * 0.3 + j * math.tau / len(look["blobs"])
            cx, cy, k = project(math.cos(a0) * 7, math.sin(a0) * 7, POOL_Z)
            blob = pygame.Rect(0, 0, int(k * 6 / PX), int(k * 2.2 / PX))
            blob.center = (int(cx / PX), int(cy / PX))
            pygame.draw.ellipse(L, c, blob)

    def _bowl(self, B):
        look = self.look
        R = self.radius
        n = 72

        def pt(x, y, dz=0.0):
            sx, sy, _k = project(x, y, self.surface_z(x, y) + dz)
            return sx / PX, sy / PX
        top = [pt(math.cos(i * math.tau / n) * R, math.sin(i * math.tau / n) * R) for i in range(n)]
        # the side of the bowl (the front half shows), in stripes
        side = look["side"]
        for i in range(n):
            a0, a1 = i * math.tau / n, (i + 1) * math.tau / n
            if math.sin((a0 + a1) / 2) > 0.15:
                continue
            quad = [pt(math.cos(a0) * R, math.sin(a0) * R), pt(math.cos(a1) * R, math.sin(a1) * R),
                    pt(math.cos(a1) * R, math.sin(a1) * R, -0.9), pt(math.cos(a0) * R, math.sin(a0) * R, -0.9)]
            light = -math.cos((a0 + a1) / 2)                # lit from the left
            c = _mix(side, (255, 255, 255), 0.25 * max(0.0, light)) if light > 0 else _mix(side, (40, 20, 60),
                                                                                          0.3 * -light)
            pygame.draw.polygon(B, c if i % 3 else _mix(c, (40, 20, 60), 0.12), quad)
        # the painted rings on top
        rings = look["rings"]
        for j in range(len(rings)):
            rr = R * (1 - j / (len(rings) + 0.4))
            ring = [pt(math.cos(i * math.tau / n) * rr, math.sin(i * math.tau / n) * rr) for i in range(n)]
            pygame.draw.polygon(B, rings[j], ring)
            far = [p for i, p in enumerate(ring) if math.sin(i * math.tau / n) > 0.3]
            if len(far) > 1:                                # a lit far edge on each ring
                pygame.draw.lines(B, _mix(rings[j], (255, 255, 255), 0.45), False, far, 1)
        if look.get("spots"):                               # a mushroom cap: white spots
            for k in range(9):
                a = k * 2.3
                d = R * (0.25 + 0.6 * ((k * 37) % 10) / 10)
                sx, sy = pt(math.cos(a) * d, math.sin(a) * d)
                pygame.draw.ellipse(B, (255, 255, 255), (int(sx) - 3, int(sy) - 2, 7, 4))
        if look.get("sparkle"):                             # frost glitter
            for k in range(14):
                a = k * 2.1 + self.t * 0.5
                sx, sy = pt(math.cos(a) * R * 0.8 * ((k % 5) + 1) / 5, math.sin(a) * R * 0.8 * ((k % 5) + 1) / 5)
                if (k + int(self.t * 4)) % 3 == 0:
                    B.set_at((int(sx), int(sy)), (255, 255, 255))
        pygame.draw.polygon(B, INK, top, 1)
        cx, cy = pt(0, 0)
        pygame.draw.circle(B, WHITE, (int(cx), int(cy)), 2)

    def _marble(self, surf, m):
        z = self.surface_z(m.x, m.y) + (m.z if not m.falling else m.z) + MARBLE_R
        sx, sy, k = project(m.x, m.y, z)
        rr = max(3, MARBLE_R * k)
        if m.alive:                                        # a shadow on the bowl
            shx, shy, _k = project(m.x, m.y, self.surface_z(m.x, m.y))
            sh = pygame.Surface((int(rr * 2.4), int(rr * 1.0)), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (*INK, 70), sh.get_rect())
            surf.blit(sh, (shx - rr * 1.2, shy - rr * 0.5))
        mood = "happy" if (m.falling or (self.over and m in self.over[0])) else (
            "wow" if math.hypot(m.vx, m.vy) > 6 else "plain")
        if m.player:
            draw_player(surf, shape_of(m.sides), sx, sy, rr, self.t, mood=mood, rot=m.phase, shadow=False)
        else:
            draw_critter(surf, shape_of(m.sides), sx, sy, rr, COLOR_RGB[m.color], mood=mood, rot=m.phase,
                         shadow=False, look=(math.cos(m.phase), 0.3))
        # 3D: a darker lower side and a shine
        shade = _shade(int(rr))
        surf.blit(shade, (sx - shade.get_width() / 2, sy - shade.get_height() / 2))
        pygame.draw.circle(surf, WHITE, (int(sx - rr * 0.38), int(sy - rr * 0.42)), max(2, int(rr * 0.16)))

    def _floater(self, surf, m, t):
        """A marble that fell: floating in the colour pool, waving, having a lovely time."""
        bob = math.sin(t * 3 + len(m.name)) * 0.15
        sx, sy, k = project(m.x, m.y, POOL_Z + MARBLE_R * 0.6 + bob)
        rr = max(3, MARBLE_R * k)
        ring = pygame.Rect(0, 0, int(rr * 3), int(rr * 1.1))
        ring.center = (int(sx), int(sy + rr * 0.7))
        tint = WHITE if m.player else mix(COLOR_RGB[m.color], WHITE, 0.6)
        pygame.draw.ellipse(surf, tint, ring, 2)
        if m.player:
            draw_player(surf, shape_of(m.sides), sx, sy, rr, t, mood="happy", shadow=False)
        else:
            draw_critter(surf, shape_of(m.sides), sx, sy, rr, COLOR_RGB[m.color], mood="happy",
                         shadow=False, width=2)

    def _bubble(self, surf, m):
        if m.say is None or m.out:
            return
        z = self.surface_z(m.x, m.y) + m.z + MARBLE_R * 2.6
        sx, sy, _k = project(m.x, m.y, z)
        f = font(20)
        w = f.size(m.say[0])[0] + 18
        box = pygame.Rect(0, 0, w, 28)
        box.midbottom = (int(sx), int(sy))
        box.clamp_ip(pygame.Rect(4, 4, 952, 632))
        pygame.draw.rect(surf, WHITE, box, border_radius=10)
        pygame.draw.rect(surf, INK, box, 2, border_radius=10)
        draw_text(surf, f, m.say[0], box.center, INK, center=True)

    def _hud(self, surf):
        heading(surf, "Roll-Off: %s!" % ("Bump" if self.mode == "bump" else "Tilt"), (24, 12), 36)
        x = 300
        for m in self.marbles:                             # who has won how many rounds
            if m.player:
                draw_player(surf, shape_of(m.sides), x, 34, 11, self.t, shadow=False)
            else:
                draw_critter(surf, shape_of(m.sides), x, 34, 11, COLOR_RGB[m.color], shadow=False, width=2)
            draw_text(surf, font(22), "x%d" % m.wins, (x + 16, 26), WHITE, shadow=INK)
            x += 70
        hint = ("arrows: roll   Space: dash   Esc: back to the Meadow" if self.mode == "bump"
                else "arrows: tip the bowl (you grip better)   Esc: back to the Meadow")
        if self.you.out and not self.over:
            hint = "Splash! Space: next round now   (or watch them finish)"
        _pill(surf, hint, (480, 618))
        if self.mode == "bump" and self.round_t > SHRINK_AFTER - 3 and not self.over:
            _pill(surf, "the bowl is shrinking!", (480, 582), COLOR_RGB["M"])
        if self.over:
            winners, age = self.over
            k = ease_out(min(1.0, age / 0.4))
            card = pygame.Rect(0, 0, 440, 104)
            card.center = (480, int(112 - 40 * (1 - k)))
            draw_card(surf, card, PAPER, 16)
            if not winners:
                title = "Everybody splashed!"
            elif winners == [self.you]:
                title = "You win the round!"
            elif len(winners) == 1:
                title = "%s wins the round!" % winners[0].name
            else:
                title = "%s stayed on!" % " & ".join(w.name for w in winners)
            draw_text(surf, font(36 if len(title) < 24 else 28), title, (card.centerx, card.y + 30), INK,
                      center=True)
            if len(winners) == 1 and not winners[0].player and winners[0].was:
                draw_text(surf, font(18), "(it used to be a %s)" % winners[0].was,
                          (card.centerx, card.y + 56), (120, 106, 150), center=True)
            elif self.you.out or self.you.falling:
                draw_text(surf, font(18), "(you splashed! the best part)", (card.centerx, card.y + 56),
                          (120, 106, 150), center=True)
            if age > 1.0:
                draw_text(surf, font(22), "Space: again!   Esc: back to the Meadow",
                          (card.centerx, card.bottom - 20), INK, center=True)

    def _menu(self, surf):
        heading(surf, "Roll-Off!", (480, 40), 60, center=True)
        draw_text(surf, font(24), "Last one on the bowl wins. Falling off is the best part: splash!",
                  (480, 96), WHITE, center=True, shadow=INK)
        for i, (title, words) in enumerate((
                ("Bump", "Steer your own marble and dash into the others. The bowl shrinks as you play."),
                ("Tilt", "Tip the whole bowl. Everyone rolls downhill, but you grip better. "
                         "Roll them all off and stay on."))):
            card = draw_card(surf, (150 + i * 360, 330, 300, 126))
            draw_text(surf, font(28), title, (card.centerx, card.y + 22), INK, center=True)
            draw_wrapped(surf, font(20), words, (card.x + 14, card.y + 44), card.w - 28, INK, 1,
                         center=True)


def _slot(a):
    return (round(math.cos(a) * FLOAT_R, 3), round(math.sin(a) * FLOAT_R, 3))


def _pill(surf, text, center, color=INK):
    f = font(20)
    box = pygame.Rect(0, 0, f.size(text)[0] + 28, 28)
    box.center = center
    pygame.draw.rect(surf, color, box, border_radius=14)
    draw_text(surf, f, text, box.center, WHITE, center=True)


_SHADES = {}


def _shade(r):
    """A soft darker crescent on a sphere's lower-right side (cached by size)."""
    s = _SHADES.get(r)
    if s is None:
        size = r * 2 + 2
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(8):
            k = i / 8
            pygame.draw.circle(s, (*INK, 10), (int(r + 1 + r * 0.25 * k), int(r + 1 + r * 0.28 * k)),
                               max(1, int(r * (1 - 0.5 * k))))
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (r + 1, r + 1), r)
        s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        _SHADES[r] = s
    return s
