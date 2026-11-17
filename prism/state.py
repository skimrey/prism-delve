"""Plain state objects for combat. Cheap to clone so the solver and the UI
preview can simulate freely."""

from dataclasses import dataclass

from .consts import (COLOR_NAMES, DEFAULT_MODS, GRID_H, GRID_W, PATTERNS, PLAYER_HP,
                     PLAYER_START, PRIMARIES, SHAPE_PLURAL, START_CAP, START_CHARGES,
                     START_PATTERNS)

DIR_NAMES = {(0, -1): "up", (1, 0): "right", (0, 1): "down", (-1, 0): "left",
             (1, -1): "up-right", (1, 1): "down-right", (-1, 1): "down-left",
             (-1, -1): "up-left"}


@dataclass(frozen=True)
class Action:
    """One beat of the player's plan: move, cast or wait.

    For a cast, (dx, dy) is the aim: a unit direction for Beam and Slant, the
    offset of the landing tile for Lob, and (0, 0) for Halo and Leap."""
    kind: str
    dx: int = 0
    dy: int = 0
    pattern: str = ""
    shape: str = ""
    color: str = ""

    def describe(self):
        if self.kind == "move":
            return "Move " + DIR_NAMES.get((self.dx, self.dy), "?")
        if self.kind == "cast":
            aim = DIR_NAMES.get((self.dx, self.dy), "")
            return "%s %s%s at %s" % (COLOR_NAMES.get(self.color, "?"),
                                      PATTERNS.get(self.pattern, {"name": "?"})["name"],
                                      " " + aim if aim else "",
                                      SHAPE_PLURAL.get(self.shape, "?"))
        return "Wait"


def move(dx, dy):
    return Action("move", dx=dx, dy=dy)


def cast(pattern, shape, color, dx=0, dy=0):
    return Action("cast", dx=dx, dy=dy, pattern=pattern, shape=shape, color=color)


def wait():
    return Action("wait")


class Board:
    """The room. `portals` are holes in the floor, in pairs: a circle rolling
    into one drops through and rolls out of its partner, still rolling the
    same way. Only round things fall in: corners catch on the rim, so the Set
    walk straight over them (and so does light). `tiles` are the other
    special floor tiles, which likewise only matter to something rolling."""
    __slots__ = ("w", "h", "walls", "portals", "pairs", "tiles")

    def __init__(self, w=GRID_W, h=GRID_H, walls=(), portals=(), tiles=None):
        self.w = w
        self.h = h
        self.walls = frozenset(walls)
        # other special floor tiles, (x, y) -> kind (see consts.TWISTS and
        # rules.roll_route): "spring", "drift", "bend/", "bend\\", "pool:R" ...
        self.tiles = dict(tiles or {})
        self.pairs = tuple((tuple(a), tuple(b)) for a, b in portals)
        self.portals = {}
        for a, b in self.pairs:
            self.portals[a] = b
            self.portals[b] = a

    def pair_index(self, tile):
        """Which pair a hole belongs to (its colour on the board), or None."""
        for i, (a, b) in enumerate(self.pairs):
            if tile in (a, b):
                return i
        return None


class Player:
    __slots__ = ("x", "y", "hp", "max_hp", "shield", "palette", "cap",
                 "patterns", "used", "mods", "rolls")

    def __init__(self):
        self.x, self.y = PLAYER_START
        self.hp = PLAYER_HP
        self.max_hp = PLAYER_HP
        self.shield = 0
        self.cap = {c: START_CAP for c in PRIMARIES}
        self.palette = {c: START_CHARGES for c in PRIMARIES}
        self.patterns = list(START_PATTERNS)   # patterns you know (grows over a run)
        self.used = frozenset()                # patterns already cast this turn
        self.mods = dict(DEFAULT_MODS)
        self.rolls = False                     # a circle: moves roll until something stops you

    def begin_fight(self):
        self.x, self.y = PLAYER_START
        self.shield = 0
        self.used = frozenset()
        self.palette = {c: min(self.cap[c], START_CHARGES) for c in PRIMARIES}

    def clone(self):
        p = Player.__new__(Player)
        p.x, p.y, p.hp, p.max_hp, p.shield = self.x, self.y, self.hp, self.max_hp, self.shield
        p.palette = dict(self.palette)
        p.cap = self.cap          # caps never change inside a fight
        p.patterns = self.patterns  # nor do the patterns you know
        p.used = self.used
        p.mods = self.mods        # mods never change inside a fight
        p.rolls = self.rolls
        return p


class Enemy:
    __slots__ = ("id", "kind", "x", "y", "hp", "max_hp", "color", "shape", "shield",
                 "stun", "burn", "orders", "squad")

    def __init__(self, eid, kind, x, y, hp, color, shape):
        self.id = eid
        self.kind = kind
        self.x, self.y = x, y
        self.hp = self.max_hp = hp
        self.color = color
        self.shape = shape        # what your light must be cut to fit
        self.squad = None         # enemies sharing a squad id march in formation
        self.shield = 0
        self.stun = 0
        self.burn = 0
        self.orders = []

    def clone(self):
        e = Enemy.__new__(Enemy)
        e.id, e.kind, e.x, e.y = self.id, self.kind, self.x, self.y
        e.hp, e.max_hp, e.color, e.shape = self.hp, self.max_hp, self.color, self.shape
        e.shield, e.stun, e.burn = self.shield, self.stun, self.burn
        e.squad = self.squad
        e.orders = self.orders    # orders are replaced, never mutated
        return e


class GameState:
    """One combat. `outcome` is 'ongoing', 'victory' or 'defeat'."""

    def __init__(self, board, player):
        self.board = board
        self.player = player
        self.enemies = []
        self.turn = 0
        self.next_id = 1
        self.outcome = "ongoing"

    def add_enemy(self, kind, x, y, color, hp, shape):
        e = Enemy(self.next_id, kind, x, y, hp, color, shape)
        self.next_id += 1
        self.enemies.append(e)
        return e

    def clone(self):
        s = GameState.__new__(GameState)
        s.board = self.board
        s.player = self.player.clone()
        s.enemies = [e.clone() for e in self.enemies]
        s.turn = self.turn
        s.next_id = self.next_id
        s.outcome = self.outcome
        return s

    def enemy_at(self, x, y):
        for e in self.enemies:
            if e.x == x and e.y == y:
                return e
        return None

    def get(self, eid):
        for e in self.enemies:
            if e.id == eid:
                return e
        return None
