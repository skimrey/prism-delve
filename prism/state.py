"""Plain state objects for combat. Cheap to clone so the solver and the UI
preview can simulate freely."""

from dataclasses import dataclass

from .consts import (DEFAULT_MODS, GRID_H, GRID_W, PLAYER_HP, PLAYER_START,
                     PRIMARIES, START_CAP, START_CHARGES)


@dataclass(frozen=True)
class Action:
    """One beat of the player's plan: move, cast or wait."""
    kind: str
    dx: int = 0
    dy: int = 0
    shape: str = ""
    color: str = ""
    tx: int = 0
    ty: int = 0

    def describe(self):
        if self.kind == "move":
            names = {(0, -1): "up", (1, 0): "right", (0, 1): "down", (-1, 0): "left"}
            return "Move " + names.get((self.dx, self.dy), "?")
        if self.kind == "cast":
            return "%s %s" % (self.color, self.shape)
        return "Wait"


def move(dx, dy):
    return Action("move", dx=dx, dy=dy)


def cast(shape, color, tx, ty):
    return Action("cast", shape=shape, color=color, tx=tx, ty=ty)


def wait():
    return Action("wait")


class Board:
    __slots__ = ("w", "h", "walls")

    def __init__(self, w=GRID_W, h=GRID_H, walls=()):
        self.w = w
        self.h = h
        self.walls = frozenset(walls)


class Player:
    __slots__ = ("x", "y", "hp", "max_hp", "shield", "palette", "cap",
                 "chain", "last_shape", "mods")

    def __init__(self):
        self.x, self.y = PLAYER_START
        self.hp = PLAYER_HP
        self.max_hp = PLAYER_HP
        self.shield = 0
        self.cap = {c: START_CAP for c in PRIMARIES}
        self.palette = {c: START_CHARGES for c in PRIMARIES}
        self.chain = 0
        self.last_shape = None
        self.mods = dict(DEFAULT_MODS)

    def begin_fight(self):
        self.x, self.y = PLAYER_START
        self.shield = 0
        self.chain = 0
        self.last_shape = None
        self.palette = {c: min(self.cap[c], START_CHARGES) for c in PRIMARIES}

    def clone(self):
        p = Player.__new__(Player)
        p.x, p.y, p.hp, p.max_hp, p.shield = self.x, self.y, self.hp, self.max_hp, self.shield
        p.palette = dict(self.palette)
        p.cap = self.cap          # caps never change inside a fight
        p.chain = self.chain
        p.last_shape = self.last_shape
        p.mods = self.mods        # mods never change inside a fight
        return p


class Enemy:
    __slots__ = ("id", "kind", "x", "y", "hp", "max_hp", "color", "shield",
                 "stun", "burn", "orders")

    def __init__(self, eid, kind, x, y, hp, color):
        self.id = eid
        self.kind = kind
        self.x, self.y = x, y
        self.hp = self.max_hp = hp
        self.color = color
        self.shield = 0
        self.stun = 0
        self.burn = 0
        self.orders = []

    def clone(self):
        e = Enemy.__new__(Enemy)
        e.id, e.kind, e.x, e.y = self.id, self.kind, self.x, self.y
        e.hp, e.max_hp, e.color = self.hp, self.max_hp, self.color
        e.shield, e.stun, e.burn = self.shield, self.stun, self.burn
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

    def add_enemy(self, kind, x, y, color, hp):
        e = Enemy(self.next_id, kind, x, y, hp, color)
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
