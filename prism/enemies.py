"""Enemy definitions and the AI that plans their orders.

At the start of every turn each enemy gets one order per beat. Orders are
RELATIVE to where the enemy stands when the beat resolves, so pushing,
stunning or dodging an enemy changes what it hits. That is what makes
planning meaningful: everything is visible and deterministic.

Order forms:
    ("wait",)
    ("move", dx, dy)
    ("hit", dx, dy, dmg)              melee on an adjacent offset tile
    ("line", dx, dy, dmg, length)     piercing line
    ("splash", cx, cy, dmg)           plus-shaped burst centred at an offset
    ("shield", amount)                shield orthogonally adjacent allies
    ("summon", kind)                  spawn a minion next to the summoner
"""

from .consts import BEATS, COLORS, ORTH

KINDS = {
    "pawn": {"label": "Pawn", "hp": 4, "shape": "square", "dmg": 2,
             "desc": "Walks up and strikes."},
    "lancer": {"label": "Lancer", "hp": 3, "shape": "triangle", "dmg": 2,
               "desc": "Lines up, then pierces a row or column."},
    "bloom": {"label": "Bloom", "hp": 4, "shape": "circle", "dmg": 2,
              "desc": "Lobs a burst at where you stand."},
    "warden": {"label": "Warden", "hp": 5, "shape": "square", "dmg": 1,
               "desc": "Shields its allies, then pokes."},
    "splitter": {"label": "Splitter", "hp": 4, "shape": "circle", "dmg": 2,
                 "desc": "Splits into two shards when killed."},
    "shard": {"label": "Shard", "hp": 1, "shape": "triangle", "dmg": 1,
              "desc": "Fragile and quick."},
    "colossus": {"label": "Colossus", "hp": 18, "shape": "square", "dmg": 3,
                 "boss": True, "line": 2, "summon": "pawn",
                 "script": ("approach", "strike", "line", "summon"),
                 "desc": "Boss. Changes colour every turn."},
    "oracle": {"label": "Oracle", "hp": 22, "shape": "circle", "dmg": 3,
               "boss": True, "line": 3, "splash": 3, "summon": "lancer",
               "script": ("splash", "approach", "splash", "line"),
               "desc": "Boss. Bursts, pierces and shifts colour."},
    "prism": {"label": "Prism King", "hp": 28, "shape": "triangle", "dmg": 4,
              "boss": True, "line": 3, "splash": 3, "summon": "bloom",
              "script": ("splash", "line", "strike", "summon"),
              "desc": "Boss. The final colour wheel."},
}

BOSS_FOR_ACT = {1: "colossus", 2: "oracle", 3: "prism"}


def is_boss(kind):
    return bool(KINDS[kind].get("boss"))


def spawn(state, kind, x, y, color, hp_bonus=0):
    return state.add_enemy(kind, x, y, color, KINDS[kind]["hp"] + hp_bonus)


def _sign(v):
    return (v > 0) - (v < 0)


def _passable(state, x, y):
    b = state.board
    return 0 <= x < b.w and 0 <= y < b.h and (x, y) not in b.walls


def _step_toward(state, x, y, tx, ty):
    """One step from (x, y) toward (tx, ty), avoiding walls. None if stuck."""
    dx, dy = tx - x, ty - y
    options = []
    if abs(dx) >= abs(dy):
        options = [(_sign(dx), 0), (0, _sign(dy))]
    else:
        options = [(0, _sign(dy)), (_sign(dx), 0)]
    for ox, oy in options:
        if (ox, oy) == (0, 0):
            continue
        if _passable(state, x + ox, y + oy) and (x + ox, y + oy) != (tx, ty):
            return ox, oy
    return None


def _step_to_align(state, x, y, tx, ty):
    """One step that closes the SMALLER offset so a line attack can follow."""
    dx, dy = tx - x, ty - y
    if dx == 0 or dy == 0:
        return None
    if abs(dx) <= abs(dy):
        options = [(_sign(dx), 0), (0, _sign(dy))]
    else:
        options = [(0, _sign(dy)), (_sign(dx), 0)]
    for ox, oy in options:
        if _passable(state, x + ox, y + oy):
            return ox, oy
    return None


def _melee_orders(state, e, dmg):
    px, py = state.player.x, state.player.y
    x, y = e.x, e.y
    orders = []
    cd = 0
    for _ in range(BEATS):
        dist = abs(px - x) + abs(py - y)
        if dist == 1:
            if cd > 0:
                orders.append(("wait",))
                cd -= 1
            else:
                orders.append(("hit", px - x, py - y, dmg))
                cd = 1
            continue
        step = _step_toward(state, x, y, px, py)
        if step is None:
            orders.append(("wait",))
        else:
            orders.append(("move", step[0], step[1]))
            x += step[0]
            y += step[1]
        if cd > 0:
            cd -= 1
    return orders


def _lancer_orders(state, e, dmg, length=3):
    px, py = state.player.x, state.player.y
    x, y = e.x, e.y
    orders = []
    cd = 0
    for _ in range(BEATS):
        aligned = (x == px) != (y == py)
        in_reach = abs(px - x) + abs(py - y) <= length
        if aligned and in_reach:
            if cd > 0:
                orders.append(("wait",))
                cd -= 1
            else:
                orders.append(("line", _sign(px - x), _sign(py - y), dmg, length))
                cd = 1
            continue
        if aligned:                      # lined up but too far away: close the gap
            step = _step_toward(state, x, y, px, py)
        else:
            step = _step_to_align(state, x, y, px, py)
        if step is None:
            orders.append(("wait",))
        else:
            orders.append(("move", step[0], step[1]))
            x += step[0]
            y += step[1]
        if cd > 0:
            cd -= 1
    return orders


def _bloom_orders(state, e, dmg, reach=3):
    px, py = state.player.x, state.player.y
    x, y = e.x, e.y
    orders = []
    cd = 1                     # wind-up beat: lets you step two tiles clear of the burst
    for _ in range(BEATS):
        dist = abs(px - x) + abs(py - y)
        if dist <= reach:
            if cd > 0:
                orders.append(("wait",))
                cd -= 1
            else:
                orders.append(("splash", px - x, py - y, dmg))
                cd = 1
            continue
        step = _step_toward(state, x, y, px, py)
        if step is None:
            orders.append(("wait",))
        else:
            orders.append(("move", step[0], step[1]))
            x += step[0]
            y += step[1]
        if cd > 0:
            cd -= 1
    return orders


def _warden_orders(state, e, dmg):
    orders = [("shield", 2)]
    rest = _melee_orders(state, e, dmg)
    # the first beat is spent shielding, so the walk starts one beat late
    return orders + rest[:BEATS - 1]


def _boss_orders(state, e, spec):
    px, py = state.player.x, state.player.y
    x, y = e.x, e.y
    orders = []
    for beat in range(BEATS):
        action = spec["script"][beat % len(spec["script"])]
        dist = abs(px - x) + abs(py - y)
        aligned = (x == px) != (y == py)
        order = None
        if action == "approach":
            if dist > 1:
                step = _step_toward(state, x, y, px, py)
                if step:
                    order = ("move", step[0], step[1])
                    x += step[0]
                    y += step[1]
        elif action == "strike":
            if dist == 1:
                order = ("hit", px - x, py - y, spec["dmg"])
            else:
                step = _step_toward(state, x, y, px, py)
                if step:
                    order = ("move", step[0], step[1])
                    x += step[0]
                    y += step[1]
        elif action == "line":
            if aligned:
                order = ("line", _sign(px - x), _sign(py - y), spec["line"], 3)
            else:
                step = _step_to_align(state, x, y, px, py)
                if step:
                    order = ("move", step[0], step[1])
                    x += step[0]
                    y += step[1]
        elif action == "splash":
            if dist <= 4:
                order = ("splash", px - x, py - y, spec.get("splash", spec["dmg"]))
            else:
                step = _step_toward(state, x, y, px, py)
                if step:
                    order = ("move", step[0], step[1])
                    x += step[0]
                    y += step[1]
        elif action == "summon":
            if state.turn % 2 == 0:
                order = ("summon", spec["summon"])
        orders.append(order or ("wait",))
    return orders


def plan_orders(state):
    """Give every enemy its orders for the coming turn."""
    for e in state.enemies:
        spec = KINDS[e.kind]
        if spec.get("boss"):
            e.orders = _boss_orders(state, e, spec)
        elif e.kind in ("pawn", "splitter", "shard"):
            e.orders = _melee_orders(state, e, spec["dmg"])
        elif e.kind == "lancer":
            e.orders = _lancer_orders(state, e, spec["dmg"])
        elif e.kind == "bloom":
            e.orders = _bloom_orders(state, e, spec["dmg"])
        elif e.kind == "warden":
            e.orders = _warden_orders(state, e, spec["dmg"])
        else:  # pragma: no cover - guards against a new kind with no AI
            e.orders = [("wait",)] * BEATS


def boss_color(state, e):
    return COLORS[(state.turn + e.id) % len(COLORS)]


NEIGHBOURS = ORTH
