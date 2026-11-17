"""Constants and lookup tables for Prism Delve.

Everything here is plain data so the rules engine, the solver and the UI
all agree on the same numbers.
"""

GRID_W = 9
GRID_H = 9
BEATS = 4                      # beats per turn (length of the planning timeline)
PLAYER_START = (4, 4)          # the middle: the Set comes at you from every side
PLAYER_HP = 14
MAX_SHIELD = 4
START_CHARGES = 3              # palette charges at the start of every fight
START_CAP = 5                  # starting cap per colour
BEAM_LEN = 8                   # rays run until a wall or the edge (the board is 9 wide)
SLANT_LEN = 8
LOB_DIST = 3

COLORS = ("R", "G", "B", "Y", "C", "M")
PRIMARIES = ("R", "G", "B")
RAINBOW = ("R", "Y", "G", "C", "B", "M")    # hue order, for anything that cycles colour

# Which primaries each colour consumes (a mix costs one of each component).
COMPONENTS = {
    "R": ("R",),
    "G": ("G",),
    "B": ("B",),
    "Y": ("R", "G"),
    "C": ("G", "B"),
    "M": ("R", "B"),
}

# Hitting an enemy with the opposite colour doubles damage; the same colour
# is absorbed (no effect at all).
OPPOSITE = {"R": "C", "C": "R", "G": "M", "M": "G", "B": "Y", "Y": "B"}

COLOR_NAMES = {
    "R": "Red", "G": "Green", "B": "Blue",
    "Y": "Yellow", "C": "Cyan", "M": "Magenta",
}
COLOR_RGB = {
    "R": (255, 72, 96), "G": (40, 206, 110), "B": (60, 118, 255),
    "Y": (255, 206, 36), "C": (24, 214, 232), "M": (226, 70, 226),
}
COLOR_EFFECT = {
    "R": "3 damage",
    "G": "2 dmg, push 1 (collision +dmg)",
    "B": "1 dmg, stun 2 beats, +1 shield",
    "Y": "1 dmg, burn 3 turns, push 1",
    "C": "2 dmg, stun 1, swap places with first hit",
    "M": "4 dmg, splashes 1 to same-shape neighbours",
}

# A cast has three parts:
#   PATTERN  where the light goes. Fixed geometry anchored on you, like the way
#            a game piece moves. Each pattern can be used once per turn.
#   SHAPE    what the light is cut to fit. It only touches enemies of that
#            shape and passes straight through everything else (the Sorter's
#            one rule: a shape only fits its own door).
#   COLOUR   what it does when it lands.
# Landing on several shapes at once is rewarded (see rules.player_cast).
SHAPES = ("triangle", "square", "circle")
SHAPE_NAMES = {"triangle": "Triangle", "square": "Square", "circle": "Circle"}
SHAPE_PLURAL = {"triangle": "triangles", "square": "squares", "circle": "circles"}

ORTH = ((0, -1), (1, 0), (0, 1), (-1, 0))
DIAG = ((1, -1), (1, 1), (-1, 1), (-1, -1))
KNIGHT = ((1, -2), (2, -1), (2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2))
RING = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))

PATTERNS = {
    "beam": {"name": "Beam", "aim": "orth",
             "desc": "A straight line up, down, left or right, until a wall."},
    "slant": {"name": "Slant", "aim": "diag",
              "desc": "A diagonal line, until a wall."},
    "halo": {"name": "Halo", "aim": "none",
             "desc": "All 8 tiles around you."},
    "leap": {"name": "Leap", "aim": "none",
             "desc": "The 8 tiles an L-step away (2 then 1), straight over anything."},
    "lob": {"name": "Lob", "aim": "far",
            "desc": "A plus that lands %d tiles away, straight up, down, left or right." % LOB_DIST},
}
PATTERN_ORDER = ("beam", "slant", "halo", "leap", "lob")
START_PATTERNS = ("beam", "slant")     # a triangle is all points: it fires lines
# (each new form brings a pattern of its own: see FORMS "gift")

# Finishing a fight quickly is the goal. Par is the fewest turns the solver
# found; each grade pays extra glint, and a clean sort offers a 4th reward.
GRADES = (("Clean", 1, 8), ("Tidy", 2, 4))        # (name, turns over par allowed, glint)

# Player modifiers (relics change these).
DEFAULT_MODS = {
    "red_bonus": 0,        # extra damage from red casts
    "collision_bonus": 0,  # extra collision damage on pushes
    "blue_shield": 1,      # shield gained per blue cast
    "group_bonus": 0,      # extra damage when one cast fits 2+ shapes
    "regen": 1,            # palette charges regained per colour per turn
    "pierce": 0,           # walls Beam and Slant pass through
    "burn_bonus": 0,       # extra burn turns
}

# Relics are "facets": faces you cut into yourself. You are a prism, so a new
# face changes how light leaves you. Ids are stable (saves and tests use them).
# Every facet is drawn as the same cut gem: tinted only when it is about that
# colour ("tint"), prismatic otherwise. Never a shape: shapes mean enemies.
# (Names never say "Facet": the UI already calls them facets.)
RELICS = {
    "crimson_lens": {"name": "Sharp Red", "desc": "Red casts deal +1 damage.",
                     "mods": {"red_bonus": 1}, "tint": "R"},
    "verdant_root": {"name": "Hard Corner", "desc": "Push collisions deal +2 damage.",
                     "mods": {"collision_bonus": 2}, "tint": "G"},
    "azure_plate": {"name": "Blue Plate", "desc": "Blue casts give +1 extra shield.",
                    "mods": {"blue_shield": 1}, "tint": "B"},
    "prism_shard": {"name": "Spare Angle", "desc": "+1 damage whenever a cast fits 2+ shapes.",
                    "mods": {"group_bonus": 1}, "tint": None},
    "echo_stone": {"name": "Open Face", "desc": "Regain +1 of every colour each turn.",
                   "mods": {"regen": 1}, "tint": None},
    "long_reach": {"name": "Long Edge", "desc": "Beam and Slant pass through one wall.",
                   "mods": {"pierce": 1}, "tint": None},
    "ember_core": {"name": "Afterglow", "desc": "Burn lasts 2 turns longer.",
                   "mods": {"burn_bonus": 2}, "tint": "Y"},
}

CURRENCY = "glint"        # scraps of light the Set leaves behind (stored as run.gold)

# ------------------------------------------------------------------ story
# You climb the Sorter one floor per act, gaining a side at each Keeper.
# FORMS[act] is the shape you are during that act; FORMS[ACTS + 1] is the end.
FORMS = {
    1: {"shape": "triangle", "name": "Triangle", "sides": 3, "perk": "",
        "max_hp": 0, "cap": 0, "gift": None},
    2: {"shape": "square", "name": "Square", "sides": 4,
        "perk": "Four sides to stand on: you can hit all around you. +3 max HP.",
        "max_hp": 3, "cap": 0, "gift": "halo"},
    3: {"shape": "pentagon", "name": "Pentagon", "sides": 5,
        "perk": "Almost round: your light starts to arc. +1 cap on every colour.",
        "max_hp": 0, "cap": 1, "gift": "lob"},
    4: {"shape": "circle", "name": "Circle", "sides": 0, "perk": "",
        "max_hp": 0, "cap": 0, "gift": None},
}

FLOORS = {
    1: {"name": "Floor of Three", "door": "square", "door_name": "Four-Door",
        "blurb": "The bottom of the Sorter, where every shape is first cut.",
        "sky": ((255, 128, 102), (255, 204, 92)), "tiles": ((255, 241, 222), (255, 230, 204)),
        "wall": (226, 98, 80), "accent": (236, 84, 70)},
    2: {"name": "Floor of Four", "door": "pentagon", "door_name": "Five-Door",
        "blurb": "Flat, tidy rooms. The Set here likes things square.",
        "sky": ((38, 190, 178), (170, 232, 120)), "tiles": ((230, 252, 240), (214, 244, 228)),
        "wall": (28, 140, 128), "accent": (18, 150, 130)},
    3: {"name": "Floor of Five", "door": "circle", "door_name": "Round Door",
        "blurb": "Almost round up here. The Round Door is close.",
        "sky": ((120, 84, 232), (244, 104, 184)), "tiles": ((246, 234, 255), (236, 222, 252)),
        "wall": (112, 72, 190), "accent": (140, 70, 220)},
}

# Towers out in the Meadow (the hub, after you've rolled out once). Each has
# someone at a window who asked to get out. You go in as a circle, you reach
# them, and the door is theirs to take. Nobody else has to leave. Each tower
# stands at the end of its own zone (see world.py), is painted in
# towers_art.py, and has a twist: special tiles in its floors (see TWISTS).
#
# A tower's fields: name, blurb, door_name, zone, sky/tiles/wall/accent
# (palette), act (enemy pool), depth (rooms before its Keeper), boss (a Keeper
# in enemies.KINDS, with lines in banter.KEEPER), tier (how much tougher than
# the Sorter), twists, friend (who asked: its old shape, colour, what it
# shouts from the window, what it says after), plea (its words on the intro
# card), intro (three cards: words, scene, stage) and after (the open door).


def _tower(name, blurb, zone, palette, boss, twists, friend, plea, intro, after, tier=2, depth=5):
    sky, tiles, wall, accent = palette
    return {"name": name, "door": "circle", "door_name": "its window", "blurb": blurb, "zone": zone,
            "sky": sky, "tiles": tiles, "wall": wall, "accent": accent, "act": 3, "depth": depth,
            "boss": boss, "tier": tier, "twists": twists,
            "portals": 2 if "holes" in twists else 0, "friend": friend, "plea": plea,
            "intro": intro, "after": after}


def _friend(was, color, ask, lines):
    return {"was": was, "color": color, "ask": ask, "lines": lines}


TOWERS = {
    "leaning": _tower(
        "The Leaning Tower", "It leans. So does everyone inside it.", "meadow",
        (((70, 180, 236), (255, 186, 120)), ((236, 246, 255), (220, 236, 250)), (64, 120, 186), (40, 110, 200)),
        "latch", (),
        _friend("hexagon", "C", "Hey! Up here! I want to roll too!",
                ("You came! I waved for ages.",
                 "Everyone in there thought I'd fall. I thought so too, a bit.",
                 "Rolling is SO much better than leaning.")),
        "Everyone in here leans. I want to ROLL! Come up and get me?",
        (("The Leaning Tower leans, and so does everyone in it. From its one high "
          "window, a hexagon has been waving at the Meadow for ages.", "_asker", None),
         ("In here you're a sphere. No more clicking tile to tile: you ROLL until "
          "something stops you. Roll into a shape: bump! 2 damage and a shove.", "_sphere", None),
         ("The window is kept by the Latch. It isn't mean, just worried: it thinks "
          "the hexagon will fall. Show it that rolling isn't falling.", "_guardian", None)),
        "The Latch holds the ground door open now. Through the tower: what's next.",
        tier=1, depth=4),
    "hollow": _tower(
        "The Hollow Tree", "Hollow all the way up, and full of knotholes.", "wilds",
        (((24, 150, 120), (214, 240, 110)), ((246, 236, 206), (234, 220, 184)), (132, 88, 52), (40, 150, 80)),
        "knot", ("holes",),
        _friend("square", "G", "Help! I'm stuck in the knothole!",
                ("You got me out! Corners catch, you know.",
                 "I climbed up to see the view. Then I couldn't climb down.",
                 "Moss grew on my corners while I waited. It helped, a bit.",
                 "YOU helped more.")),
        "I climbed in to see the view and my corners caught. I'm STUCK!",
        (("Deep in the Wilds stands the Hollow Tree. A square climbed up inside it to see "
          "the view, and got stuck in a knothole. Corners catch.", "_asker", None),
         ("The tree is full of knotholes. Roll into one: you drop through and roll out of "
          "its twin, still going. Only round things fall in. The Set just step over.", "_twist", None),
         ("The Knot holds the whole tree together, and it thinks everything should stay "
          "tied where it grew. Even a stuck square. Untie it.", "_guardian", None)),
        "The Knot loosened. The Hollow Tree creaks happily now."),
    "toadstool": _tower(
        "The Toadstool", "A mushroom as tall as a tower. Everything in it bounces.", "grove",
        (((250, 130, 170), (255, 222, 190)), ((255, 244, 236), (250, 230, 222)), (210, 80, 100), (220, 80, 120)),
        "cap", ("springs",),
        _friend("diamond", "Y", "Help! I keep bouncing back up!",
                ("Down at last! And it's so... still.",
                 "Up there everything bounces. You never land anywhere.",
                 "Rolling's better. You choose where you stop.")),
        "Every time I try to come down, a cap bounces me right back up here!",
        (("In the Glow Grove stands the Toadstool, a mushroom as tall as a tower. A diamond at "
          "its window keeps trying to come down. It keeps bouncing back up.", "_asker", None),
         ("Its floors are dotted with springy caps. Roll onto one and it flings you right over "
          "the next tile (a shape, a wall, anything) and on you roll. Get behind them.", "_twist", None),
         ("The Cap keeps everything bouncing. It thinks coming down is dangerous. Show it that "
          "landing is lovely.", "_guardian", None)),
        "The Cap stopped bouncing things back. The Toadstool's door is open."),
    "icicle": _tower(
        "The Icicle Spire", "Frozen solid, top to bottom. Snow on every floor.", "frost",
        (((150, 200, 250), (235, 245, 255)), ((240, 248, 255), (224, 238, 252)), (120, 170, 220), (70, 140, 220)),
        "rime", ("snow",),
        _friend("pentagon", "B", "I'm frozen! Mid-roll!",
                ("...and ROLL! Oh, that's better. I've waited ages to finish that.",
                 "Ice is pretty. Melting is prettier.",
                 "Snow is just rain that's been through something, you know.")),
        "I was halfway through a roll when everything froze. I'd love to finish it!",
        (("High in the Frost stands the Icicle Spire. A pentagon in its window froze halfway "
          "through a roll, and has been stuck that way ever since.", "_asker", None),
         ("Snow lies on its floors. Roll through it and it packs onto you: every tile of snow adds "
          "+1 to your bump. Take the long way round, and hit hard.", "_twist", None),
         ("The Rime keeps everything exactly as it froze. It thinks change is just melting. "
          "Show it some.", "_guardian", None)),
        "The Rime let go a little. It's dripping, happily."),
    "sundial": _tower(
        "The Sundial", "It tells the time. Its pointer would like to tell it something else.", "dunes",
        (((255, 170, 90), (255, 236, 170)), ((255, 244, 220), (246, 230, 196)), (200, 150, 90), (230, 140, 60)),
        "hour", ("pools",),
        _friend("triangle", "Y", "I've been the pointer for SO long!",
                ("Do you know how long I've been a pointer? Exactly. I told everyone.",
                 "Turns out the sun comes up whether I point at it or not.",
                 "Time goes on. So do I, now.")),
        "I'm the pointer. I stand still so the shadow tells the time. I'd like to go somewhere!",
        (("Out in the Dunes stands the Sundial. A triangle has been its pointer for as long as "
          "anyone can tell, which is exactly as long as it's been pointing.", "_asker", None),
         ("Little oases of colour dot its floors. Roll through one and you're dyed: your bump lands "
          "as that colour. Red hits hard, green shoves twice, blue stuns.", "_twist", None),
         ("The Hourglass thinks that if the pointer leaves, time will stop. Time won't. "
          "Show it.", "_guardian", None)),
        "The Hourglass turned itself over. Time's still going. It seems relieved."),
    "lens": _tower(
        "The Lens", "A tower of crystal. Light goes in one end and bends.", "caves",
        (((90, 60, 160), (200, 150, 240)), ((240, 234, 255), (228, 220, 250)), (140, 110, 220), (160, 110, 240)),
        "focus", ("bends",),
        _friend("diamond", "M", "Let me out! I want to SCATTER!",
                ("Wheee! Look, rainbows everywhere!",
                 "One straight beam is so... straight.",
                 "You're a prism too! We should scatter together sometime.")),
        "They use me to focus all the light into one beam. I want to scatter it. Every colour!",
        (("Under the Glimmer Caves grows the Lens, a tower of crystal. A diamond sits in its "
          "heart, focusing all the light into one straight beam.", "_asker", None),
         ("Crystal facets are set into its floors. They turn you a quarter turn, and they bend light "
          "too: every Beam, yours and theirs, turns at a facet.", "_twist", None),
         ("The Focus thinks light should go in one straight line, always. Show it what "
          "scattering looks like.", "_guardian", None)),
        "The Focus loosened up. There are little rainbows all over the cave now."),
    "lighthouse": _tower(
        "The Lighthouse", "It shines all night for ships that never come.", "coast",
        (((60, 90, 170), (250, 180, 140)), ((240, 246, 252), (224, 234, 246)), (210, 80, 80), (60, 120, 200)),
        "beacon", ("holes", "currents"),
        _friend("pentagon", "R", "Hello? Is anyone out there?",
                ("The ground! It's so... grounded.",
                 "The Beacon keeps the lamp going now. It likes that bit.",
                 "I can see the sea from down here too. It's even bigger.")),
        "I keep the lamp lit. I've never once been down to the ground. Is it nice?",
        (("On the edge of the Coast stands the Lighthouse. A pentagon has kept its lamp lit for "
          "years, and has never once been down to the ground.", "_asker", None),
         ("Blowholes run through the rock: roll into one, out of its twin. And the tide runs over "
          "the floors: end a beat on a current and it carries you. Or them.", "_twist", None),
         ("The Beacon thinks the lamp needs its keeper, always. It can keep the lamp itself. "
          "Show it.", "_guardian", None)),
        "The Beacon keeps the lamp itself now. It's very proud.", depth=6),
    "windmill": _tower(
        "The Windmill", "Turning and turning, and never going anywhere.", "heights",
        (((110, 180, 250), (230, 245, 255)), ((250, 248, 240), (236, 232, 220)), (150, 110, 80), (90, 150, 220)),
        "vane", ("gusts", "springs"),
        _friend("diamond", "G", "Up here! I'm the weather kite!",
                ("Free as the wind! Well. Freer.",
                 "Turns out I can tell which way the wind blows from down here.",
                 "Want to race down the big hill?")),
        "They keep me at the top to show which way the wind blows. I'd like to blow somewhere!",
        (("Up on the Windy Heights turns the Windmill. A diamond is kept at its window to show "
          "which way the wind blows.", "_asker", None),
         ("Gusts blow across its floors: end a beat on one and you're blown two tiles. So are they. "
          "And springy caps fling you over whatever's in the way.", "_twist", None),
         ("The Vane thinks everything should turn with the wind. Show it you can go your own "
          "way.", "_guardian", None)),
        "The Vane is spinning happily on its own. The door is open.", depth=6),
}
TOWER_ORDER = ("leaning", "hollow", "toadstool", "icicle", "sundial", "lens", "lighthouse", "windmill")

# The tiles a tower can put in its floors (rules.roll_info and rules.flow).
# Only round things notice most of them (corners catch, so the Set walk over,
# and light passes over) except currents and gusts, which carry everyone, and
# facets, which bend Beams (yours and theirs) as well as rolls.
TWISTS = {
    "holes": {"name": "Knotholes", "short": "in one hole, out of its twin",
              "tip": "Roll into a hole and you come out of the one that glows the same colour, still "
                     "rolling. The Set just step over them."},
    "springs": {"name": "Springy caps", "short": "fling you over the next tile",
                "tip": "Roll onto a cap and it flings you over the next tile (a shape, a wall, anything) "
                       "and you land two on, still rolling. Get behind them."},
    "snow": {"name": "Snow", "short": "+1 bump for every tile of it you roll through",
             "tip": "Roll through snow and it packs onto you: every tile of it adds +1 to your bump. "
                    "Take the long way round and hit hard."},
    "pools": {"name": "Colour pools", "short": "dye you: your bump lands as that colour",
              "tip": "Roll through a pool and you're dyed its colour: your bump hits as that colour "
                     "(red hits hard, green shoves twice, blue stuns; opposite colour doubles it)."},
    "bends": {"name": "Crystal facets", "short": "turn rolls and Beams a quarter turn",
              "tip": "Facets turn you a quarter turn, the way they slant. They bend light too: "
                     "Beams, yours and theirs, turn at a facet. Read the board!"},
    "currents": {"name": "Currents", "short": "carry whoever ends a beat on them a tile",
                 "tip": "Tide runs along the arrows: anyone who ends a beat on a current (you or "
                        "them) is carried a tile along it. Drift them into trouble."},
    "gusts": {"name": "Gusts", "short": "blow whoever ends a beat on them two tiles",
              "tip": "The wind blows along the arrows: anyone who ends a beat on a gust (you or "
                     "them) is blown two tiles along it, as far as it's clear."},
}

# Some towers call a twist something else (the sea's holes aren't knotholes).
TWIST_NAMES = {("lighthouse", "holes"): "Blowholes"}


def twist_name(twist, tower=None):
    return TWIST_NAMES.get((tower, twist), TWISTS[twist]["name"])
