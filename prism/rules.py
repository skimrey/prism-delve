"""The rules engine. Pure functions over GameState, no pygame, no randomness.

A turn is BEATS beats long. Each beat the player acts first (move, cast or
wait), then every enemy carries out its order for that beat. At the end of the
turn burn ticks, the palette regenerates and the next turn's orders are
planned. Because nothing is random, the UI can preview a plan exactly by
running it on a clone, and the solver can search plans.

Damage formula for a cast hit:
    base * (chain + 1) // 2, doubled if the colour is opposite to the enemy's.
Casting the SAME colour as the enemy is absorbed (no effect).
"""

from .consts import (BEATS, COMPONENTS, MAX_CHAIN, MAX_SHIELD, OPPOSITE, ORTH,
                     SHAPE_RANGE, SHAPES, COLORS)
from .enemies import KINDS, boss_color, is_boss, plan_orders, spawn
from .state import wait

MAX_ENEMIES = 7
ENEMY_SHIELD_CAP = 3


def sign(v):
    return (v > 0) - (v < 0)


def in_bounds(board, x, y):
    return 0 <= x < board.w and 0 <= y < board.h


def tile_open(board, x, y):
    return in_bounds(board, x, y) and (x, y) not in board.walls


def tile_free(state, x, y):
    p = state.player
    return (tile_open(state.board, x, y) and (x, y) != (p.x, p.y)
            and state.enemy_at(x, y) is None)


def shape_range(state):
    return SHAPE_RANGE + state.player.mods["range"]


def line_tiles(board, ox, oy, dx, dy, length):
    tiles = []
    for i in range(1, length + 1):
        x, y = ox + dx * i, oy + dy * i
        if not tile_open(board, x, y):
            break
        tiles.append((x, y))
    return tiles


def shape_tiles(state, shape, tx, ty):
    """Tiles a cast would cover, or None if the target is not legal."""
    p, board = state.player, state.board
    if shape not in SHAPES or not tile_open(board, tx, ty):
        return None
    dx, dy = tx - p.x, ty - p.y
    dist = abs(dx) + abs(dy)
    rng = shape_range(state)
    if dist > rng:
        return None
    if shape == "triangle":
        if dist == 0 or (dx != 0 and dy != 0):
            return None
        return line_tiles(board, p.x, p.y, sign(dx), sign(dy), rng)
    if shape == "square":
        raw = [(tx, ty), (tx + 1, ty), (tx, ty + 1), (tx + 1, ty + 1)]
    else:
        raw = [(tx, ty)] + [(tx + ox, ty + oy) for ox, oy in ORTH]
    tiles = [t for t in raw if tile_open(board, *t) and t != (p.x, p.y)]
    tiles.sort(key=lambda t: abs(t[0] - p.x) + abs(t[1] - p.y))
    return tiles or None


def can_afford(player, color):
    return all(player.palette[c] >= 1 for c in set(COMPONENTS[color]))


def validate_action(state, a):
    """(ok, message). The message is always shown to the player when not ok."""
    p = state.player
    if state.outcome != "ongoing":
        return False, "The fight is over."
    if a.kind == "wait":
        return True, ""
    if a.kind == "move":
        nx, ny = p.x + a.dx, p.y + a.dy
        if abs(a.dx) + abs(a.dy) != 1:
            return False, "Move one tile at a time."
        if not in_bounds(state.board, nx, ny):
            return False, "That is the edge of the room."
        if (nx, ny) in state.board.walls:
            return False, "A wall blocks that tile."
        if state.enemy_at(nx, ny):
            return False, "An enemy is standing there."
        return True, ""
    if a.kind == "cast":
        if a.color not in COLORS or a.shape not in SHAPES:
            return False, "Pick a shape and a colour."
        if not can_afford(p, a.color):
            need = "+".join(sorted(set(COMPONENTS[a.color])))
            return False, "Not enough charges (%s needed)." % need
        if shape_tiles(state, a.shape, a.tx, a.ty) is None:
            if a.shape == "triangle":
                return False, "Triangle needs a straight line within range."
            return False, "Target is out of range or blocked."
        return True, ""
    return False, "Unknown action."


def emit(ev, **kw):
    if ev is not None:
        ev.append(kw)


# ---------------------------------------------------------------- damage

def damage_enemy(state, e, amount, ev, beat):
    if amount <= 0 or e.hp <= 0:
        return 0
    soaked = min(e.shield, amount)
    e.shield -= soaked
    took = amount - soaked
    e.hp -= took
    emit(ev, t="dmg", who=e.id, amount=amount, took=took, pos=(e.x, e.y), beat=beat)
    return took


def damage_player(state, amount, ev, beat):
    p = state.player
    soaked = min(p.shield, amount)
    p.shield -= soaked
    took = amount - soaked
    p.hp -= took
    emit(ev, t="dmg", who="player", amount=amount, took=took, pos=(p.x, p.y), beat=beat)
    return took


def reap(state, ev, beat):
    for e in list(state.enemies):
        if e.hp > 0:
            continue
        state.enemies.remove(e)
        emit(ev, t="kill", who=e.id, kind=e.kind, pos=(e.x, e.y), beat=beat)
        if e.kind == "splitter":
            made = 0
            for ox, oy in ORTH:
                if made == 2 or len(state.enemies) >= MAX_ENEMIES:
                    break
                x, y = e.x + ox, e.y + oy
                if tile_free(state, x, y):
                    s = spawn(state, "shard", x, y, e.color)
                    emit(ev, t="spawn", who=s.id, kind="shard", pos=(x, y), beat=beat)
                    made += 1


def check_outcome(state):
    if state.player.hp <= 0:
        state.outcome = "defeat"
    elif not state.enemies:
        state.outcome = "victory"


def push_enemy(state, e, dx, dy, ev, beat):
    nx, ny = e.x + dx, e.y + dy
    blocker = state.enemy_at(nx, ny)
    bonus = state.player.mods["collision_bonus"]
    if tile_free(state, nx, ny):
        emit(ev, t="push", who=e.id, frm=(e.x, e.y), to=(nx, ny), beat=beat)
        e.x, e.y = nx, ny
        return
    emit(ev, t="collision", who=e.id, pos=(e.x, e.y), beat=beat)
    damage_enemy(state, e, 2 + bonus, ev, beat)
    if blocker is not None:
        damage_enemy(state, blocker, 2 + bonus, ev, beat)


def push_direction(state, e):
    p = state.player
    dx, dy = e.x - p.x, e.y - p.y
    if abs(dx) >= abs(dy):
        return sign(dx), 0
    return 0, sign(dy)


# ----------------------------------------------------------------- casts

def _scaled(base, chain, weak):
    d = base * (chain + 1) // 2
    d = max(d, 1) if base > 0 else 0
    return d * 2 if weak else d


def player_cast(state, a, beat, ev):
    p = state.player
    tiles = shape_tiles(state, a.shape, a.tx, a.ty)
    for c in set(COMPONENTS[a.color]):
        p.palette[c] -= 1
    if p.last_shape is None or p.last_shape == a.shape:
        p.chain = 1 + p.mods["chain_start"]
    else:
        p.chain += 1
    p.chain = min(p.chain, MAX_CHAIN)
    p.last_shape = a.shape
    chain = p.chain
    emit(ev, t="cast", shape=a.shape, color=a.color, tiles=list(tiles),
         chain=chain, beat=beat)

    targets = []
    for t in tiles:
        e = state.enemy_at(*t)
        if e is not None:
            targets.append(e)
    hit_positions = []
    first_hit = None
    for e in targets:
        if e.hp <= 0:
            continue
        if a.color == e.color:
            emit(ev, t="absorb", who=e.id, pos=(e.x, e.y), beat=beat)
            continue
        weak = OPPOSITE[a.color] == e.color
        if first_hit is None:
            first_hit = e
        hit_positions.append((e.x, e.y))
        col = a.color
        if col == "R":
            damage_enemy(state, e, _scaled(2 + p.mods["red_bonus"], chain, weak), ev, beat)
        elif col == "G":
            damage_enemy(state, e, _scaled(1, chain, weak), ev, beat)
            if e.hp > 0:
                push_enemy(state, e, *push_direction(state, e), ev, beat)
        elif col == "B":
            damage_enemy(state, e, _scaled(1, chain, weak), ev, beat)
            e.stun = max(e.stun, 2)
            emit(ev, t="stun", who=e.id, beat=beat)
        elif col == "Y":
            damage_enemy(state, e, _scaled(1, chain, weak), ev, beat)
            e.burn = max(e.burn, 3 + p.mods["burn_bonus"])
            emit(ev, t="burn", who=e.id, beat=beat)
            if e.hp > 0:
                push_enemy(state, e, *push_direction(state, e), ev, beat)
        elif col == "C":
            damage_enemy(state, e, _scaled(1, chain, weak), ev, beat)
            e.stun = max(e.stun, 1)
            emit(ev, t="stun", who=e.id, beat=beat)
        elif col == "M":
            damage_enemy(state, e, _scaled(3, chain, weak), ev, beat)

    if a.color == "M":
        hit_set = set(hit_positions)
        for hx, hy in hit_positions:
            for ox, oy in ORTH:
                n = state.enemy_at(hx + ox, hy + oy)
                if n is not None and (n.x, n.y) not in hit_set and n.hp > 0:
                    damage_enemy(state, n, 1, ev, beat)
    if a.color == "C" and first_hit is not None and first_hit.hp > 0:
        emit(ev, t="swap", who=first_hit.id, a=(p.x, p.y), b=(first_hit.x, first_hit.y),
             beat=beat)
        p.x, first_hit.x = first_hit.x, p.x
        p.y, first_hit.y = first_hit.y, p.y
    if a.color == "B":
        p.shield = min(MAX_SHIELD, p.shield + p.mods["blue_shield"])
        emit(ev, t="shield", who="player", beat=beat)
    if not hit_positions and not any(e.hp > 0 for e in targets):
        emit(ev, t="miss", beat=beat)


def player_action(state, a, beat, ev):
    ok, msg = validate_action(state, a)
    if not ok:
        emit(ev, t="fizzle", who="player", msg=msg, beat=beat)
        return
    p = state.player
    if a.kind == "move":
        emit(ev, t="move", who="player", frm=(p.x, p.y), to=(p.x + a.dx, p.y + a.dy),
             beat=beat)
        p.x += a.dx
        p.y += a.dy
    elif a.kind == "cast":
        player_cast(state, a, beat, ev)
    else:
        emit(ev, t="wait", who="player", beat=beat)


# --------------------------------------------------------------- enemies

def _enemy_attack(state, e, tiles, dmg, ev, beat):
    p = state.player
    hit = (p.x, p.y) in tiles
    emit(ev, t="enemy_attack", who=e.id, kind=e.kind, tiles=list(tiles), dmg=dmg,
         hit=hit, beat=beat)
    if hit:
        damage_player(state, dmg, ev, beat)


def enemy_order(state, e, order, ev, beat):
    kind = order[0]
    board = state.board
    if kind == "wait":
        return
    if kind == "move":
        nx, ny = e.x + order[1], e.y + order[2]
        if tile_free(state, nx, ny):
            emit(ev, t="move", who=e.id, frm=(e.x, e.y), to=(nx, ny), beat=beat)
            e.x, e.y = nx, ny
        else:
            emit(ev, t="blocked", who=e.id, beat=beat)
    elif kind == "hit":
        tile = (e.x + order[1], e.y + order[2])
        _enemy_attack(state, e, [tile], order[3], ev, beat)
    elif kind == "line":
        tiles = line_tiles(board, e.x, e.y, order[1], order[2], order[4])
        _enemy_attack(state, e, tiles, order[3], ev, beat)
    elif kind == "splash":
        cx, cy = e.x + order[1], e.y + order[2]
        tiles = [(cx, cy)] + [(cx + ox, cy + oy) for ox, oy in ORTH]
        tiles = [t for t in tiles if tile_open(board, *t)]
        _enemy_attack(state, e, tiles, order[3], ev, beat)
    elif kind == "shield":
        for ox, oy in ORTH:
            ally = state.enemy_at(e.x + ox, e.y + oy)
            if ally is not None:
                ally.shield = min(ENEMY_SHIELD_CAP, ally.shield + order[1])
                emit(ev, t="shield", who=ally.id, beat=beat)
    elif kind == "summon":
        if len(state.enemies) >= MAX_ENEMIES:
            return
        for ox, oy in ORTH:
            x, y = e.x + ox, e.y + oy
            if tile_free(state, x, y):
                s = spawn(state, order[1], x, y, e.color)
                emit(ev, t="spawn", who=s.id, kind=order[1], pos=(x, y), beat=beat)
                break


def enemy_phase(state, beat, ev):
    for e in sorted(state.enemies, key=lambda en: en.id):
        if e.hp <= 0 or e not in state.enemies:
            continue
        if e.stun > 0:
            e.stun -= 1
            emit(ev, t="stunned", who=e.id, beat=beat)
            continue
        order = e.orders[beat] if beat < len(e.orders) else ("wait",)
        enemy_order(state, e, order, ev, beat)
        if state.player.hp <= 0:
            break


# ------------------------------------------------------------ turn flow

def resolve_beat(state, action, beat, ev=None):
    if state.outcome != "ongoing":
        return
    player_action(state, action, beat, ev)
    reap(state, ev, beat)
    check_outcome(state)
    if state.outcome != "ongoing":
        return
    enemy_phase(state, beat, ev)
    reap(state, ev, beat)
    check_outcome(state)


def end_turn(state, ev=None):
    for e in list(state.enemies):
        if e.burn > 0:
            damage_enemy(state, e, 1, ev, BEATS)
            e.burn -= 1
    reap(state, ev, BEATS)
    check_outcome(state)
    p = state.player
    if state.outcome == "ongoing":
        for c in p.palette:
            p.palette[c] = min(p.cap[c], p.palette[c] + p.mods["regen"])


def begin_turn(state):
    state.turn += 1
    p = state.player
    p.chain = 0
    p.last_shape = None
    for e in state.enemies:
        if is_boss(e.kind):
            e.color = boss_color(state, e)
    plan_orders(state)


def snapshot(state):
    p = state.player
    return {
        "player": (p.x, p.y, p.hp, p.shield),
        "palette": dict(p.palette),
        "enemies": [(e.id, e.kind, e.x, e.y, e.hp, e.max_hp, e.color, e.shield,
                     e.stun, e.burn) for e in state.enemies],
        "outcome": state.outcome,
    }


class TurnResult:
    def __init__(self, events, snapshots, outcome):
        self.events = events
        self.snapshots = snapshots
        self.outcome = outcome


def padded(actions):
    acts = list(actions)[:BEATS]
    return acts + [wait()] * (BEATS - len(acts))


def resolve_turn(state, actions, advance=True, record=True):
    """Run a full turn in place. Returns a TurnResult (events + per-beat
    snapshots for animation)."""
    ev = [] if record else None
    snaps = []
    for beat, a in enumerate(padded(actions)):
        if state.outcome != "ongoing":
            break
        resolve_beat(state, a, beat, ev)
        if record:
            snaps.append(snapshot(state))
    if state.outcome == "ongoing":
        end_turn(state, ev)
        if record:
            snaps.append(snapshot(state))
        if advance and state.outcome == "ongoing":
            begin_turn(state)
    return TurnResult(ev, snaps, state.outcome)


def simulate_prefix(state, actions):
    """Clone of the state after the first len(actions) beats (player then
    enemies each beat), without end-of-turn effects. Used to validate the
    next queued action against what the board will really look like."""
    s = state.clone()
    ev = []
    for beat, a in enumerate(actions):
        resolve_beat(s, a, beat, ev)
    return s, ev


def preview_full(state, actions):
    """Exact preview of the whole turn for a (possibly short) queue."""
    s = state.clone()
    res = resolve_turn(s, actions, advance=False, record=True)
    return s, res.events
