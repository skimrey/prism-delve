"""The Side Show: pinball in the Meadow's zones, run by a friend you got out
of a tower.

You are the ball. Each stage has exactly two colours: the LEFT flipper is
one, the RIGHT flipper is the other, and whichever flipper you touch paints
you its colour. Shapes pop up around the table in those two colours only.
Hit a shape while you're its own colour and your light feeds it a side;
grow it all the way round and it rolls off the table, free. Free them all
and the stage clears (light show, multiball), and the next stage brings two
new colours, more shapes, and shapes that drift about.

Also on the table: four rollover lanes at the top (light all four for a
bigger multiplier; the flippers shuffle which are lit), three mushroom
bumpers (round: they don't change you), two slingshots, and a knothole on
the left: roll into it and it bursts your light over every shape of your
colour at once. Knock down all three drop targets on the right and every
shape on the table grows a side. A spinner on the left orbit whirs for points. Three balls, a ball save at the start of each, nothing at
stake. The table is painted as pixel art (2x) with glow on top.
"""

import math
import random

import pygame

from . import sound
from .art import Particles
from .consts import COLOR_NAMES, COLOR_RGB, RAINBOW
from .art import draw_critter, draw_player
from .pixel import OUTLINE, Pix, cached, mix, ramp, shade
from .world import shape_of
from .screens import Screen
from .widgets import INK, PAPER, WHITE, draw_card, draw_colour_mark, draw_text, draw_wrapped, font

TX, TY, TW, TH = 250, 16, 460, 608          # the table, on screen
PK = 2                                       # table pixels are 2x2 screen pixels
FW = 420                                     # the field's width (the plunger lane is to its right)
BALL = 12
GRAVITY = 600.0
MAX_SPEED = 1150.0
SUBSTEPS = 6
FLIP_LEN, FLIP_R = 88, 9
FLIP_REST, FLIP_UP = 0.52, -0.5              # flipper angles below horizontal (radians)
FLIP_SPEED_UP, FLIP_SPEED_DOWN = 20.0, 11.0
LEFT_PIVOT, RIGHT_PIVOT = (112, TH - 64), (FW - 112, TH - 64)
BUMPERS = ((140, 190, 22), (280, 190, 22), (210, 262, 22))
LANES = (150, 190, 230, 270)                 # rollover lanes at the top: their centres
LANE_Y = (70, 100)
SAUCER = (56, 300, 14)                       # the knothole
DROPS = ((398, 244, "R"), (398, 274, "G"), (398, 304, "B"))   # drop targets on the right: (x, y, colour)
SPINNER = (12, 64, 150)                      # a spinner across the left orbit: (x0, x1, y)
SLOTS = ((96, 372), (324, 372), (210, 150), (78, 222), (342, 222), (210, 346), (150, 300), (270, 300))
BALLS = 3
SAVE_TIME = 8.0
SHAPE_NAMES = {3: "triangle", 4: "square", 5: "pentagon", 6: "hexagon"}
CHEERS = ("Wheee!", "Free!", "I'm ROUND!", "Bye-bye corners!", "Rolling!")

# The stages: (left colour, right colour, shapes to free, fewest sides, most
# sides, round at, how fast they drift). Past the last, colours keep coming.
STAGES = (("R", "B", 3, 4, 5, 7, 0.0), ("Y", "G", 4, 3, 5, 7, 0.0), ("C", "M", 4, 3, 4, 7, 18.0),
          ("R", "G", 5, 3, 4, 7, 26.0), ("B", "Y", 5, 3, 4, 8, 34.0), ("M", "C", 6, 3, 3, 8, 42.0))
THEMES = {                                   # the table's felt and rails, per zone
    "wilds": ((34, 80, 70), (20, 46, 60), (120, 200, 120)),
    "dunes": ((120, 70, 50), (70, 40, 40), (250, 200, 120)),
    "caves": ((40, 26, 80), (18, 14, 44), (190, 150, 255)),
    "heights": ((60, 110, 180), (30, 60, 120), (230, 240, 255)),
}


def stage_spec(n):
    """The stage numbered n (1..): its colours, how many shapes, and so on."""
    if n <= len(STAGES):
        return STAGES[n - 1]
    rng = random.Random(n)
    a, b = rng.sample(("R", "G", "B", "Y", "C", "M"), 2)
    return (a, b, min(7, 5 + n // 3), 3, 3, 8, min(70.0, 30.0 + n * 4))


def table_walls():
    """Line segments the ball bounces off: (ax, ay, bx, by, kick)."""
    w = []
    cx, cy, r = TW / 2, TW / 2, TW / 2
    n = 18
    arc = [(cx + math.cos(math.pi + math.pi * k / n) * r, cy + math.sin(math.pi + math.pi * k / n) * r)
           for k in range(n + 1)]
    for a, b in zip(arc, arc[1:]):
        w.append((a[0], a[1], b[0], b[1], 0))
    w.append((0, cy, 0, TH - 210, 0))                       # left wall
    w.append((TW, cy, TW, TH, 0))                           # right wall (outside the lane)
    w.append((FW, 200, FW, TH, 0))                          # the lane's inner wall
    w.append((0, TH - 210, LEFT_PIVOT[0] - 6, LEFT_PIVOT[1] - 4, 0))        # funnels to the flippers
    w.append((FW, TH - 210, RIGHT_PIVOT[0] + 6, RIGHT_PIVOT[1] - 4, 0))
    w.append((44, TH - 250, 92, TH - 160, 340))             # slingshots: they kick
    w.append((FW - 44, TH - 250, FW - 92, TH - 160, 340))
    w.append((FW + 6, 60, FW + 34, 20, 0))                  # bends the launch into the arc
    for x in LANES[:-1]:                                    # posts between the top lanes
        w.append((x + 20, LANE_Y[0], x + 20, LANE_Y[1], 0))
    return w


def _closest_on_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ln = dx * dx + dy * dy
    f = 0.0 if ln == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ln))
    return ax + dx * f, ay + dy * f


class Flipper:
    def __init__(self, pivot, side):
        self.px, self.py = pivot
        self.side = side                      # -1 left (points right), +1 right (points left)
        self.angle = FLIP_REST
        self.omega = 0.0
        self.held = False
        self.shifted = False                  # (kept: set when a flip has hit the ball)
        self.color = "R"

    def tip(self):
        d = -self.side
        return (self.px + d * math.cos(self.angle) * FLIP_LEN, self.py + math.sin(self.angle) * FLIP_LEN)

    def update(self, dt):
        if not self.held:
            self.shifted = False
        target = FLIP_UP if self.held else FLIP_REST
        speed = FLIP_SPEED_UP if self.held else FLIP_SPEED_DOWN
        old = self.angle
        if self.angle > target:
            self.angle = max(target, self.angle - speed * dt)
        else:
            self.angle = min(target, self.angle + speed * dt)
        self.omega = (self.angle - old) / dt if dt else 0.0      # negative while swinging up


class PBall:
    """You, as a ball. None colour: white, straight off the plunger."""

    def __init__(self, x, y, vx=0.0, vy=0.0, in_lane=True):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.in_lane = in_lane
        self.color = None
        self.trail = []
        self.held = 0.0                      # seconds left in the knothole
        self.cool = 0.0                      # (just spat out of it: it can't swallow you yet)
        self.gone = False


class Target:
    """A shape on the table, waiting for light its own colour."""

    def __init__(self, slot, sides, color, drift=0.0, seed=0):
        self.slot = slot
        self.hx, self.y = SLOTS[slot]
        self.x = self.hx
        self.sides = sides
        self.color = color
        self.drift = drift
        self.phase = seed * 1.7
        self.age = 0.0
        self.wiggle = 0.0
        self.happy = 0.0
        self.free = None                      # once round: (vx, seconds) as it rolls away

    @property
    def r(self):
        return 20


class PinballScreen(Screen):
    def __init__(self, app, back=None, seed=None, theme="wilds"):
        super().__init__(app)
        self.theme = theme if theme in THEMES else "wilds"
        self.back = back or app.show_hub
        self.rng = random.Random(seed if seed is not None else 11)
        self.fx = Particles()
        self.left = Flipper(LEFT_PIVOT, -1)
        self.right = Flipper(RIGHT_PIVOT, 1)
        self.walls = self._walls()
        self.best = app.meta.data.get("pinball_best", 0)
        from .world import World, friend_sides, plan_of, your_sides
        pretend = getattr(app, "hub_rescued", None)
        self.you_sides = your_sides(app.meta.data, pretend)
        plan = plan_of(app.meta.data)                      # who runs this table: whoever opened its zone
        rescued = app.meta.data.get("friends", []) if pretend is None else pretend
        zone = next((z for z in World(plan, rescued).zones if z.kind == theme and z.index), None)
        self.host_tower = plan[zone.index - 1] if zone else "leaning"
        self.host_sides = friend_sides(self.host_tower, app.meta.data, rescued)
        self.add((24, 592, 200, 34), "Back", self.leave, tag="back", small=True)
        self.restart(first=True)

    # -- the table
    def _walls(self):
        return table_walls()

    def restart(self, first=False):
        if not first:
            self._save_best()
        self.score = 0
        self.mult = 1
        self.freed = 0
        self.sides_given = 0
        self.balls_left = BALLS
        self.over = None
        self.stage = 0
        self.lanes = [False] * 4
        self.words = []
        self.flash = 0.0
        self.banner = None                    # (title, line, seconds shown)
        self.bumper_glow = [0.0] * len(BUMPERS)
        self.sling_glow = [0.0, 0.0]
        self.shake = 0.0
        self.drops = [True, True, True]          # standing
        self.drops_t = 0.0                       # seconds until they pop back up
        self.spin = 0.0                          # the spinner's speed (turns a second)
        self.spin_a = 0.0
        self.balls = []
        self.next_stage()
        self._serve()

    def next_stage(self):
        self.stage += 1
        a, b, n, lo, hi, grow, drift = stage_spec(self.stage)
        self.left.color, self.right.color = a, b
        self.grow_to = grow
        self.targets = []
        self.to_free = n
        self.spawned = 0
        self._freed_stage = 0
        self.drift = drift
        self.spawn_t = 0.0
        for _ in range(min(3, n)):
            self._spawn()
        self.banner = ["Stage %d" % self.stage, "%s and %s" % (COLOR_NAMES[a], COLOR_NAMES[b]), 0.0]
        for ball in getattr(self, "balls", ()):
            ball.color = None                              # new colours: everyone starts white again

    def _serve(self):
        self.balls.append(PBall(FW + (TW - FW) / 2, TH - 40))
        self.save_t = SAVE_TIME
        self.charge = 0.0
        self.charging = False

    def _spawn(self):
        if self.spawned >= self.to_free:
            return
        free = [i for i in range(len(SLOTS)) if all(t.slot != i for t in self.targets)]
        if not free:
            return
        a, b, n, lo, hi, grow, drift = stage_spec(self.stage)
        slot = self.rng.choice(free)
        color = (a, b)[self.spawned % 2]
        self.targets.append(Target(slot, self.rng.randint(lo, hi), color, drift, seed=self.spawned))
        self.spawned += 1
        sound.play("step", 0.5)

    @property
    def color(self):
        """Your colour (the first ball's): None while white."""
        return self.balls[0].color if self.balls else None

    # (the old name, kept for the tests)
    @property
    def in_lane(self):
        return bool(self.balls) and self.balls[0].in_lane

    # -- input
    def leave(self):
        self._save_best()
        sound.roll(0)
        self.back()

    def _save_best(self):
        if self.score > self.app.meta.data.get("pinball_best", 0):
            self.app.meta.data["pinball_best"] = self.score
            self.app.meta.save()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.leave()
                return True
            if ev.key in (pygame.K_LEFT, pygame.K_z, pygame.K_a, pygame.K_LSHIFT):
                self.left.held = True
                self.lanes = self.lanes[1:] + self.lanes[:1]          # lane change
                sound.play("tick", 0.4)
                return True
            if ev.key in (pygame.K_RIGHT, pygame.K_SLASH, pygame.K_d, pygame.K_RSHIFT):
                self.right.held = True
                self.lanes = self.lanes[-1:] + self.lanes[:-1]
                sound.play("tick", 0.4)
                return True
            if ev.key in (pygame.K_SPACE, pygame.K_DOWN, pygame.K_RETURN):
                if self.over is not None and self.over > 1.0:
                    self.restart()
                elif any(b.in_lane and b.vy == 0 for b in self.balls):
                    self.charging = True
                return True
        elif ev.type == pygame.KEYUP:
            if ev.key in (pygame.K_LEFT, pygame.K_z, pygame.K_a, pygame.K_LSHIFT):
                self.left.held = False
                return True
            if ev.key in (pygame.K_RIGHT, pygame.K_SLASH, pygame.K_d, pygame.K_RSHIFT):
                self.right.held = False
                return True
            if ev.key in (pygame.K_SPACE, pygame.K_DOWN, pygame.K_RETURN) and self.charging:
                self.launch()
                return True
        return super().handle(ev)

    def launch(self):
        self.charging = False
        for b in self.balls:
            if b.in_lane and b.vy == 0:
                b.vy = -1250 * (0.45 + 0.55 * self.charge)
                sound.play("step")
        self.charge = 0.0

    # -- simulation
    def update(self, dt):
        super().update(dt)
        self.fx.update(dt)
        dt = min(dt, 1 / 30)
        for w in self.words:
            w[3] += dt
        self.words = [w for w in self.words if w[3] < 1.3]
        self.flash = max(0.0, self.flash - dt)
        self.shake = max(0.0, self.shake - dt)
        self.bumper_glow = [max(0.0, g - dt) for g in self.bumper_glow]
        self.sling_glow = [max(0.0, g - dt) for g in self.sling_glow]
        if self.banner is not None:
            self.banner[2] += dt
            if self.banner[2] > 2.4:
                self.banner = None
        if self.over is not None:
            self.over += dt
            return True
        if self.charging:
            self.charge = min(1.0, self.charge + dt * 1.2)
        if self.spin > 0:                                   # the spinner whirs down
            before = int(self.spin_a)
            self.spin_a += self.spin * dt
            if int(self.spin_a) > before:
                self._score(10, None)
                sound.play("tick", 0.3)
            self.spin = max(0.0, self.spin - dt * 6)
        if not any(self.drops):
            self.drops_t -= dt
            if self.drops_t <= 0:
                self.drops = [True, True, True]
        if self.save_t > 0 and not any(b.in_lane for b in self.balls):
            self.save_t -= dt
        for t in list(self.targets):
            t.age += dt
            t.wiggle = max(0.0, t.wiggle - dt)
            t.happy = max(0.0, t.happy - dt)
            if t.free is not None:                      # rolling off the table, happily
                vx, secs = t.free
                t.x += vx * dt
                t.y += 60 * dt
                t.free = (vx, secs + dt)
                if secs > 1.4:
                    self.targets.remove(t)
            elif t.drift:
                t.x = t.hx + math.sin(self.t * 0.9 + t.phase) * t.drift
        self.spawn_t += dt
        live = [t for t in self.targets if t.free is None]
        if len(live) < 4 and self.spawn_t > 2.0:
            self.spawn_t = 0.0
            self._spawn()
        if self.freed_this_stage() >= self.to_free and not any(t.free for t in self.targets):
            self._stage_clear()
        sub = dt / SUBSTEPS
        for _ in range(SUBSTEPS):
            self.left.update(sub)
            self.right.update(sub)
            for b in list(self.balls):
                self._step(b, sub)
            self._collide_balls()
            if self.over is not None:
                break
        for b in self.balls:
            b.trail.append((b.x, b.y, b.color))
            b.trail = b.trail[-8:]
        speed = max((math.hypot(b.vx, b.vy) for b in self.balls), default=0.0)
        sound.roll(min(1.0, speed / MAX_SPEED) * 0.6)
        return True

    def freed_this_stage(self):
        return self._freed_stage

    def _stage_clear(self):
        bonus = 5000 * self.stage
        self.score += bonus * self.mult
        self.words.append(["STAGE CLEAR! +%d" % (bonus * self.mult), FW / 2, 300, 0.0, WHITE])
        self.flash = 1.0
        self.shake = 0.4
        sound.play("fanfare")
        for c in RAINBOW:
            self.fx.burst(TX + TW / 2, TY + 300, COLOR_RGB[c], n=10, speed=380, shapes=("circle",))
        self.next_stage()
        if len(self.balls) < 3:                          # multiball: two more, straight down the lane
            for k in range(2):
                nb = PBall(FW / 2 + (k * 2 - 1) * 60, 120, (k * 2 - 1) * 120, 200, in_lane=False)
                nb.color = (self.left.color, self.right.color)[k]
                self.balls.append(nb)
            self.save_t = 10.0
            self.words.append(["MULTIBALL!", FW / 2, 250, 0.0, COLOR_RGB["Y"]])

    def _step(self, b, dt):
        if b.gone:
            return
        if b.held > 0:                                   # in the knothole, glowing
            b.held -= dt
            if b.held <= 0:                               # spat out, down and to the right
                b.x, b.y = SAUCER[0] + SAUCER[2] + BALL + 4, SAUCER[1] + 6
                b.vx, b.vy = 300, 320
                b.cool = 1.2
            return
        b.cool = max(0.0, b.cool - dt)
        if b.in_lane and b.vy == 0.0:
            return                                      # waiting on the plunger
        b.vy += GRAVITY * dt
        b.x += b.vx * dt
        b.y += b.vy * dt
        if b.in_lane and b.y < 200 and b.x < TW - 2:
            b.in_lane = False
        if b.in_lane and b.y > TH - 40:                 # fell back down the lane: ready again
            b.y, b.vx, b.vy = TH - 40, 0.0, 0.0
            return
        for i, (ax, ay, bx, by, kick) in enumerate(self.walls):
            hit = self._segment(b, ax, ay, bx, by, 0.0, 0.0, kick)
            if hit and kick:
                self.sling_glow[0 if ax < FW / 2 else 1] = 0.3
                self._score(5, None)
        for fl in (self.left, self.right):
            self._flipper(b, fl)
        for i, (x, y, r) in enumerate(BUMPERS):
            if self._bumper(b, x, y, r):
                self.bumper_glow[i] = 0.35
                self._score(10, None)
        for t in self.targets:
            if t.free is None:
                self._target(b, t)
        self._lanes(b)
        self._drop_targets(b)
        x0, x1, sy0 = SPINNER
        if x0 < b.x < x1 and abs(b.y - sy0) < abs(b.vy) * dt + 1 and abs(b.vy) > 200:
            self.spin = min(14.0, self.spin + abs(b.vy) / 90)      # through the spinner: whirr
        sx, sy, sr = SAUCER
        if b.cool <= 0 and math.hypot(b.x - sx, b.y - sy) < sr and math.hypot(b.vx, b.vy) < 900:
            self._knothole(b)
        sp = math.hypot(b.vx, b.vy)
        if sp > MAX_SPEED:
            b.vx, b.vy = b.vx / sp * MAX_SPEED, b.vy / sp * MAX_SPEED
        if b.y > TH + 30:                                # down the middle: that ball's done
            self._drain(b)

    def _collide_balls(self):
        live = [b for b in self.balls if not b.in_lane and b.held <= 0]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if 0 < d < BALL * 2:
                    nx, ny = dx / d, dy / d
                    push = (BALL * 2 - d) / 2
                    a.x, a.y = a.x - nx * push, a.y - ny * push
                    b.x, b.y = b.x + nx * push, b.y + ny * push
                    rel = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny
                    if rel > 0:
                        a.vx, a.vy = a.vx - rel * nx, a.vy - rel * ny
                        b.vx, b.vy = b.vx + rel * nx, b.vy + rel * ny

    def _segment(self, b, ax, ay, bx, by, svx, svy, kick, e=0.45):
        """Bounce ball b off a segment whose surface moves at (svx, svy).
        Returns the approach speed (0 if no hit)."""
        cx, cy = _closest_on_segment(b.x, b.y, ax, ay, bx, by)
        dx, dy = b.x - cx, b.y - cy
        d = math.hypot(dx, dy)
        reach = BALL + (FLIP_R if (svx or svy or kick == -1) else 3)
        if d >= reach or d == 0:
            return 0.0
        nx, ny = dx / d, dy / d
        b.x, b.y = cx + nx * reach, cy + ny * reach
        rvx, rvy = b.vx - svx, b.vy - svy
        vn = rvx * nx + rvy * ny
        if vn < 0:
            b.vx -= (1 + e) * vn * nx
            b.vy -= (1 + e) * vn * ny
            if kick > 0 and -vn > 60:                   # a slingshot
                b.vx += nx * kick
                b.vy += ny * kick
                sound.play("hit", 0.4)
                self.fx.burst(TX + cx, TY + cy, WHITE, n=4, speed=120, shapes=("circle",))
            return -vn
        return 0.0

    def _flipper(self, b, fl):
        ax, ay = fl.px, fl.py
        bx, by = fl.tip()
        cx, cy = _closest_on_segment(b.x, b.y, ax, ay, bx, by)
        rx, ry = cx - ax, cy - ay
        svx, svy = fl.omega * fl.side * ry, -fl.omega * fl.side * rx
        reach = BALL + FLIP_R
        if math.hypot(b.x - cx, b.y - cy) < reach + 1:
            if b.color != fl.color:                     # the flipper you touch paints you
                b.color = fl.color
                sound.play("cast:" + fl.color, 0.6)
                self.fx.ring(TX + cx, TY + cy, COLOR_RGB[fl.color], 6, 40, 0.4)
        hit = self._segment(b, ax, ay, bx, by, svx, svy, -1, e=0.3)
        if hit and fl.omega < -1.0:
            fl.shifted = True

    def _bumper(self, b, x, y, r):
        dx, dy = b.x - x, b.y - y
        d = math.hypot(dx, dy)
        if d >= r + BALL or d == 0:
            return False
        nx, ny = dx / d, dy / d
        b.x, b.y = x + nx * (r + BALL), y + ny * (r + BALL)
        vn = b.vx * nx + b.vy * ny
        b.vx -= 2 * vn * nx
        b.vy -= 2 * vn * ny
        boost = max(0.0, 520 - (b.vx * nx + b.vy * ny))
        b.vx += nx * boost
        b.vy += ny * boost
        sound.play("hit", 0.5)
        self.fx.burst(TX + x + nx * r, TY + y + ny * r, (255, 200, 240), n=5, speed=150, shapes=("circle",))
        return True

    def _target(self, b, t):
        dx, dy = b.x - t.x, b.y - t.y
        d = math.hypot(dx, dy)
        if d >= t.r + BALL or d == 0:
            return
        nx, ny = dx / d, dy / d
        b.x, b.y = t.x + nx * (t.r + BALL), t.y + ny * (t.r + BALL)
        vn = b.vx * nx + b.vy * ny
        if vn < 0:
            b.vx -= 1.7 * vn * nx
            b.vy -= 1.7 * vn * ny
            b.vx += nx * 120
            b.vy += ny * 120
        if t.age < 0.3 or t.happy > 0.25:
            return                                      # (one hit at a time)
        self.hit(t, b.color)

    def hit(self, t, color=None):
        """Your light on a shape: its own colour feeds it a side."""
        color = color if color is not None else self.color
        if color != t.color:
            t.wiggle = 0.4
            sound.play("tick", 0.6)
            return False
        t.sides += 1
        t.happy = 0.6
        self.sides_given += 1
        self._score(100, (t.x, t.y - 26))
        sound.play("ascend", 0.4)
        self.fx.ring(TX + t.x, TY + t.y, COLOR_RGB[t.color], 8, 46, 0.5)
        if t.sides >= self.grow_to:                     # round: off it rolls
            self.freed += 1
            self._freed_stage += 1
            t.free = (-180 if t.x < FW / 2 else 180, 0.0)
            self._score(1000, None)
            sound.play("fanfare", 0.5)
            self.words.append([self.rng.choice(CHEERS), t.x, t.y - 50, 0.0, WHITE])
            for c in RAINBOW:
                self.fx.burst(TX + t.x, TY + t.y, COLOR_RGB[c], n=3, speed=220, shapes=("circle",))
        return True

    def _score(self, pts, at):
        self.score += pts * self.mult
        if at is not None:
            self.words.append(["+%d" % (pts * self.mult), at[0], at[1], 0.0, COLOR_RGB["Y"]])

    def _lanes(self, b):
        if not (LANE_Y[0] < b.y < LANE_Y[1]) or b.vy <= 0:
            return
        for i, x in enumerate(LANES):
            if abs(b.x - x) < 14 and not self.lanes[i]:
                self.lanes[i] = True
                self._score(50, (x, LANE_Y[1] + 10))
                sound.play("ui", 0.6)
                if all(self.lanes):                     # all four lit: the multiplier goes up
                    self.lanes = [False] * 4
                    self.mult = min(5, self.mult + 1)
                    self.words.append(["x%d!" % self.mult, FW / 2, 120, 0.0, COLOR_RGB["M"]])
                    self.flash = 0.5
                    sound.play("group")

    def _drop_targets(self, b):
        """Three little targets on the right. Knock all three down and every
        shape on the table grows a side."""
        for i, (x, y, c) in enumerate(DROPS):
            if not self.drops[i]:
                continue
            hit = self._segment(b, x, y - 10, x, y + 10, 0.0, 0.0, 0, e=0.6)
            if hit:
                self.drops[i] = False
                self._score(200, (x - 30, y))
                sound.play("cast:" + c, 0.6)
                self.fx.burst(TX + x, TY + y, COLOR_RGB[c], n=6, speed=160, shapes=("square",))
                if not any(self.drops):
                    self.drops_t = 3.0
                    self.words.append(["EVERYONE +1 SIDE!", FW / 2, 200, 0.0, COLOR_RGB["G"]])
                    self.flash = 0.5
                    sound.play("group")
                    for t in list(self.targets):
                        if t.free is None:
                            t.happy, t.age = 0.0, 1.0
                            self.hit(t, t.color)

    def _knothole(self, b):
        """The knothole: it swallows you, then bursts your colour over every
        shape of that colour on the table."""
        b.held = 1.0
        b.vx = b.vy = 0.0
        b.x, b.y = SAUCER[0], SAUCER[1]
        sound.play("door", 0.6)
        self._score(250, (SAUCER[0] + 30, SAUCER[1] - 20))
        if b.color is not None:
            hits = [t for t in self.targets if t.free is None and t.color == b.color]
            for t in hits:
                t.happy = 0.0
                t.age = 1.0
                self.hit(t, b.color)
            if hits:
                self.words.append(["PRISM BURST!", SAUCER[0] + 60, SAUCER[1] - 44, 0.0, COLOR_RGB[b.color]])
                self.flash = 0.35

    def _drain(self, b):
        self.balls.remove(b)
        if self.balls:
            return                                       # multiball: the others play on
        if self.save_t > 0:
            self.words.append(["SAVED!", FW / 2, TH - 140, 0.0, COLOR_RGB["C"]])
            sound.play("ascend", 0.5)
            self._serve()
            self.save_t = 0.0
            return
        self.balls_left -= 1
        sound.play("loose", 0.7)
        if self.balls_left <= 0:
            self.over = 0.0
            self._save_best()
            sound.roll(0)
            return
        self._serve()

    # -- drawing
    def draw(self, surf):
        t = self.t
        top, bottom, rail = THEMES[self.theme]
        surf.blit(_backdrop(self.theme), (0, 0))
        jolt = (int(math.sin(t * 70) * 6 * self.shake), int(math.cos(t * 53) * 6 * self.shake))
        table = pygame.Surface((TW // PK, TH // PK), pygame.SRCALPHA)
        table.blit(_table_canvas(self.theme), (0, 0))
        self._paint(table, t)
        big = pygame.transform.scale(table, (TW, TH))
        surf.blit(big, (TX + jolt[0], TY + jolt[1]))
        self._glow(surf, t, jolt)
        self._actors(surf, t, jolt)
        for i, x in enumerate(LANES):                              # R O L L over the lanes
            col = COLOR_RGB["Y"] if self.lanes[i] else (200, 190, 220)
            draw_text(surf, font(18), "ROLL"[i], (TX + x + jolt[0], TY + LANE_Y[0] - 12 + jolt[1]), col,
                      center=True, shadow=INK)
        self._panel(surf, t)
        self.fx.draw(surf)
        for text, x, y, age, col in self.words:
            draw_text(surf, font(22 if len(text) < 8 else 26), text, (TX + x, TY + y - age * 30), col,
                      center=True, shadow=INK)
        if self.banner is not None:
            title, line, age = self.banner
            k = min(1.0, age / 0.3, (2.4 - age) / 0.4)
            box = pygame.Rect(0, 0, 300, 84)
            box.center = (TX + TW // 2 - 20, TY + 300)
            plate = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(plate, (*INK, int(200 * k)), plate.get_rect(), border_radius=16)
            surf.blit(plate, box.topleft)
            f1 = font(34).render(title, True, WHITE)
            f1.set_alpha(int(255 * k))
            surf.blit(f1, f1.get_rect(center=(box.centerx, box.y + 28)))
            a, b = self.left.color, self.right.color
            f2 = font(22).render(line, True, WHITE)
            f2.set_alpha(int(255 * k))
            surf.blit(f2, f2.get_rect(center=(box.centerx, box.y + 60)))
            pygame.draw.circle(surf, COLOR_RGB[a], (box.x + 24, box.y + 60), 9)
            pygame.draw.circle(surf, COLOR_RGB[b], (box.right - 24, box.y + 60), 9)
        if self.flash > 0:
            veil = pygame.Surface((TW, TH), pygame.SRCALPHA)
            veil.fill((255, 255, 255, int(140 * min(1.0, self.flash))))
            surf.blit(veil, (TX, TY))
        if self.over is not None:
            k = min(1.0, self.over / 0.4)
            card = draw_card(surf, (TX + 20, int(220 - 30 * (1 - k)), TW - 40, 180))
            draw_text(surf, font(38), "%d points!" % self.score, (card.centerx, card.y + 40), INK, center=True)
            draw_text(surf, font(20), "%d set rolling, %d sides grown, stage %d. Best: %d." % (
                self.freed, self.sides_given, self.stage, max(self.best, self.score)),
                (card.centerx, card.y + 86), INK, center=True)
            if self.over > 1.0:
                draw_text(surf, font(22), "Space: again!   Esc: back", (card.centerx, card.bottom - 34), INK,
                          center=True)
        self.draw_buttons(surf)

    def _paint(self, L, t):
        """The moving parts, on the low-res table: lights, lanes, flippers,
        bumpers, shapes, the knothole, and you."""
        # chase lights along the rails
        n = 36
        for i in range(n):
            a = math.pi + math.pi * i / (n - 1)
            x = (TW / 2 + math.cos(a) * (TW / 2 - 8)) / PK
            y = (TW / 2 + math.sin(a) * (TW / 2 - 8)) / PK
            on = (i + int(t * 12)) % 6 == 0
            c = COLOR_RGB[RAINBOW[(i // 6) % 6]]
            L.set_at((int(x), int(y)), c if on else shade(c, -3))
        # rollover lanes
        for i, x in enumerate(LANES):
            lit = self.lanes[i]
            c = COLOR_RGB["Y"] if lit else (90, 80, 110)
            pygame.draw.rect(L, c, (x // PK - 2, (LANE_Y[1] + 6) // PK, 5, 3))
            if lit and int(t * 6) % 2:
                pygame.draw.rect(L, (255, 255, 230), (x // PK - 1, (LANE_Y[1] + 6) // PK, 3, 1))
        # the knothole
        sx, sy, sr = SAUCER
        glow = 0.5 + 0.5 * math.sin(t * 5)
        pygame.draw.circle(L, mix((150, 100, 60), (255, 220, 140), glow * 0.4), (sx // PK, sy // PK), sr // PK + 3)
        pygame.draw.circle(L, (34, 22, 30), (sx // PK, sy // PK), sr // PK + 1)
        for k in range(3):
            a = t * 3 + k * math.tau / 3
            L.set_at((int(sx / PK + math.cos(a) * 3), int(sy / PK + math.sin(a) * 3)),
                     COLOR_RGB[RAINBOW[(k * 2 + int(t * 4)) % 6]])
        # bumpers: mushrooms, round, they don't mind
        for i, (x, y, r) in enumerate(BUMPERS):
            lit = self.bumper_glow[i] > 0
            img = _bumper_sprite(lit)
            L.blit(img, (x // PK - img.get_width() // 2, y // PK - img.get_height() // 2))
        # slingshots glow when they kick
        for i, (ax, ay, bx, by) in enumerate(((44, TH - 250, 92, TH - 160), (FW - 44, TH - 250, FW - 92, TH - 160))):
            c = (255, 255, 210) if self.sling_glow[i] > 0 else COLOR_RGB["Y"]
            pygame.draw.line(L, OUTLINE, (ax // PK, ay // PK), (bx // PK, by // PK), 4)
            pygame.draw.line(L, c, (ax // PK, ay // PK), (bx // PK, by // PK), 2)
        # drop targets
        for i, (x, y, c) in enumerate(DROPS):
            if self.drops[i]:
                pygame.draw.rect(L, OUTLINE, (x // PK - 2, (y - 10) // PK - 1, 5, 12))
                pygame.draw.rect(L, COLOR_RGB[c], (x // PK - 1, (y - 10) // PK, 3, 10))
                L.set_at((x // PK - 1, (y - 10) // PK), shade(COLOR_RGB[c], 2))
            else:
                pygame.draw.rect(L, shade(COLOR_RGB[c], -3), (x // PK - 1, (y - 2) // PK, 3, 2))
        # the spinner: a little plate on a wire, whirring
        x0, x1, sy = SPINNER
        pygame.draw.line(L, (200, 200, 220), (x0 // PK, sy // PK), (x1 // PK, sy // PK))
        face = abs(math.cos(self.spin_a * math.pi))
        ph = max(1, int(5 * face))
        pygame.draw.rect(L, OUTLINE, ((x0 + x1) // 2 // PK - 8, sy // PK - ph, 17, ph * 2 + 1))
        pygame.draw.rect(L, (250, 220, 120) if self.spin > 1 else (200, 180, 140),
                         ((x0 + x1) // 2 // PK - 7, sy // PK - ph + 1, 15, ph * 2 - 1))
        # the plunger
        ly = (TH - 40 + BALL + 4 + self.charge * 20) // PK
        pygame.draw.rect(L, OUTLINE, ((FW + 8) // PK, ly, (TW - FW - 16) // PK, 12))
        pygame.draw.rect(L, COLOR_RGB["R"], ((FW + 10) // PK, ly + 1, (TW - FW - 20) // PK, 4))
        # flippers, in their colours
        for fl in (self.left, self.right):
            a, b = fl.tip(), (fl.px, fl.py)
            col = COLOR_RGB[fl.color]
            pygame.draw.line(L, OUTLINE, (b[0] / PK, b[1] / PK), (a[0] / PK, a[1] / PK), FLIP_R + 2)
            pygame.draw.line(L, shade(col, -1), (b[0] / PK, b[1] / PK + 1), (a[0] / PK, a[1] / PK + 1), FLIP_R - 2)
            pygame.draw.line(L, col, (b[0] / PK, b[1] / PK - 1), (a[0] / PK, a[1] / PK - 1), FLIP_R - 4)
            pygame.draw.circle(L, OUTLINE, (int(b[0] / PK), int(b[1] / PK)), FLIP_R // 2 + 2)
            pygame.draw.circle(L, (255, 255, 255), (int(b[0] / PK), int(b[1] / PK)), FLIP_R // 2 - 1)
        for b in self.balls:                                   # your trail, in your colour
            for i, (x, y, c) in enumerate(b.trail):
                col = COLOR_RGB[c] if c else (255, 255, 255)
                L.set_at((int(x / PK), int(y / PK)), mix(col, (255, 255, 255), 0.3))

    def _actors(self, surf, t, jolt):
        """The shapes and you: smooth and round, on top of the pixel table."""
        ox, oy = TX + jolt[0], TY + jolt[1]
        for tg in self.targets:
            self._shape(surf, tg, t, ox, oy)
        you = shape_of(self.you_sides)
        for b in self.balls:
            if b.held > 0 and int(t * 10) % 2:
                continue
            rot = (b.x + b.y) / BALL
            if b.color:
                draw_critter(surf, you, ox + b.x, oy + b.y, BALL, COLOR_RGB[b.color], mood="happy", rot=rot,
                             shadow=False)
            else:
                draw_player(surf, you, ox + b.x, oy + b.y, BALL, t, mood="happy", rot=rot, shadow=False)

    def _shape(self, surf, tg, t, ox, oy):
        grow = min(1.0, tg.age / 0.3)
        x = ox + tg.x + math.sin(t * 40) * 4 * tg.wiggle
        y = oy + tg.y
        r = tg.r * (0.4 + 0.6 * grow) * (1 + 0.15 * tg.happy) * 0.8
        col = COLOR_RGB[tg.color]
        if tg.free is not None:
            draw_critter(surf, "circle", x, y, r, col, mood="happy", rot=tg.free[1] * 8, shadow=False)
            return
        shape = SHAPE_NAMES.get(tg.sides, tg.sides)
        draw_critter(surf, shape, x, y, r, col, mood="happy" if tg.happy else ("wow" if tg.wiggle else "plain"),
                     look=(0, 1), shadow=False)
        draw_colour_mark(surf, tg.color, x + r * 0.8, y - r * 0.8, 5)
        for k in range(self.grow_to - 3):                      # how far to round: pips
            px = int(x) - (self.grow_to - 4) * 4 + k * 8
            done = k < tg.sides - 3
            pygame.draw.circle(surf, INK, (px, int(y + r + 9)), 4)
            pygame.draw.circle(surf, WHITE if done else shade(col, -2), (px, int(y + r + 9)), 3)

    def _glow(self, surf, t, jolt):
        """Light on top: bumpers flaring, your colour glowing, shapes of your colour shimmering."""
        glow = pygame.Surface((TW, TH))                     # additive light: black adds nothing

        def light(col, k):
            return tuple(int(c * max(0.0, min(1.0, k))) for c in col)
        for i, (x, y, r) in enumerate(BUMPERS):
            if self.bumper_glow[i] > 0:
                pygame.draw.circle(glow, light((255, 160, 240), self.bumper_glow[i] / 0.35 * 0.6), (x, y), r + 14)
        for b in self.balls:
            col = COLOR_RGB[b.color] if b.color else (255, 255, 255)
            pygame.draw.circle(glow, light(col, 0.22), (int(b.x), int(b.y)), BALL + 12)
            pygame.draw.circle(glow, light(col, 0.22), (int(b.x), int(b.y)), BALL + 6)
            for tg in self.targets:
                if tg.free is None and b.color == tg.color:
                    pygame.draw.circle(glow, light(col, 0.35 + 0.25 * math.sin(t * 6)), (int(tg.x), int(tg.y)),
                                       tg.r + 10, 4)
        if self.save_t > 0 and int(t * 4) % 2:
            pygame.draw.rect(glow, light(COLOR_RGB["C"], 0.6), (FW // 2 - 60, TH - 24, 120, 10), border_radius=5)
        for i in range(4):                                  # lit lanes shine
            if self.lanes[i]:
                pygame.draw.circle(glow, light(COLOR_RGB["Y"], 0.4), (LANES[i], LANE_Y[1] + 8), 14)
        surf.blit(glow, (TX + jolt[0], TY + jolt[1]), special_flags=pygame.BLEND_RGB_ADD)

    def _panel(self, surf, t):
        """Left: score, stage, the two colours. Right: the host and the controls."""
        card = draw_card(surf, (14, 16, 222, 566), PAPER, 16)
        draw_text(surf, font(30), "Side Show!", (card.centerx, card.y + 26), INK, center=True)
        draw_text(surf, font(34), "%d" % self.score, (card.centerx, card.y + 70), INK, center=True)
        draw_text(surf, font(18), "x%d multiplier   stage %d" % (self.mult, self.stage), (card.centerx, card.y + 100),
                  (120, 106, 150), center=True)
        draw_text(surf, font(20), "The flippers paint you:", (card.centerx, card.y + 140), INK, center=True)
        for k, fl in enumerate((self.left, self.right)):
            cx = card.x + 60 + k * 100
            col = COLOR_RGB[fl.color]
            pygame.draw.rect(surf, INK, (cx - 36, card.y + 162, 72, 22), border_radius=11)
            pygame.draw.rect(surf, col, (cx - 34, card.y + 164, 68, 18), border_radius=9)
            draw_colour_mark(surf, fl.color, cx, card.y + 173, 6)
            draw_text(surf, font(18), ("left", "right")[k], (cx, card.y + 200), INK, center=True)
            draw_text(surf, font(18), COLOR_NAMES[fl.color], (cx, card.y + 220), col, center=True, shadow=INK)
        you = self.color
        draw_text(surf, font(20), "You are: %s" % (COLOR_NAMES[you] if you else "white (no colour yet)"),
                  (card.centerx, card.y + 256), COLOR_RGB[you] if you else INK, center=True,
                  shadow=INK if you else None)
        words = ("Hit a shape in its own colour: it grows a side. Round, and it rolls free. "
                 "Free them all to clear the stage. The knothole bursts your colour over every "
                 "matching shape.")
        draw_wrapped(surf, font(17), words, (card.x + 12, card.y + 284), card.w - 24, INK, 1, center=True)
        left = self.to_free - self._freed_stage
        draw_text(surf, font(20), "Shapes to free: %d" % max(0, left), (card.centerx, card.bottom - 92), INK,
                  center=True)
        draw_text(surf, font(20), "Balls: " + "o " * max(0, self.balls_left), (card.centerx, card.bottom - 64),
                  INK, center=True)
        hint = "Space: launch (hold)" if any(b.in_lane and b.vy == 0 for b in self.balls) else "<- ->: flippers"
        draw_text(surf, font(18), hint, (card.centerx, card.bottom - 36), (120, 106, 150), center=True)
        surf.blit(_marquee(int(t * 8) % 8), (726, 14))              # a lit sign, bulbs chasing
        draw_text(surf, font(30), "SIDE SHOW", (837, 52), WHITE, center=True, shadow=INK)
        draw_text(surf, font(18), "best %d" % max(self.best, self.score), (837, 84), (255, 230, 160), center=True,
                  shadow=INK)
        keys = draw_card(surf, (726, 120, 222, 124), PAPER, 14)
        for i, line in enumerate(("<- or Z: left flipper", "-> or /: right flipper",
                                  "Space: launch (hold it)", "Esc: back")):
            draw_text(surf, font(18), line, (keys.x + 14, keys.y + 12 + i * 26), INK)
        # the host, cheering from the right
        from .consts import TOWERS
        hx, hy = 835, 520
        bob = abs(math.sin(t * 3)) * 10
        f = TOWERS[self.host_tower]["friend"]
        n = self.host_sides
        draw_critter(surf, n, hx, hy - bob, 40, COLOR_RGB[f["color"]], mood="happy",
                     look=((TX + FW / 2 - hx) / 300, -1), rot=t * 0.5)
        line = "Go go go!" if self.over is None else "Again? Again!"
        if self.words and self.words[-1][4] == WHITE:
            line = "They're FREE!"
        fnt = font(22)
        box = pygame.Rect(0, 0, fnt.size(line)[0] + 24, 34)
        box.midbottom = (hx, int(hy - 60 - bob))
        pygame.draw.rect(surf, WHITE, box, border_radius=12)
        pygame.draw.rect(surf, INK, box, 2, border_radius=12)
        draw_text(surf, fnt, line, box.center, INK, center=True)


# ------------------------------------------------------------------- art

def _backdrop(theme):
    """The room the table stands in: the zone's colours, in pixel bands, with twinkles."""
    def build():
        top, bottom, rail = THEMES[theme]
        p = Pix(480, 320, seed=3)
        p.vgrad(0, 0, 480, 320, mix(top, (255, 255, 255), 0.35), mix(bottom, top, 0.4), steps=8)
        for _ in range(90):
            x, y = p.rng.randint(0, 479), p.rng.randint(0, 319)
            p.px(x, y, mix(rail, (255, 255, 255), 0.5))
        return p.up(2)
    return cached(("pb_backdrop", theme), build)


def _table_canvas(theme):
    """The table itself, painted once: felt, rainbow arcs, rails, the lane
    guides, the funnels."""
    def build():
        top, bottom, rail = THEMES[theme]
        w, h = TW // PK, TH // PK
        p = Pix(w, h, seed=9)
        p.vgrad(0, 0, w, h, top, bottom, steps=8)
        for k, c in enumerate(RAINBOW):                          # soft rainbow arcs in the felt
            pygame.draw.circle(p.s, mix(COLOR_RGB[c], bottom, 0.7), (w // 2, h - 30), 165 - k * 13, 5)
        for _ in range(60):
            x, y = p.rng.randint(4, w - 5), p.rng.randint(4, h - 5)
            p.px(x, y, mix(rail, top, 0.5))
        for y in range(70, h - 40, 16):                           # arrow inserts pointing up the middle
            p.poly([(w // 2 - 4, y + 6), (w // 2, y), (w // 2 + 4, y + 6)], mix(rail, bottom, 0.55))
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, w // 2, w, h), border_radius=10)
        pygame.draw.circle(mask, (255, 255, 255, 255), (w // 2, w // 2), w // 2)
        p.s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        r = ramp(rail)
        walls = table_walls()
        for ax, ay, bx, by, kick in walls:
            if kick:
                continue
            pygame.draw.line(p.s, OUTLINE, (ax / PK, ay / PK), (bx / PK, by / PK), 4)
            pygame.draw.line(p.s, r[2], (ax / PK, ay / PK), (bx / PK, by / PK), 2)
            pygame.draw.line(p.s, r[4], (ax / PK, ay / PK - 1), (bx / PK, by / PK - 1), 1)
        return p.s
    return cached(("pb_table", theme), build)


def _bumper_sprite(lit):
    def build():
        p = Pix(26, 26)
        cap = (255, 150, 230) if lit else (226, 90, 190)
        p.disc(13, 14, 11, shade(cap, -2))
        p.disc(13, 13, 11, cap)
        p.disc(11, 11, 6, shade(cap, 1))
        for dx, dy in ((-5, -3), (4, -5), (5, 3), (-3, 5), (0, 0)):
            p.rect(13 + dx - 1, 13 + dy - 1, 3, 2, (255, 255, 255))
        p.outline()
        return p.s
    return cached(("pb_bumper", lit), build)


def _marquee(frame):
    """The sign over the table: a dark board ringed with bulbs, chasing."""
    def build():
        p = Pix(111, 50)
        p.rect(0, 0, 111, 50, (60, 30, 80))
        p.rect(2, 2, 107, 46, (90, 44, 110))
        p.rect(5, 5, 101, 40, (40, 20, 60))
        n = 0
        for x in range(3, 109, 5):
            for y in (1, 47):
                on = (n + frame) % 4 == 0
                c = COLOR_RGB[RAINBOW[n % 6]]
                p.rect(x, y, 2, 2, c if on else shade(c, -3))
                n += 1
        for y in range(6, 46, 5):
            for x in (1, 108):
                on = (n + frame) % 4 == 0
                c = COLOR_RGB[RAINBOW[n % 6]]
                p.rect(x, y, 2, 2, c if on else shade(c, -3))
                n += 1
        p.outline()
        return p.up(2)
    return cached(("pb_marquee", frame), build)
