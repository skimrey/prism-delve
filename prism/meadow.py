"""The Meadow: the only place in the game without a grid, beats, or points.

After the Round Door and the Long Ramp you land here, and for the first time
you steer freely: roll, pick up speed down hills, hop, bump into other
rollers. Everyone here used to be something with corners, and each will tell
you about it if you roll up and say hello (Space). Nothing here can be won.
Esc, whenever you like, and Tri rests.

Nobody here is perfectly round, and nobody needs to be. Sides aren't sanded
off; they're grown. Every Keeper, every bump, every time through adds one,
and a shape that's been through enough is round enough to roll. The old
hands have so many sides you can't count them; the newcomers go ka-thunk.

Later, opened from the title, the Meadow is a hub that goes on zone after
zone (see world.py): each zone ends at a tower with someone at its window,
and each one you get out opens the next zone, whose game it runs. The
landscape is painted as pixel art by hubart.py; this module is the rolling,
the talking, and the characters.
"""

import math
import random

import pygame

from . import sound
from .art import Particles, draw_critter, draw_player
from .consts import COLOR_RGB, RAINBOW, TOWERS
from .enemies import KINDS
from .hubart import K, LH, LW, HubPainter
from .pixel import OUTLINE, Pix, cached
from .screens import Screen
from .widgets import INK, WHITE, draw_text, font, wrap_text
from .world import (KICK_START, LIP, ROUND_ENOUGH, TOWER_X, WINDOW, WORLD, World, ZONES, friend_sides,
                    ground_y, meadow_hub, plan_of, shape_of, your_sides)

HUB_WORLD = 5000                # the hub before anyone is out: on past the Stillwheel to the first tower
COYOTE = 0.12                   # a hop just after rolling off an edge still counts
BALL_R = 26
ACCEL, MAX_V, FRICTION = 620.0, 640.0, 0.9
GRAVITY, HOP = 1500.0, 560.0
TALK_RANGE = 120
ROOT_FLING = 520.0              # fast enough, and a root flings you over it
SPRING_KICK = 820.0
hub_ground_y = meadow_hub       # (the Meadow part of the hub, for the physics tests)
EXPORTS = (KICK_START, LIP, TOWER_X, WINDOW, ZONES)   # the Meadow's geometry lives in world.py


def slope(x, land=ground_y):
    return (land(x + 2) - land(x - 2)) / 4.0


# Everyone here was once a shape with corners. (colour, what they were, where
# they hang about, what they say, how many sides they've grown: 0 = can't count)
FRIENDS = [
    ("Y", "triangle", 420, ("Another triangle! I was one too.",
                            "The Set knocked me back into my slot nine times.",
                            "The tenth time, I rolled.",
                            "I've got about twenty sides now. Every bump's another one."), 20),
    ("R", "square", 900, ("I was a square for the longest time.",
                          "Four corners. Four floors of worrying about them.",
                          "Then one day I just stopped counting."), 24),
    ("C", "square", 1260, ("Don't tell anyone, but I was one of the Set.",
                           "Stomped around in formation. Kept everybody in their slot.",
                           "Then a triangle slipped through our line and I thought:",
                           "wait. You can LEAVE?",
                           "I'm still new out here. Ten sides. Ka-thunk, ka-thunk."), 10),
    ("G", "pentagon", 1720, ("Did you meet the Polisher? It buffed a facet onto me.",
                             "Took forever and tickled the whole time. See it glint?",
                             "You keep what you went through. It just stops being sharp."), 14),
    ("B", "hexagon", 2150, ("I was a hexagon. So nearly round nobody noticed I left.",
                            "The Round Door gave me a few more sides. It felt like a hug.",
                            "Nobody out here is perfectly round. We just rolled a lot."), 30),
    ("M", "circle", 2620, ("I was a Bloom. A circle with roots.",
                           "I was round the whole time. I just wouldn't move.",
                           "Turns out roots come loose if you wiggle."), 0),
    ("Y", "diamond", 2980, ("Race you to the end!",), 18),
]
# Shapes in the Meadow that have only just started rolling (colour, was, home, lines, sides).
NEWCOMERS = [
    ("R", "triangle", 1500, ("Is this rolling? It feels like falling over. Lots.",
                             "Four sides! I only had three yesterday!",
                             "Ka... thunk. Ka... thunk. I'm getting the hang of it."), 4),
    ("G", "square", 2400, ("Ka-THUNK. Oh! Hello! I'm new at this.",
                           "Five sides so far. Every corner's a little hop.",
                           "They say it gets smoother. I believe them."), 5),
]
STILLWHEEL = (3260, ("I kept the Round Door shut. I thought someone had to stay.",
                     "Turns out the door works fine on its own.",
                     "...Why did nobody tell me rolling was this nice?"))

# The Roll-Off host: a beach-ball of a circle who runs the spheres' favourite
# game (see rolloff.py), at the start of the Meadow. The last line is the invitation.
HOST_X = 620
HOST_LINES = ("Hiya! You rolled out! That means you can play ROLL-OFF!",
              "Everyone rolls onto the big bowl. Last one still on it wins.",
              "And falling off is the BEST part. Splash! Right into the colour pool!",
              "Wanna play? Space: let's roll!")
HOST_AGAIN = ("Again? Again! Space: let's roll!",)
# Every later zone's game is run by the friend whose rescue opened it.
GAME_LINES = {
    "pinball": ("You came through! Look what I found out here: a table!",
                "You're the ball. Hit a shape in its OWN colour and it grows a side.",
                "The left flipper turns you one colour, the right flipper the other.",
                "Grow a shape all the way round and it rolls off free. Like you did for me!",
                "Wanna play? Space: flip!"),
    "rolloff": ("You came through! Guess what they play out here? Roll-Off!",
                "Everyone onto the bowl. Last one still on it wins.",
                "Falling off is the best part. Trust me.",
                "Wanna play? Space: let's roll!"),
    "sporedrop": ("You made it to the Grove! Want to wake some shapes up?",
                  "Drop from the big cap and bounce down through them. Everything you touch lights up.",
                  "When you leave, they all float away round. Wake all the sleepy ones!",
                  "Wanna play? Space: drop!"),
    "curl": ("Brr! You made it! Fancy a slide?",
             "Slide down the ice to the rings. Hold Space while you go to sweep: you'll go further.",
             "Closest to the middle scores. Knock theirs away if you like!",
             "Wanna play? Space: slide!"),
    "duneputt": ("You came all this way! Golf?",
                 "Six holes. Dunes push you sideways, sand slows you, the oasis sends you back.",
                 "The hole's round. The only thing out here rounder than you.",
                 "Wanna play? Space: tee off!"),
    "glimmerpop": ("Ooh, you found the caves! Look at all the crystals!",
                   "Fly up at them. Three of a colour touching: they round off and float away.",
                   "Anything left hanging drops too. Watch the roof, it settles!",
                   "Wanna play? Space: pop!"),
    "beachbowl": ("You made it to the Coast! Bowling?",
                  "You roll until you hit something. You're SO good at that.",
                  "Ten sandcastles. All ten at once is a strike!",
                  "Wanna play? Space: roll!"),
    "skyball": ("You made it up here! Feel that wind?",
                "Roll up the lane, off the ramp, and come down in a ring.",
                "The wind changes every throw. The corner holes are worth the most!",
                "Wanna play? Space: fly!"),
}
GAME_AGAIN = {"pinball": ("Another go? Space: flip!",), "rolloff": ("Again? Again! Space: let's roll!",),
              "sporedrop": ("Another drop? Space!",), "curl": ("Another end? Space!",),
              "duneputt": ("Another round? Space!",), "glimmerpop": ("More popping? Space!",),
              "beachbowl": ("Another game? Space!",), "skyball": ("Another go? Space!",)}
SHOW_LINES = GAME_LINES["pinball"]
# What a Keeper says last, once its friend is out: its tower's floors reshuffle for every climb.
KEEPER_INVITE = "The floors have all shuffled since you came. Climb again? Space: up we go!"
# The guardians, after: nobody has to leave, and they don't. They just change jobs.
KEEPER_AFTER = {
    "latch": ("I used to keep that window shut.", "Now I keep this door open. It's a much nicer job.",
              "Mind the roots, out there!"),
    "knot": ("I held on so tight, I forgot what for.", "The square's out. The tree's still standing. Huh.",
             "Maybe I'll loosen up a little more. Slowly."),
    "cap": ("I still bounce. But only when someone wants to.", "Landing's nice, isn't it? I tried it."),
    "rime": ("Drip. Drip. I'm melting a little every day.", "It's nicer than I thought. Everything moves."),
    "hour": ("Time's still going. I checked. Several times.", "The shadow points by itself now. Who knew?"),
    "focus": ("Look at all the little rainbows.", "I used to think a straight line was the only way."),
    "beacon": ("I turn the lamp myself now. Round and round.", "No ships yet. Lovely view, though."),
    "vane": ("I still turn with the wind. That's just me.", "But you don't have to. Off you go!"),
}
LATCH_LINES, KNOT_LINES = KEEPER_AFTER["latch"], KEEPER_AFTER["knot"]
GUARD_COLOURS = {"latch": (224, 90, 200), "knot": (140, 160, 70), "cap": (240, 120, 110),
                 "rime": (150, 200, 240), "hour": (230, 190, 110), "focus": (170, 130, 240),
                 "beacon": (250, 190, 90), "vane": (140, 150, 180)}


def friend_home(tid, app=None):
    """Where a friend you got out of a tower lives in the hub."""
    data = app.meta.data if app is not None else {}
    pretend = getattr(app, "hub_rescued", None) if app is not None else None
    rescued = set(pretend if pretend is not None else data.get("friends", [])) | {tid}
    return World(plan_of(data), rescued).home_of(tid)


class Ball:
    """Anything that rolls here. On the ground it follows the land; in the air
    it flies. Leaving the ground (a hop, or the land dropping away under you)
    you keep the land's slope as upward speed, so a fast roll up a ramp
    launches you. `grip` and `push_k` change on ice; `wind` pushes."""

    def __init__(self, x, r, land=ground_y, width=WORLD):
        self.x, self.r = float(x), r
        self.land, self.width = land, width
        self.vx = 0.0
        self.air = None                       # None on the ground, else the height (screen y)
        self.vy = 0.0                         # screen coordinates: up is negative
        self.rot = 0.0
        self.flying = 9.0                     # seconds since rolling off an edge (not hopping)
        self.hopped = False
        self.grip, self.push_k, self.wind, self.drag = 1.0, 1.0, 0.0, 0.0

    @property
    def y(self):
        return self.air if self.air is not None else self.land(self.x) - self.r

    @property
    def lift(self):
        """How high above the ground (0 when on it)."""
        return 0.0 if self.air is None else max(0.0, self.land(self.x) - self.r - self.air)

    def step(self, dt, push=0.0):
        s = slope(self.x, self.land)
        if self.air is None:
            self.vx += GRAVITY * 0.55 * s / math.sqrt(1 + s * s) * dt   # downhill speeds you up
        self.vx += push * ACCEL * self.push_k * dt * (1.0 if self.air is None else 0.3)
        self.vx += self.wind * dt
        self.vx -= self.vx * FRICTION * self.grip * dt * (0.3 if push else 1.0)
        self.vx -= self.vx * self.drag * dt
        self.vx = max(-MAX_V, min(MAX_V, self.vx))
        old_y = self.y
        self.x = max(self.r, min(self.width - self.r, self.x + self.vx * dt))
        ground = self.land(self.x) - self.r
        self.flying += dt
        if self.air is None:
            if ground > old_y + 12:                      # the land dropped away: fly off it
                self.air, self.vy = old_y, self.vx * s
                self.flying, self.hopped = 0.0, False
        else:
            self.vy += GRAVITY * dt
            self.air += self.vy * dt
            if self.air >= ground and self.vy > 0:       # land
                self.air, self.vy = None, 0.0
        self.rot += self.vx * dt / self.r

    def hop(self):
        if self.air is None:
            sound.play("step", 0.5)
            self.vy = self.vx * slope(self.x, self.land) - HOP
            self.air = self.y
            self.hopped = True
        elif not self.hopped and self.flying < COYOTE:   # just rolled off an edge: still counts
            sound.play("step", 0.5)
            self.vy = min(self.vy, 0.0) - HOP
            self.hopped = True


class Friend(Ball):
    """Someone to roll up to and talk to. `sides` is how many sides it has
    grown (0: too many to count, so it's drawn as a circle)."""

    def __init__(self, color, was, home, lines, r=22, roamer=False, land=ground_y, width=WORLD,
                 sides=0, tumbler=False):
        super().__init__(home, r, land, width)
        self.color, self.was, self.home, self.lines = color, was, home, lines
        self.sides = sides
        self.line = 0
        self.heard = False
        self.roamer = roamer
        self.tumbler = tumbler          # only just started rolling: up and down all day, ka-thunk
        self.corner = 0
        self.thunked = False            # it just came down on a corner (the screen puffs some dust)
        self.phase = random.Random(home).uniform(0, math.tau)

    def think(self, dt, t, tri):
        """Drift about home; the racer heads for the end once you've spoken;
        a newcomer tumbles up and down, practising."""
        if self.tumbler:
            goal = self.home + math.sin(t * 0.32 + self.phase) * 230
            self.step(dt, max(-0.55, min(0.55, (goal - self.x) / 80.0)))
            if self.sides:
                corner = int(self.rot // (math.tau / self.sides))
                if corner != self.corner and self.air is None:
                    self.thunked = True
                self.corner = corner
            return
        if self.roamer and self.heard:
            goal = min(self.width, 3600) - 300
        else:
            goal = self.home + math.sin(t * 0.4 + self.phase) * 80
        push = max(-0.6, min(0.6, (goal - self.x) / 120.0))
        if self.roamer and self.heard:
            push = 1.0 if tri.x > self.x - 40 else 0.25
        self.step(dt, push)
        if random.Random(int(t * 3) + int(self.home)).random() < 0.004 and self.lift <= 0:
            self.hop()

    def thunk(self):
        """How far it rides up on a corner right now (a polygon rolling bumps)."""
        if not self.sides:
            return 0.0
        seg = math.tau / self.sides
        return self.r * (1 - math.cos(math.pi / self.sides)) * abs(math.sin((self.rot % seg) / seg * math.pi))


class Host(Friend):
    """Runs a game. Bounces on the spot by its sign, can't keep still. Talk
    to it through to the end and you're off to play. `theme` is its zone."""

    def __init__(self, game, home, lines, color, land, width, sides=0, r=30, theme="meadow", was=None,
                 key=None):
        super().__init__(color, was or ("circle" if not sides else "hexagon"), home, lines, r=r, land=land,
                         width=width, sides=sides)
        self.game, self.theme = game, theme
        self.key = key or "%s:%s" % (game, theme)
        self.beachball = key == "rolloff:meadow"

    def think(self, dt, t, tri):
        push = max(-0.6, min(0.6, (self.home - self.x) / 60.0))
        self.step(dt, push)
        if self.air is None and (t + self.phase) % 1.3 < dt * 1.5:
            self.hop()


class Keeper(Friend):
    """A tower's guardian, after: it stays put (it never wanted to roll), and
    it's doing a different job now."""

    def __init__(self, kind, home, lines, land, width, tower=None):
        from .enemies import KINDS
        lines = tuple(lines) + ((KEEPER_INVITE,) if tower else ())
        super().__init__("M", KINDS[kind]["shape"], home, lines, r=30, land=land, width=width)
        self.kind = kind
        self.tower = tower              # talk it through to the end and it lets you climb again

    def think(self, dt, t, tri):
        self.x = float(self.home)


class MeadowScreen(Screen):
    """Roll about. Say hello. Rest when you like.

    The first time, after the Long Ramp, this is the epilogue: the meadow ends
    at the Stillwheel's hill, and resting ends the climb. Later, opened from
    the title, it is the hub: see the module docstring. Get up enough speed,
    hop at the lip of a kicker, and you're in through a tower's window."""

    def __init__(self, app, hub=False, start_x=None, rescued=None, back_from=None):
        super().__init__(app)
        self.hub = hub
        if rescued is None:
            rescued = getattr(app, "hub_rescued", None)      # (dev mode can pretend)
        if rescued is None:
            rescued = app.meta.data.get("friends", []) if hub else []
        self.rescued = set(rescued) if hub else set()
        self.sides = dict(app.meta.data.get("sides", {}))
        self.plan = plan_of(app.meta.data) if hub else ["leaning"]
        self.you_sides = your_sides(app.meta.data, self.rescued) if hub else ROUND_ENOUGH
        from .settings import SETTINGS
        self.open_all = hub and (SETTINGS.get("open_zones") or bool(getattr(app, "dev_open_zones", False)))
        self.world = World(self.plan, self.rescued if hub else (), self.open_all)
        self.land = self.world.ground if hub else ground_y
        self.width = self.world.width if hub else WORLD
        self.wilds = hub and len(self.world.zones) > 1           # past the Meadow?
        start_x = min(start_x, self.width - 60) if start_x else None
        self.tri = Ball(start_x or 160, BALL_R, self.land, self.width)
        self.tri.vx = 380.0 if not hub else (0.0 if start_x else 120.0)   # still rolling from the ramp
        w = self.width
        self.friends = [Friend(c, was, home, lines, roamer=(was == "diamond"), land=self.land,
                               width=w, sides=n)
                        for c, was, home, lines, n in FRIENDS]
        self.friends += [Friend(c, was, home, lines, land=self.land, width=w, sides=n, tumbler=True)
                         for c, was, home, lines, n in NEWCOMERS]
        sx, lines = STILLWHEEL
        self.stillwheel = Friend(None, "circle", sx, lines, r=34, land=self.land, width=w)
        self.hosts, self.keepers = [], []
        self.host = self.show = None
        if hub:
            self._people(back_from)
        self.everyone = self.friends + [self.stillwheel] + self.hosts + self.keepers
        self.fx = Particles()
        self.keys = set()
        self.cam = max(0.0, min(self.width - 960.0, self.tri.x - 380))
        self.hop_t = 9.0                                 # time since you last pressed hop
        self.painter = HubPainter(self.world, self.land, self.width, epilogue=not hub)
        self.low = pygame.Surface((LW, LH))
        self.talking = next((h for h in self.hosts if back_from and h.key == back_from), None)
        self.in_pond = False
        self.in_pool = False
        self.region = self.region_at(self.tri.x)
        self.title_text = None if back_from else self.region
        self.title_t = 0.0
        self.entering = None                             # a tower id, once you're through a window
        self.bonked = 0.0                                # seconds to show the "hop the roots" hint
        self.sprung = 0.0

    def _people(self, back_from):
        """Who lives where: the Roll-Off host; in each later zone, the friend
        whose rescue opened it (running the zone's game) and the locals; by
        each open door, its tower's guardian."""
        world, land, w = self.world, self.land, self.width
        self.host = Host("rolloff", HOST_X, HOST_AGAIN if back_from == "rolloff:meadow" else HOST_LINES, "M",
                         land, w, key="rolloff:meadow")
        self.hosts.append(self.host)
        for z in world.zones[1:]:
            prev = world.plan[z.index - 1]
            f = TOWERS[prev]["friend"]
            if prev not in self.rescued and z.locals:        # (every zone open: a local runs it for now)
                c, was, _home, _lines, _n = z.locals[0]
                f = {"color": c, "was": was}
            game = z.spec["game"]
            key = "%s:%s" % (game, z.kind)
            lines = GAME_AGAIN[game] if back_from == key else GAME_LINES[game]
            host = Host(game, z.host_x, lines, f["color"], land, w, r=26,
                        sides=friend_sides(prev, self.app.meta.data, self.rescued),
                        theme=z.kind, was=f["was"], key=key)
            self.hosts.append(host)
            if z.index == 1:
                self.show = host
            for c, was, home, lines_, n in z.locals:
                self.friends.append(Friend(c, was, home, lines_, land=land, width=w, sides=n))
            for c, was, home, lines_, n in z.newcomers:
                self.friends.append(Friend(c, was, home, lines_, land=land, width=w, sides=n, tumbler=True))
        last = world.zones[-1]
        if last.tower in self.rescued:                    # everyone's out: the last one rolls about its tower
            f = TOWERS[last.tower]["friend"]
            self.friends.append(Friend(f["color"], f["was"], last.wall - 330, f["lines"], land=land, width=w,
                                       sides=friend_sides(last.tower, self.app.meta.data, self.rescued)))
        for z in world.zones:
            if z.tower in self.rescued:
                boss = TOWERS[z.tower]["boss"]
                self.keepers.append(Keeper(boss, z.wall - 60, KEEPER_AFTER.get(boss, ("...",)), land, w,
                                           tower=z.tower))

    @property
    def waiting(self):
        """Someone is at the first tower's window, waiting for you."""
        return self.waiting_at(self.plan[0])

    def waiting_at(self, tid):
        return self.hub and tid not in self.rescued and any(z.tower == tid for z in self.world.zones)

    def region_at(self, x):
        if not self.hub:
            return "The Meadow"
        z = self.world.zone_at(x - 200)
        return z.spec["name"]

    # -- input
    def nearest(self):
        best = min(self.everyone, key=lambda f: abs(f.x - self.tri.x))
        return best if abs(best.x - self.tri.x) < TALK_RANGE else None

    def talk(self):
        f = self.nearest()
        if f is None:
            return
        if isinstance(f, Host) and self.talking is f and f.line == len(f.lines) - 1:
            sound.play("group")                          # "let's play!"
            self.app.show_game(f.game, f.theme, f.home)
            return
        if isinstance(f, Keeper) and f.tower and self.talking is f and f.line == len(f.lines) - 1:
            sound.play("door")                           # up its tower again, freshly shuffled
            self.app.enter_tower(f.tower)
            return
        if self.talking is f:
            f.line = (f.line + 1) % len(f.lines)
            if f.line == 0:
                f.heard = True
        self.talking = f
        sound.play("talk")
        if len(f.lines) == 1:
            f.heard = True

    def open_map(self):
        """Every tower you've reached, and every zone: go anywhere, climb anything."""
        from .worldmap import MapScreen
        self.keys.clear()
        self.app.push(MapScreen(self.app, here=self.tri.x))

    def rest(self):
        if self.hub:
            self.app.to_title()
        else:
            self.app.show_end()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.rest()
                return True
            if ev.key in (pygame.K_SPACE, pygame.K_e, pygame.K_RETURN):
                self.talk()
                return True
            if ev.key in (pygame.K_m, pygame.K_TAB) and self.hub:
                self.open_map()
                return True
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.hop_t = 0.0
                self.tri.hop()
                return True
            if ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                self.keys.add(ev.key)
                return True
        elif ev.type == pygame.KEYUP:
            self.keys.discard(ev.key)
            return True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.talk()
            return True
        return False

    def push(self):
        left = self.keys & {pygame.K_LEFT, pygame.K_a}
        right = self.keys & {pygame.K_RIGHT, pygame.K_d}
        return (1.0 if right else 0.0) - (1.0 if left else 0.0)

    # -- the world moving
    def update(self, dt):
        super().update(dt)
        dt = min(dt, 0.05)
        tri = self.tri
        self.hop_t += dt
        self.title_t += dt
        self.bonked = max(0.0, self.bonked - dt)
        self.sprung = max(0.0, self.sprung - dt)
        if tri.air is None and self.hop_t < 0.15:        # a hop pressed just before landing counts
            tri.hop()
            self.hop_t = 9.0
        old_x = tri.x
        self._ground_feel(tri)
        tri.step(dt, self.push())
        if self.hub:
            self._tower_physics(tri)
            self._obstacles(tri, old_x)
        for f in self.everyone:
            f.think(dt, self.t, tri)
            if f.thunked:                                # a newcomer's corner comes down: ka-thunk
                f.thunked = False
                near = abs(f.x - tri.x)
                if near < 700:
                    self.fx.burst(f.x, f.y + f.r, (236, 226, 210), n=3, speed=60, shapes=("circle",))
                    sound.play("step", 0.25 * (1 - near / 700))
            gap = f.x - tri.x
            reach = f.r + tri.r
            # rolling through someone: they hop, you pass underneath, nobody gets shoved
            if abs(gap) < reach and f.air is None and tri.lift < reach and not isinstance(f, Keeper):
                f.hop()
                f.vx += (1 if gap >= 0 else -1) * 40
                self.fx.burst(f.x, f.y + f.r, COLOR_RGB[f.color or "M"], n=5, speed=140,
                              shapes=("circle",))
        if self.talking is not None and abs(self.talking.x - tri.x) > TALK_RANGE * 1.6:
            self.talking = None
        pond = abs(tri.x - 2500) < 140 and tri.air is None
        if pond and not self.in_pond:
            for c in RAINBOW:
                self.fx.ring(tri.x, self.land(tri.x) - 6, COLOR_RGB[c], 6, 60, 0.8)
        self.in_pond = pond
        z = self.world.zone_at(tri.x) if self.hub else None
        pool = z is not None and z.pool_at(tri.x) is not None and tri.air is None
        if pool and not self.in_pool:                    # splash!
            sound.play("loose", 0.5)
            for c in ("C", "B", "G"):
                self.fx.ring(tri.x, self.land(tri.x), COLOR_RGB[c], 6, 70, 0.7)
            self.fx.burst(tri.x, self.land(tri.x), WHITE, n=10, speed=220, shapes=("circle",))
        self.in_pool = pool
        region = self.region_at(tri.x)
        if region != self.region:                        # into a new part of the world: its name
            self.region, self.title_text, self.title_t = region, region, 0.0
        sound.roll(abs(tri.vx) / MAX_V if tri.air is None else 0.0)     # the only smooth sound
        self.cam += ((tri.x - 380) - self.cam) * min(1.0, dt * 4)
        self.cam = max(0.0, min(self.width - 960.0, self.cam))
        self.fx.update(dt)
        if self.entering:
            self.app.enter_tower(self.entering)
        return True

    def _ground_feel(self, tri):
        """Ice slides, snow and sand drag, water holds you back, wind pushes."""
        tri.grip, tri.push_k, tri.wind, tri.drag = 1.0, 1.0, 0.0, 0.0
        if not self.hub:
            return
        z = self.world.zone_at(tri.x)
        if tri.air is None and z.pool_at(tri.x) is not None:
            tri.drag = 1.6
        kind = z.region(tri.x)
        if kind == "ice" and tri.air is None:
            tri.grip, tri.push_k = 0.12, 0.45
        elif kind == "drift" and tri.air is None:
            tri.drag = 2.6
        elif kind == "sand" and tri.air is None:
            tri.drag = 1.1
        elif kind == "gust":
            tri.wind = 340.0

    def _obstacles(self, tri, old_x):
        """Roots bonk you (hop them; fast, they fling you over), crystals
        always bounce you back (hop them), big caps throw you in the air."""
        z = self.world.zone_at(tri.x)
        for kind, fx, size in z.features:
            if kind in ("root", "crystal"):
                core = 26 if kind == "root" else 24
                was_out, now_in = abs(old_x - fx) >= core, abs(tri.x - fx) < core
                if not (was_out and now_in) or tri.air is not None:
                    continue
                side = -1 if old_x < fx else 1
                if kind == "root" and abs(tri.vx) >= ROOT_FLING:
                    tri.air = tri.y
                    tri.vy = -260 - abs(tri.vx) * 0.25               # boing
                    tri.flying, tri.hopped = 0.0, True
                    sound.play("step", 0.7)
                    continue
                tri.x = fx + side * core
                tri.vx = side * max(60.0, abs(tri.vx) * (0.35 if kind == "root" else 0.8))
                sound.play("hit" if kind == "root" else "cast:C", 0.5)
                col = (176, 128, 80) if kind == "root" else (200, 170, 255)
                self.fx.burst(tri.x - side * tri.r, tri.y, col, n=6, speed=140, shapes=("circle",))
                self.bonked = 2.5
            elif kind == "spring":
                if tri.air is None and abs(tri.x - fx) < 18 and self.sprung <= 0 and abs(tri.vx) > 20:
                    tri.air = tri.y
                    tri.vy = -SPRING_KICK
                    tri.flying, tri.hopped = 0.0, True
                    self.sprung = 0.5
                    sound.play("step")
                    sound.play("ascend", 0.3)
                    self.fx.burst(fx, tri.y + tri.r, (250, 110, 120), n=8, speed=200, shapes=("circle",))

    def entrances(self):
        """(tower id, its wall's x, its window) for each tower in this world."""
        return [(z.tower, z.wall, z.window) for z in self.world.zones]

    def _tower_physics(self, tri):
        """Towers: a wall bounces you back; the window takes you in (if
        someone's waiting at it). Once a tower's friend is out, its ground
        door stands open and you roll straight through."""
        for tid, wall, (wx, wy, wr) in self.entrances():
            if not (wall < tri.x + tri.r < wall + 200):
                continue
            # the window takes you in: to the one who asked, or (once it's out) for another climb
            if tri.air is not None and abs(tri.y - wy) < wr + tri.r * 0.5:
                sound.play("door")                       # through the window: you're in
                self.entering = tid
                return
            if tid in self.rescued or self.open_all:
                continue                                 # the door's open: through you go
            tri.x = wall - tri.r                         # the wall: bounce back and try again
            tri.vx = -abs(tri.vx) * 0.4
            sound.play("hit", 0.5)

    # -- drawing
    def draw(self, surf):
        t, cam = self.t, self.cam
        L = self.low
        towers = []
        if self.hub:
            for z in self.world.zones:
                f = TOWERS[z.tower]["friend"]
                towers.append((z, (f["was"], COLOR_RGB[f["color"]]) if self.waiting_at(z.tower) else None,
                               z.tower in self.rescued))
        self.painter.paint(L, cam, t, towers)
        cl = int(round(cam / K))
        for h in self.hosts:
            self._sign(L, h, cl, t)
        surf.blit(pygame.transform.scale(L, (LW * K, LH * K)), (0, 0))
        # the characters: smooth and round on top of the pixel world (they're the ones growing round)
        for wx, wy, wr, (shape, color) in self.painter.windows:
            self._waving(surf, wx, wy, wr, shape, color, t)
        for f in self.everyone:
            self._friend(surf, f, cam, t)
        self._you(surf, cam, t)
        front = pygame.Surface((LW, LH), pygame.SRCALPHA)
        self.painter.paint_front(front, cam, t)          # vines and stalactites hang in front of everyone
        surf.blit(pygame.transform.scale(front, (LW * K, LH * K)), (0, 0))
        self.fx.draw(surf, -cam)                         # (particles live in the world)
        if self.hub:
            self._sides_pill(surf)
        for h in self.hosts:
            self._sign_words(surf, h, cam)
            if self.talking is not h and -60 < h.x - cam < 1020:
                self._bang(surf, h.x - cam, h.y - h.r, t)
        self._shouts(surf, cam, t)
        self._bubble(surf, cam)
        if self.title_text and self.title_t < 4:        # words: barely any
            k = min(1.0, self.title_t / 0.6, (4 - self.title_t) / 0.8)
            title = font(64).render(self.title_text, True, WHITE)
            title.set_alpha(int(255 * k))
            shadow = font(64).render(self.title_text, True, INK)
            shadow.set_alpha(int(255 * k))
            surf.blit(shadow, shadow.get_rect(center=(480, 73)))
            surf.blit(title, title.get_rect(center=(480, 70)))
        self._hint(surf)

    def _you(self, surf, cam, t):
        tri = self.tri
        bob = math.sin(t * 4) * 3 if self.in_pool else 0.0
        shape = shape_of(self.you_sides)
        lift = _thunk(self.you_sides, tri.r, tri.rot) if tri.air is None else 0.0
        draw_player(surf, shape, tri.x - cam, tri.y + bob - lift, tri.r, t, mood="happy", rot=tri.rot)

    def _waving(self, surf, x, y, r, shape, color, t):
        """Whoever's at a tower's window: waving, all the time."""
        wave = math.sin(t * 6)
        rr = max(8, r - 12)
        draw_critter(surf, shape, x, y + 4, rr, color, look=(-0.6, 0.5), mood="happy", rot=wave * 0.08,
                     shadow=False, width=2)
        arm = (x + rr + 2, y - 2)
        pygame.draw.line(surf, INK, arm, (arm[0] + 10, arm[1] - 12 + wave * 7), 3)

    def _friend(self, surf, f, cam, t):
        x = f.x - cam
        if not -60 < x < 1020:
            return
        look = ((self.tri.x - f.x) / 200.0, 0)
        if isinstance(f, Keeper):
            y = f.land(f.x) - f.r
            draw_critter(surf, TOWERS_SHAPE.get(f.kind, "square"), x, y, f.r,
                         GUARD_COLOURS.get(f.kind, (224, 90, 200)), look=(look[0], -0.2), mood="happy",
                         face=KINDS[f.kind].get("face"))
            _keeper_prop(surf, f.kind, x, y, f.r, t)
            return
        if isinstance(f, Host) and f.beachball:
            self._beachball(surf, f, x, t)
            return
        color = (150, 140, 170) if f is self.stillwheel else COLOR_RGB[f.color]
        talk = self.talking is f
        mood = "happy" if (talk or f.heard or isinstance(f, Host)) else "plain"
        y = f.y - f.thunk()
        draw_critter(surf, shape_of(f.sides), x, y, f.r, color, look=look, mood=mood, rot=f.rot)
        if f.was != "circle":                            # a faint memory of the shape it used to be
            from .art import draw_body, lighten
            draw_body(surf, f.was, x, y, f.r * 0.55, None, lighten(color, 0.45), 2, f.rot * 0.2)
        if f is self.stillwheel:
            for i, c in enumerate(RAINBOW):
                a = t * 1.2 + i * math.tau / 6
                pygame.draw.circle(surf, COLOR_RGB[c], (int(x + math.cos(a) * (f.r + 12)),
                                                        int(f.y + math.sin(a) * 10 + f.r * 0.6)), 4)

    def _beachball(self, surf, f, x, t):
        """The Roll-Off host: a beach ball with a grin."""
        draw_critter(surf, "circle", x, f.y, f.r, WHITE, look=((self.tri.x - f.x) / 200.0, -0.2),
                     mood="happy", rot=f.rot)
        for i, c in enumerate(RAINBOW):                  # the wedges, turning as it rolls
            a0 = f.rot + i * math.tau / 6
            pts = [(x, f.y)] + [(x + math.cos(a0 + k * 0.2) * (f.r - 2), f.y + math.sin(a0 + k * 0.2) * (f.r - 2))
                                for k in range(6)]
            pygame.draw.polygon(surf, COLOR_RGB[c], pts)
        pygame.draw.circle(surf, INK, (int(x), int(f.y)), f.r, 3)
        pygame.draw.circle(surf, WHITE, (int(x), int(f.y)), int(f.r * 0.42))
        pygame.draw.circle(surf, INK, (int(x), int(f.y)), int(f.r * 0.42), 2)
        from .art import draw_eyes
        draw_eyes(surf, x, f.y - 2, f.r * 0.5, ((self.tri.x - f.x) / 200.0, -0.2), "happy")

    def _sides_pill(self, surf):
        """How round you are, in the corner."""
        n = self.you_sides
        text = "round, all the way round" if not n else "you: %d sides" % n
        f = font(18)
        pill = pygame.Rect(10, 10, f.size(text)[0] + 50, 30)
        plate = pygame.Surface(pill.size, pygame.SRCALPHA)
        pygame.draw.rect(plate, (*INK, 150), plate.get_rect(), border_radius=15)
        surf.blit(plate, pill.topleft)
        draw_player(surf, shape_of(n), pill.x + 18, pill.centery, 9, self.t, shadow=False)
        draw_text(surf, f, text, (pill.x + 34, pill.centery - f.get_height() // 2), WHITE)

    def _sign(self, L, h, cl, t):
        """A game's sign, on a post next to its host."""
        x = int((h.home + 140) / K) - cl
        if not -40 < x < LW + 40:
            return
        gy = int(self.land(h.home + 140) / K)
        L.blit(_sign_board(h.game, int(t * 4) % 4), (x - 17, gy - 38))

    def _sign_words(self, surf, h, cam):
        x = h.home + 140 - cam
        if not -120 < x < 1080:
            return
        gy = self.land(h.home + 140)
        word = {"rolloff": ("Roll-", "Off!"), "pinball": ("Side", "Show!"), "sporedrop": ("Spore", "Drop!"),
                "curl": ("Curl", "!"), "duneputt": ("Dune", "Putt!"), "glimmerpop": ("Glimmer", "Pop!"),
                "beachbowl": ("Beach", "Bowl!"), "skyball": ("Sky", "Ball!")}[h.game]
        draw_text(surf, font(20), word[0], (x + 24, gy - 136), INK, center=True)
        draw_text(surf, font(20), word[1], (x + 24, gy - 116), COLOR_RGB["M"], center=True)

    def _bang(self, surf, x, top, t):
        """The bouncing "!" over a host: come and talk to me."""
        bounce = int(abs(math.sin(t * 4.5)) * 3) * 4
        img = _bang_sprite()
        surf.blit(img, (int(x) - img.get_width() // 2, int(top) - 64 - bounce))

    def _shouts(self, surf, cam, t):
        """Whoever's at a tower's window, calling out when you're near."""
        for z in self.world.zones:
            if not self.waiting_at(z.tower) or not (z.h0 + 300 < self.tri.x < z.wall + 100):
                continue
            if int(t * 1.2) % 3 == 2:
                continue
            wx, wy, wr = z.window
            ask = TOWERS[z.tower]["friend"]["ask"]
            f = font(20)
            box = pygame.Rect(0, 0, f.size(ask)[0] + 20, 30)
            box.midbottom = (int(wx - cam - 40), int(wy - wr - 20))
            box.clamp_ip(pygame.Rect(4, 4, 952, 600))
            pygame.draw.rect(surf, WHITE, box, border_radius=10)
            pygame.draw.rect(surf, INK, box, 2, border_radius=10)
            draw_text(surf, f, ask, box.center, INK, center=True)

    def _hint(self, surf):
        near = self.nearest()
        hint = "<- -> roll    ^ hop    %sEsc: %s" % ("M: map    " if self.hub else "",
                                                   "back to the title" if self.hub else "rest here")
        x = self.tri.x
        z = self.world.zone_at(x) if self.hub else None
        if near is not None:
            hint = "Space: say hello    " + hint
        elif z is not None and self.waiting_at(z.tower) and z.h0 + 100 < x < z.wall:
            hint = "Build up speed downhill, and hop right at the lip!    " + hint
        elif self.bonked:
            hint = "Roots and crystals: hop them (^), or hit them fast.    " + hint
        elif z is not None and z.region(x) == "ice":
            hint = "Ice! Don't push: lean.    " + hint
        f = font(20)
        pill = pygame.Rect(0, 0, f.size(hint)[0] + 28, 28)
        pill.center = (480, 620)
        plate = pygame.Surface(pill.size, pygame.SRCALPHA)
        pygame.draw.rect(plate, (*INK, 150), plate.get_rect(), border_radius=14)
        surf.blit(plate, pill.topleft)
        draw_text(surf, f, hint, pill.center, WHITE, center=True)

    def _bubble(self, surf, cam):
        f = self.talking
        if f is None:
            near = self.nearest()
            if near is not None and not isinstance(near, Host):        # a little "..." invitation
                x, y = near.x - cam, near.y - near.r - 20
                pygame.draw.rect(surf, WHITE, (x - 18, y - 10, 36, 20), border_radius=10)
                pygame.draw.rect(surf, INK, (x - 18, y - 10, 36, 20), 2, border_radius=10)
                for k in range(3):
                    pygame.draw.circle(surf, INK, (int(x - 8 + k * 8), int(y + math.sin(self.t * 6 + k) * 2)), 2)
            return
        fnt = font(22)
        lines = wrap_text(fnt, f.lines[f.line], 300)
        w = max(fnt.size(line)[0] for line in lines) + 24
        h = len(lines) * (fnt.get_height() + 2) + 16
        x, y = f.x - cam, f.y - f.r - 14
        box = pygame.Rect(0, 0, w, h)
        box.midbottom = (int(x), int(y) - 10)
        box.clamp_ip(pygame.Rect(6, 6, 948, 580))
        pygame.draw.polygon(surf, INK, [(x - 9, box.bottom), (x + 9, box.bottom), (x, y + 3)])
        pygame.draw.rect(surf, INK, box.move(0, 3), border_radius=12)
        pygame.draw.rect(surf, WHITE, box, border_radius=12)
        pygame.draw.rect(surf, INK, box, 2, border_radius=12)
        pygame.draw.polygon(surf, WHITE, [(x - 7, box.bottom - 2), (x + 7, box.bottom - 2), (x, y)])
        yy = box.y + 8
        for line in lines:
            draw_text(surf, fnt, line, (box.centerx, yy + fnt.get_height() // 2), INK, center=True)
            yy += fnt.get_height() + 2
        dots = "%d/%d" % (f.line + 1, len(f.lines))
        draw_text(surf, font(16), dots, (box.right - 8, box.bottom - 14), (150, 140, 170), right=True)


TOWERS_SHAPE = {"latch": "square", "knot": "circle", "cap": "circle", "rime": "square", "hour": "triangle",
                "focus": "triangle", "beacon": "circle", "vane": "square"}


# ------------------------------------------------------------- little sprites

def _sign_board(game, frame):
    """A wooden sign on a post, with a little picture of its game."""
    def build():
        p = Pix(34, 40)
        p.rect(15, 14, 3, 26, (120, 84, 56))
        p.rect(1, 1, 32, 16, (236, 200, 150))
        p.rect(1, 1, 32, 2, (250, 226, 180))
        p.rect(1, 15, 32, 2, (190, 150, 100))
        if game == "rolloff":
            for j, c in enumerate(RAINBOW):
                p.ellipse(3 + j, 9 + j // 3, 14 - 2 * j, 5 - j // 2, COLOR_RGB[c])
            p.disc(6 + frame, 6, 2, COLOR_RGB["Y"])
        elif game == "pinball":
            p.line((3, 13), (8, 11 - (frame % 2)), COLOR_RGB["R"], 2)
            p.line((15, 13), (10, 11 - ((frame + 1) % 2)), COLOR_RGB["B"], 2)
            p.disc(9, 5 + frame % 2, 2, COLOR_RGB[RAINBOW[frame]])
        elif game == "sporedrop":
            p.ellipse(3, 3, 12, 5, (250, 110, 170))
            for k, c in enumerate(("C", "M", "Y", "G")):
                p.rect(4 + k * 3, 9 + (k % 2) * 3, 2, 2, COLOR_RGB[c])
            p.disc(9, 9 + frame % 3, 1, (255, 255, 255))
        elif game == "curl":
            for r, c in ((6, (120, 160, 240)), (4, (255, 255, 255)), (2, (240, 120, 150))):
                p.disc(9, 8, r, c)
            p.disc(4 + frame, 13, 2, (200, 220, 255))
        elif game == "duneputt":
            p.rect(3, 11, 14, 3, (116, 196, 170))
            p.disc(12, 12, 1, (40, 30, 30))
            p.line((12, 12), (12, 3), (60, 40, 40))
            p.poly([(12, 3), (16, 4), (12, 6)], COLOR_RGB["M"])
            p.disc(4 + frame, 11, 1, (255, 255, 255))
        elif game == "glimmerpop":
            for k, c in enumerate(("R", "Y", "C", "B")):
                p.poly([(3 + k * 4, 8), (5 + k * 4, 3 + (k % 2) * 2), (7 + k * 4, 8)], COLOR_RGB[c])
            p.disc(9, 13 - frame % 3, 1, COLOR_RGB["M"])
        elif game == "beachbowl":
            for k in range(4):
                p.rect(6 + k * 3, 4 + (k % 2), 2, 4, (250, 226, 170))
                p.px(6 + k * 3, 3 + (k % 2), COLOR_RGB[RAINBOW[k]])
            p.disc(4 + frame, 12, 2, (200, 160, 250))
        else:                                               # sky ball: rings, and a ball in the air
            for r, c in ((6, COLOR_RGB["G"]), (4, COLOR_RGB["C"]), (2, COLOR_RGB["R"])):
                p.disc(11, 9, r, c)
            p.disc(4, 12 - frame, 2, (255, 255, 255))
        p.outline()
        return p.s
    return cached(("signboard", game, frame), build)


def _bang_sprite():
    def build():
        p = Pix(14, 18)
        p.disc(7, 7, 6, (255, 214, 72))
        p.poly([(5, 11), (9, 11), (7, 16)], (255, 214, 72))
        p.rect(6, 3, 2, 6, OUTLINE)
        p.rect(6, 10, 2, 2, OUTLINE)
        p.px(4, 4, (255, 246, 200))
        p.outline()
        return p.up(4)
    return cached(("bang",), build)


def _thunk(sides, r, rot):
    """How far a polygon rides up on a corner as it rolls (0 for a circle)."""
    if not sides:
        return 0.0
    seg = math.tau / sides
    return r * (1 - math.cos(math.pi / sides)) * abs(math.sin((rot % seg) / seg * math.pi))


def _keeper_prop(surf, kind, x, y, r, t):
    """A Keeper at its new job: the Latch leaning on its bolt, the Knot with
    a flower, the Cap with its hat, and so on."""
    if kind == "latch":
        pygame.draw.line(surf, INK, (x + r + 4, y + r), (x + r + 20, y - r - 8), 8)
        pygame.draw.line(surf, (220, 180, 110), (x + r + 4, y + r), (x + r + 20, y - r - 8), 4)
    elif kind == "knot":
        pygame.draw.line(surf, (60, 150, 70), (x + 4, y - r + 2), (x + 8, y - r - 10), 3)
        pygame.draw.circle(surf, (255, 214, 90), (int(x + 9), int(y - r - 12)), 6)
        pygame.draw.circle(surf, INK, (int(x + 9), int(y - r - 12)), 6, 2)
    elif kind == "cap":
        cap = pygame.Rect(0, 0, int(r * 2.2), int(r * 0.9))
        cap.midbottom = (int(x), int(y - r + 8))
        pygame.draw.ellipse(surf, (226, 64, 84), cap)
        pygame.draw.ellipse(surf, INK, cap, 3)
        for dx in (-0.45, 0.1, 0.5):
            pygame.draw.circle(surf, WHITE, (int(x + dx * r), int(cap.centery - 3)), 4)
    elif kind == "rime":
        for k in range(-2, 3):
            tip = (x + k * r * 0.35, y - r - 2)
            pygame.draw.polygon(surf, (220, 240, 255), [(tip[0] - 5, tip[1]), (tip[0] + 5, tip[1]),
                                                        (tip[0], tip[1] - 10 - (k % 2) * 5)])
    elif kind == "beacon":
        glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 230, 150, int(90 + 50 * math.sin(t * 3))), (40, 40), 34)
        surf.blit(glow, (x - 40, y - r - 56))
        pygame.draw.rect(surf, (255, 222, 130), (x - 8, y - r - 26, 16, 18))
        pygame.draw.rect(surf, INK, (x - 8, y - r - 26, 16, 18), 2)
    elif kind == "vane":
        a = math.sin(t * 1.5) * 1.2
        cx, cy = x, y - r - 16
        tip = (cx + math.cos(a) * 22, cy + math.sin(a) * 4)
        tail = (cx - math.cos(a) * 22, cy - math.sin(a) * 4)
        pygame.draw.line(surf, INK, (x, y - r + 2), (cx, cy), 3)
        pygame.draw.line(surf, INK, tail, tip, 5)
        pygame.draw.line(surf, (150, 160, 190), tail, tip, 2)
        pygame.draw.circle(surf, (250, 210, 90), (int(tip[0]), int(tip[1])), 5)
    elif kind == "hour":
        pts = [(x + r + 6, y - 12), (x + r + 22, y - 12), (x + r + 14, y), (x + r + 22, y + 12),
               (x + r + 6, y + 12), (x + r + 14, y)]
        pygame.draw.polygon(surf, (250, 230, 180), pts)
        pygame.draw.polygon(surf, INK, pts, 2)
    elif kind == "focus":
        pygame.draw.circle(surf, (250, 220, 120), (int(x + r * 0.4), int(y - r * 0.1)), int(r * 0.35), 3)
