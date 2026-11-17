"""The Meadow hub as a chain of zones, one tower at the end of each.

    The Meadow -> (tower 1) -> its zone -> (tower 2) -> its zone -> ...

The order of towers is the *plan* (saved in meta["plan"]; the default is
consts.TOWER_ORDER, and the gallery can shuffle it or leave towers out).
The Meadow always comes first and ends at the plan's first tower. Get its
friend out and that tower's ground door opens onto the next zone, which is
the home zone of the next tower in the plan, with that tower at its end.
The friend you just rescued runs the zone's game, right at its start.

Every zone after the Meadow has the same shape, so every tower's window is
reached the same way (speed down a long slope, hop at the lip of a kicker):

    start ... host + sign ... locals and features (roots, pools, ice...)
          ... a rise, then the approach (a copy of the Leaning Tower's) ... tower
"""

import math

from .consts import TOWER_ORDER, TOWERS

# -- the Meadow (zone 0): fixed land, also used for the epilogue
WORLD = 3600                    # the epilogue meadow's width
KICK_START, LIP = 4150, 4380    # the Meadow's kicker ramp, up to its lip
TOWER_X = 4660                  # the first tower's wall
WINDOW = (4740, 178, 38)        # its window (x, y, radius)
APPROACH = 3600                 # where the Meadow's approach run starts (the copy starts here too)
ZONE_BODY = 4600                # each later zone: start .. approach
DOOR_GAP = 140                  # past a tower's wall, through its door, into the next zone
TAIL = 340                      # how far the land runs past the last tower you can reach


def ground_y(x):
    """The Meadow: gentle rolls, one big hill to race down, and a dip for the
    pond."""
    y = 470 - 34 * math.sin(x * 0.0042) - 22 * math.sin(x * 0.011 + 1.3)
    y -= 150 * math.exp(-((x - 1500) / 260.0) ** 2)            # the big hill
    y += 40 * math.exp(-((x - 2500) / 160.0) ** 2)             # the pond's hollow
    y -= 90 * math.exp(-((x - 3380) / 220.0) ** 2)             # the sunset rise, at the end
    return y


def meadow_hub(x):
    """The Meadow as a hub: on past the Stillwheel, a long run downhill, a
    kicker with a lip, a drop, and the first tower."""
    if x <= 3600:
        return ground_y(x)
    down = ground_y(3600) + (min(x, KICK_START) - 3600) * 0.12
    if x <= KICK_START:
        return down
    if x <= LIP:
        f = (x - KICK_START) / (LIP - KICK_START)
        return down - f * f * 60
    return down + 40


# -- zones: what each looks like, what's in it, who lives there, what game
# features: (kind, where along the zone's middle 0..1, size)
#   root     a big root across the path: slow, you bonk; hop it; fast, it flings you
#   rock     a mound to roll over
#   pool     water: you float, slower
#   ice      a sheet of ice: you slide (little grip, little push)
#   drift    deep snow: slows you right down
#   sand     soft sand: slows you a bit
#   spring   a big bouncy cap: roll onto it and it throws you up
#   crystal  a ringing crystal: it bounces you back unless you hop it
#   gust     wind that pushes you along
# locals: (colour, the shape it was, where along the zone 0..1, lines, sides now)
# newcomers: the same, for shapes that have only just started rolling (a few
#   sides, ka-thunking up and down the zone all day)
ZONES = {
    "meadow": {
        "name": "The Meadow", "sky": ((112, 196, 255), (214, 244, 255)),
        "hills": ((190, 238, 170), (150, 222, 130)), "far": "hills",
        "ground": ((130, 220, 104), (104, 200, 92), (150, 118, 84)), "plants": ("flower", "flower", "tuft"),
        "ambient": "moths", "over": None, "sun": (255, 236, 140), "roll": 1.0, "game": "rolloff",
        "features": (),
    },
    "wilds": {
        "name": "The Wilds", "sky": ((28, 118, 104), (168, 226, 150)),
        "hills": ((70, 150, 110), (50, 128, 84)), "far": "trunks",
        "ground": ((84, 176, 84), (54, 150, 74), (110, 80, 60)), "plants": ("fern", "bloom", "fern", "tuft"),
        "ambient": "fireflies", "over": "vines", "sun": None, "roll": 1.0, "game": "pinball",
        "features": (("root", 0.05, 50), ("rock", 0.12, 52), ("root", 0.2, 62), ("pool", 0.3, 170),
                     ("root", 0.4, 58), ("rock", 0.48, 60), ("root", 0.56, 66), ("pool", 0.65, 150),
                     ("rock", 0.72, 48), ("root", 0.82, 55)),
        "newcomers": (("C", "triangle", 0.3, ("Roots! Ka-THUNK! More roots! Ka-THUNK!",
                                                  "I've only got five sides. Everything's a bump.",
                                                  "Best day ever."), 5),),
        "locals": (("Y", "triangle", 0.1, ("Round enough is different out here. The roots make you bump.",
                                           "Every bump's a side, though. I had three when I came in.",
                                           "Now I've got eight. I stopped minding the roots."), 8),
                   ("B", "pentagon", 0.5, ("The Meadow's lovely. The Wilds make you rounder.",
                                           "You can't get round by sitting still. Ask the Stillwheel.",
                                           "Hop the big roots. Float the pools. Don't fight the bumps."), 16),
                   ("M", "square", 0.9, ("I float! Did you know squares float?",
                                         "Well. Seven-sided squares do.",
                                         "The tower's just past the last rise. Someone's stuck in it."), 7)),
    },
    "grove": {
        "name": "The Glow Grove", "sky": ((70, 44, 120), (236, 140, 190)),
        "hills": ((130, 80, 160), (100, 64, 140)), "far": "mushrooms",
        "ground": ((160, 220, 130), (100, 170, 110), (96, 70, 90)), "plants": ("glowshroom", "fern", "tuft"),
        "ambient": "spores", "over": None, "sun": None, "roll": 1.0, "game": "sporedrop",
        "features": (("spring", 0.08, 0), ("rock", 0.18, 44), ("spring", 0.3, 0), ("pool", 0.4, 140),
                     ("spring", 0.52, 0), ("root", 0.62, 52), ("spring", 0.74, 0), ("spring", 0.86, 0)),
        "newcomers": (("G", "square", 0.35, ("Every bounce, I land on a corner. Every single time.",
                                                "Six sides now, though! Ka-thunk!",
                                                "The caps don't mind. They're very forgiving."), 6),),
        "locals": (("M", "triangle", 0.15, ("The glow comes from the mushrooms. They hum, if you listen.",
                                            "I bounced here from the Meadow. Took four days. Best four days.",
                                            "Land softly. Then roll."), 9),
                   ("C", "square", 0.55, ("Hop on a big cap! It throws you right up.",
                                          "Sides grow faster when you bounce. I'm sure of it.",
                                          "Well. Fairly sure."), 12),
                   ("Y", "pentagon", 0.9, ("Someone in the Toadstool keeps bouncing back up.",
                                           "I'd help, but I'd just bounce too.",
                                           "You look like a good lander."), 15)),
    },
    "frost": {
        "name": "The Frost", "sky": ((140, 190, 246), (238, 246, 255)),
        "hills": ((214, 230, 250), (184, 210, 240)), "far": "peaks",
        "ground": ((252, 254, 255), (214, 230, 250), (150, 170, 204)), "plants": ("pine", "icecrystal", "pine"),
        "ambient": "snow", "over": None, "sun": (255, 250, 220), "roll": 1.0, "game": "curl",
        "features": (("ice", 0.06, 420), ("rock", 0.2, 46), ("drift", 0.3, 260), ("ice", 0.44, 520),
                     ("rock", 0.58, 54), ("drift", 0.68, 220), ("ice", 0.8, 380)),
        "newcomers": (("Y", "triangle", 0.35, ("Ice is hard when you've got corners.",
                                                  "I slide, then I thunk, then I slide.",
                                                  "Five sides. Working on six."), 5),),
        "locals": (("B", "hexagon", 0.15, ("Brr! Ice is fast. Very fast. Too fast.",
                                           "Don't push on the ice. Just lean.",
                                           "I slid here from over there. I meant to stop there."), 11),
                   ("C", "triangle", 0.55, ("Snowdrifts slow you right down. Soft landing, though.",
                                            "I used to be a triangle. Now I'm a snowball. Mostly.",
                                            "Roll me a snowman sometime?"), 8),
                   ("R", "square", 0.92, ("There's a pentagon frozen in the Spire. Mid-roll!",
                                          "Imagine being stuck halfway through the best bit.",
                                          "Go and let it finish."), 13)),
    },
    "dunes": {
        "name": "The Dunes", "sky": ((255, 160, 96), (255, 236, 176)),
        "hills": ((246, 204, 140), (236, 184, 116)), "far": "mesas",
        "ground": ((254, 230, 168), (238, 200, 136), (200, 150, 100)), "plants": ("cactus", "drygrass", "drygrass"),
        "ambient": "dust", "over": None, "sun": (255, 246, 200), "roll": 1.8, "game": "duneputt",
        "features": (("sand", 0.08, 360), ("rock", 0.22, 50), ("pool", 0.36, 180), ("sand", 0.5, 420),
                     ("rock", 0.64, 56), ("sand", 0.78, 300)),
        "newcomers": (("B", "square", 0.35, ("Sand gets in my corners. All six of them.",
                                                "Ka-thunk, ka-thunk. Ka-thunk.",
                                                "The big dunes round you off quick, they say."), 6),),
        "locals": (("Y", "square", 0.15, ("The dunes are the best hills anywhere. Big, long, smooth.",
                                          "Sand slows you, though. Keep rolling.",
                                          "Don't stop on a dune top. It's hot."), 14),
                   ("R", "triangle", 0.55, ("The oasis is lovely. Float a while.",
                                            "I used to point at things. Now I just roll past them.",
                                            "Much better."), 10),
                   ("G", "pentagon", 0.92, ("The Sundial's pointer is a triangle. Been there for ages.",
                                            "It tells the time. I think it'd rather tell a story.",
                                            "Go and ask it."), 16)),
    },
    "caves": {
        "name": "The Glimmer Caves", "sky": ((26, 18, 56), (84, 56, 130)),
        "hills": ((64, 46, 104), (46, 36, 84)), "far": "stalagmites",
        "ground": ((176, 156, 220), (104, 84, 146), (66, 54, 98)), "plants": ("crystal", "glowshroom", "crystal"),
        "ambient": "sparkles", "over": "stalactites", "sun": None, "roll": 1.0, "game": "glimmerpop",
        "features": (("crystal", 0.08, 56), ("pool", 0.2, 150), ("crystal", 0.32, 60), ("rock", 0.42, 48),
                     ("crystal", 0.55, 54), ("pool", 0.66, 140), ("crystal", 0.8, 62)),
        "newcomers": (("Y", "pentagon", 0.35, ("Ka-THUNK! Ooh, the crystals rang!",
                                                  "I'm loud. Corners are loud.",
                                                  "Seven sides. Nearly quiet."), 7),),
        "locals": (("M", "diamond", 0.15, ("Careful, the crystals bounce you back! Hop over them.",
                                           "Everything glows down here. Even me, a bit.",
                                           "Especially me."), 12),
                   ("C", "pentagon", 0.55, ("Listen! The crystals ring when you bump them.",
                                            "I bumped them all. It was a song.", "A bumpy song."), 18),
                   ("B", "triangle", 0.92, ("Deep in the cave there's a tower made of crystal.",
                                            "There's someone in it, focusing all the light.",
                                            "Seems like hard work."), 9)),
    },
    "coast": {
        "name": "The Coast", "sky": ((96, 136, 226), (255, 198, 160)),
        "hills": ((110, 176, 232), (86, 150, 214)), "far": "sea",
        "ground": ((252, 236, 186), (234, 206, 150), (190, 156, 110)), "plants": ("seagrass", "shell", "seagrass"),
        "ambient": "gulls", "over": None, "sun": (255, 226, 170), "roll": 1.0, "game": "beachbowl",
        "features": (("rock", 0.08, 48), ("pool", 0.2, 160), ("sand", 0.34, 300), ("rock", 0.48, 56),
                     ("pool", 0.6, 170), ("rock", 0.74, 50), ("sand", 0.84, 260)),
        "newcomers": (("M", "triangle", 0.35, ("The waves roll. I'm learning from them.",
                                                  "Ka... thunk. The sea never thunks.",
                                                  "Five sides. The sea has none. Goals."), 5),),
        "locals": (("C", "hexagon", 0.15, ("Sand between my sides! Lovely.",
                                           "The tide pools are warm. Float in one.",
                                           "The sea's the flattest roundest thing there is."), 20),
                   ("Y", "square", 0.55, ("Shells are just shapes that curled up.",
                                          "I curled up once. Then I unrolled. Then I rolled.",
                                          "It's a process."), 12),
                   ("R", "triangle", 0.92, ("The Lighthouse shines every night.",
                                            "Nobody's ever come down from it. Not once.",
                                            "Maybe nobody ever asked."), 9)),
    },
    "heights": {
        "name": "The Windy Heights", "sky": ((100, 170, 250), (226, 244, 255)),
        "hills": ((176, 224, 170), (146, 204, 150)), "far": "islands",
        "ground": ((160, 226, 120), (116, 196, 104), (136, 112, 90)), "plants": ("windflower", "tuft", "flower"),
        "ambient": "petals", "over": None, "sun": (255, 240, 170), "roll": 1.4, "game": "skyball",
        "features": (("gust", 0.06, 500), ("spring", 0.22, 0), ("rock", 0.32, 50), ("gust", 0.42, 600),
                     ("spring", 0.6, 0), ("root", 0.7, 54), ("gust", 0.8, 420)),
        "newcomers": (("R", "square", 0.35, ("The wind tips me over, a corner at a time.",
                                                  "Ka-thunk! That's rolling, right? Right?",
                                                  "Six sides! Wheee-thunk!"), 6),),
        "locals": (("G", "pentagon", 0.15, ("The wind up here pushes you along. Wheee!",
                                            "Lean into it. Or don't. It's fun either way.",
                                            "Hold onto your sides."), 15),
                   ("M", "triangle", 0.55, ("The springs up here throw you right into the sky.",
                                            "I saw the whole world once. Then I came down.",
                                            "It was round. Mostly."), 10),
                   ("B", "square", 0.92, ("The Windmill's kite wants to fly free.",
                                          "Funny. A kite that wants to roll.",
                                          "Everybody wants what they haven't tried yet."), 11)),
    },
}
DEFAULT_PLAN = TOWER_ORDER
# Every zone has its own game, right at its start (see arcade.py and each game's module):
GAMES = {
    "rolloff": ("Roll-Off", "rolloff", "RollOffScreen"),
    "pinball": ("Side Show", "pinball", "PinballScreen"),
    "sporedrop": ("Spore Drop", "sporedrop", "SporeDropScreen"),
    "curl": ("Curl", "curl", "CurlScreen"),
    "duneputt": ("Dune Putt", "duneputt", "DunePuttScreen"),
    "glimmerpop": ("Glimmer Pop", "glimmerpop", "GlimmerPopScreen"),
    "beachbowl": ("Beach Bowl", "beachbowl", "BeachBowlScreen"),
    "skyball": ("Sky Ball", "skyball", "SkyBallScreen"),
}


def plan_of(meta_data):
    """The order of towers in this save (valid ids only; never empty)."""
    plan = [t for t in meta_data.get("plan", DEFAULT_PLAN) if t in TOWERS]
    return plan or list(DEFAULT_PLAN)


# -- layout

class Zone:
    """One stretch of the hub: where it starts, its tower, its terrain."""

    def __init__(self, index, kind, tower, start, base):
        self.index, self.kind, self.tower = index, kind, tower
        self.spec = ZONES[kind]
        self.start = start
        self.base = base                      # ground height where it starts
        self.h0 = APPROACH if index == 0 else start + ZONE_BODY
        self.shift = self.h0 - APPROACH
        lo, hi = start + 900, self.h0 - 500
        self.features = []
        for kind_, frac, size in self.spec.get("features", ()) if index else ():
            self.features.append((kind_, lo + (hi - lo) * frac, size))
        self.locals = [(c, was, lo + (hi - lo) * frac, lines, n)
                       for c, was, frac, lines, n in (self.spec.get("locals", ()) if index else ())]
        # shapes that have only just started rolling: few sides, ka-thunking up and down
        self.newcomers = [(c, was, lo + (hi - lo) * frac, lines, n)
                          for c, was, frac, lines, n in (self.spec.get("newcomers", ()) if index else ())]
        self.off = 0.0 if index == 0 else self._raw(self.h0) - meadow_hub(APPROACH)
        self.kick = KICK_START + self.shift
        self.lip = LIP + self.shift
        self.wall = TOWER_X + self.shift
        self.window = (WINDOW[0] + self.shift, WINDOW[1] + self.off, WINDOW[2])
        self.end = self.wall + DOOR_GAP
        self.host_x = start + 450 if index else 620

    # terrain
    def _raw(self, x):
        """The zone's land without pools: rolls (bigger in the dunes), bumps
        for roots, rocks, crystals and caps, a steady climb, and a rise
        before the approach."""
        u = x - self.start
        ramp_in = min(1.0, max(0.0, u / 1200.0))
        amp = self.spec.get("roll", 1.0)
        y = self.base - 14 * math.sin(u * 0.004) - ramp_in * amp * (40 * math.sin(u * 0.0023) +
                                                                    14 * math.sin(u * 0.011))
        for kind, fx, size in self.features:
            if kind in ("root", "rock", "crystal"):
                w = {"root": 26, "rock": 40, "crystal": 22}[kind]
                y -= size * math.exp(-((x - fx) / w) ** 2)
            elif kind == "spring":
                y -= 18 * math.exp(-((x - fx) / 30.0) ** 2)
            elif kind == "drift":
                y -= 22 * math.exp(-((x - fx - size / 2) / (size / 2.2)) ** 2)
        y -= 90 * math.exp(-((x - (self.h0 - 220)) / 220.0) ** 2)
        k = max(0.0, min(1.0, u / ZONE_BODY))
        climb = self.base - meadow_hub(APPROACH) + 5
        y -= climb * k * k * (3 - 2 * k)
        return y

    def pool_at(self, x):
        for kind, fx, size in self.features:
            if kind == "pool" and abs(x - fx) <= size:
                return fx, size, max(self._raw(fx - size), self._raw(fx + size)) + 6
        return None

    def region(self, x):
        """The kind of ground under x ('ice', 'drift', 'sand', 'gust') or None."""
        for kind, fx, size in self.features:
            if kind in ("ice", "drift", "sand", "gust") and fx <= x <= fx + size:
                return kind
        return None

    def ground(self, x):
        if self.index == 0:
            return meadow_hub(x)
        if x >= self.h0:
            return meadow_hub(x - self.shift) + self.off
        y = self._raw(x)
        pool = self.pool_at(x)
        if pool is not None:                                       # the water's surface: you float
            c, hw, level = pool
            edge = min(1.0, (hw - abs(x - c)) / 40.0)
            y = y + (level - y) * (edge * edge * (3 - 2 * edge))
        return y


class World:
    """The zones you can reach, given the plan and who you've rescued."""

    def __init__(self, plan, rescued, open_all=False):
        self.plan = list(plan)
        self.rescued = set(rescued)
        self.open_all = open_all        # every zone open (a setting): every ground door open too
        self.zones = [Zone(0, "meadow", self.plan[0], 0.0, 470.0)]
        for k in range(1, len(self.plan)):
            if self.plan[k - 1] not in self.rescued and not open_all:
                break
            prev = self.zones[-1]
            start = prev.end
            base = meadow_hub(start - prev.shift) + prev.off
            self.zones.append(Zone(k, TOWERS[self.plan[k]]["zone"], self.plan[k], start, base))
        last = self.zones[-1]
        self.width = last.wall + TAIL
        if last.tower in self.rescued or open_all:      # a little land past the last door
            self.width = last.end + 900

    def zone_at(self, x):
        for z in reversed(self.zones):
            if x >= z.start:
                return z
        return self.zones[0]

    def ground(self, x):
        z = self.zone_at(x)
        if x > z.end and z.index == len(self.zones) - 1:   # past the last door: flat, for a while
            return z.ground(z.end)
        return z.ground(x)

    def next_zone_after(self, tid):
        """The zone that opens once `tid`'s friend is out (None if it's the last)."""
        if tid not in self.plan:
            return None
        k = self.plan.index(tid)
        if k + 1 >= len(self.plan):
            return None
        return ZONES[TOWERS[self.plan[k + 1]]["zone"]]

    def home_of(self, tid):
        """Where a rescued friend lives: hosting the game at the start of the
        zone its rescue opened (or by its own tower, after the last)."""
        if tid in self.plan:
            k = self.plan.index(tid)
            if k + 1 < len(self.zones):
                return self.zones[k + 1].host_x
            z = next((z for z in self.zones if z.tower == tid), None)
            if z is not None:
                return z.wall - 330
        return TOWER_X - 260


def slope(x, land):
    return (land(x + 2) - land(x - 2)) / 4.0


# -- roundness: how many sides you (and your friends) have grown
ROUND_ENOUGH = 10               # what the Round Door makes you: round enough to roll
FRIEND_START, FRIEND_GROWTH, FRIEND_MOST = 10, 2, 26


def rescued_in_plan(meta_data, rescued=None):
    plan = plan_of(meta_data)
    rescued = set(meta_data.get("friends", []) if rescued is None else rescued)
    return plan, [t for t in plan if t in rescued]


DEV_SIDES = None                # testing mode: pretend you have this many sides (0: round)


def your_sides(meta_data, rescued=None):
    """How many sides you have now (0: perfectly round). Every friend you get
    out of a tower rounds you out a little more; once everyone in your world
    is out, you're round, all the way round."""
    if DEV_SIDES is not None:
        return DEV_SIDES
    plan, done = rescued_in_plan(meta_data, rescued)
    k = len(done)
    if plan and k >= len(plan):
        return 0
    grown = ROUND_ENOUGH * (1 + 3 * (k / max(1, len(plan))) ** 1.3)     # about 10 -> 40 over your towers
    return max(ROUND_ENOUGH + 2 * k, int(round(grown)))


def friend_sides(tid, meta_data, rescued=None):
    """A friend you got out lands with about ten sides (every bump on the
    way down is one), and grows more with every friend you get out after it."""
    plan, done = rescued_in_plan(meta_data, rescued)
    base = meta_data.get("sides", {}).get(tid, FRIEND_START)
    later = len(done) - done.index(tid) - 1 if tid in done else 0
    return min(FRIEND_MOST, base + FRIEND_GROWTH * later)


def shape_of(sides):
    """A sides count as a shape to draw: 0 is a circle."""
    return "circle" if not sides else sides
