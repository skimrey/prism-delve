"""Constants and lookup tables for Prism Delve.

Everything here is plain data so the rules engine, the solver and the UI
all agree on the same numbers.
"""

GRID_W = 9
GRID_H = 9
BEATS = 4                      # beats per turn (length of the planning timeline)
PLAYER_START = (4, 8)
PLAYER_HP = 14
MAX_SHIELD = 4
START_CHARGES = 3              # palette charges at the start of every fight
START_CAP = 5                  # starting cap per colour
SHAPE_RANGE = 3
MAX_CHAIN = 5

COLORS = ("R", "G", "B", "Y", "C", "M")
PRIMARIES = ("R", "G", "B")

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
    "R": (232, 72, 72), "G": (84, 205, 104), "B": (84, 128, 238),
    "Y": (240, 214, 76), "C": (82, 214, 224), "M": (214, 92, 214),
}
COLOR_EFFECT = {
    "R": "2 damage",
    "G": "1 dmg, push 1 (collision +dmg)",
    "B": "1 dmg, stun 2 beats, +1 shield",
    "Y": "1 dmg, burn 3 turns, push 1",
    "C": "1 dmg, stun 1, swap places with first hit",
    "M": "3 dmg, splashes 1 to neighbours",
}

SHAPES = ("triangle", "square", "circle")
SHAPE_NAMES = {"triangle": "Triangle", "square": "Square", "circle": "Circle"}
SHAPE_DESC = {
    "triangle": "Pierce: 3 tiles in a straight line",
    "square": "Block: 2x2 within range 3",
    "circle": "Burst: plus shape within range 3",
}

ORTH = ((0, -1), (1, 0), (0, 1), (-1, 0))

# Player modifiers (relics change these).
DEFAULT_MODS = {
    "red_bonus": 0,        # extra damage from red casts
    "collision_bonus": 0,  # extra collision damage on pushes
    "blue_shield": 1,      # shield gained per blue cast
    "chain_start": 0,      # bonus chain level at the start of a chain
    "regen": 1,            # palette charges regained per colour per turn
    "range": 0,            # extra shape range
    "burn_bonus": 0,       # extra burn turns
}

RELICS = {
    "crimson_lens": {"name": "Crimson Lens", "desc": "Red casts deal +1 damage.",
                     "mods": {"red_bonus": 1}},
    "verdant_root": {"name": "Verdant Root", "desc": "Push collisions deal +2 damage.",
                     "mods": {"collision_bonus": 2}},
    "azure_plate": {"name": "Azure Plate", "desc": "Blue casts give +1 extra shield.",
                    "mods": {"blue_shield": 1}},
    "prism_shard": {"name": "Prism Shard", "desc": "Chains start one level higher.",
                    "mods": {"chain_start": 1}},
    "echo_stone": {"name": "Echo Stone", "desc": "Regain +1 of every colour each turn.",
                   "mods": {"regen": 1}},
    "long_reach": {"name": "Long Reach", "desc": "All shapes reach 1 tile further.",
                   "mods": {"range": 1}},
    "ember_core": {"name": "Ember Core", "desc": "Burn lasts 2 turns longer.",
                   "mods": {"burn_bonus": 2}},
}
