"""Run state: the climb through the Sorter (three floors, one per act),
rewards, Tinters (shops), Still Tiles (rests) and Oddities (events).

In-world: you are a triangle climbing the Sorter. Each floor's Keeper holds
the side you need for the next door; beating it grows you a side (see
consts.FORMS). Losing means the Set sorts you back into your slot at the
bottom, a triangle again: that is the roguelite loop.

Currency is stored as `gold` for save/test stability but is called glint
everywhere the player can see it.
"""

import json
import os
import random

from .consts import (COLOR_NAMES, FLOORS, FORMS, GRADES, PATTERN_ORDER, PATTERNS, PRIMARIES,
                     RELICS, TOWERS)
from .enemies import BOSS_FOR_ACT, KINDS
from .dungeon import Node, Route, build_combat, generate_route
from .state import Player

ACTS = 3

# Oddities. Each has two versions:
#   "gift"  every choice is a bonus: you pick one, and there is no walking away
#   "deal"  bonuses come with a cost, so walking away is a real option
# Low floors mostly give gifts; higher floors mostly make deals (GIFT_CHANCE).
# A choice is (id, label, effects); effects are data, so the description,
# the pictures on the button and what actually happens can't disagree.
# Effects: ("heal", n) ("hp", -n) ("maxhp", n) ("cap", "low"|"high", n)
#          ("glint", n) ("facet", 0|1) ("gamble", chance, good_effects, bad_effects)
# The tone is a toy box: costs are HP, glint or a little colour, never pain.
# "low"/"high" mean your smallest/largest colour cap, and facet 0/1 the two
# facets rolled for this visit; both are settled when you walk in.
EVENTS = [
    {"id": "well", "title": "A Pool of Colour",
     "gift": [("drink", "Soak it up", [("cap", "low", 1)]),
              ("bathe", "Float in it", [("heal", 6)])],
     "deal": [("drink", "Drink deep", [("cap", "low", 2), ("cap", "high", -1)]),
              ("bathe", "Wash in it", [("heal", 12), ("cap", "high", -1)]),
              ("leave", "Walk on", [])]},
    {"id": "polisher", "title": "The Polisher",
     "gift": [("polish", "Polish this facet", [("facet", 0)]),
              ("polish2", "Or this one", [("facet", 1)])],
     "deal": [("polish", "Big polish", [("facet", 0), ("cap", "high", -1)]),
              ("polish2", "Fancy polish", [("facet", 1), ("glint", -30)]),
              ("leave", "No thanks", [])]},
    {"id": "trader", "title": "A Drifting Tinter",
     "gift": [("sample", "Free sample", [("heal", 5)]),
              ("change", "Spare change", [("glint", 15)])],
     "deal": [("buy", "Buy some light", [("glint", -10), ("heal", 8)]),
              ("haggle", "Haggle", [("gamble", 0.5, [("glint", 25)], [("glint", -10)])]),
              ("leave", "Let it clunk away", [])]},
]
GIFT_CHANCE = {1: 0.75, 2: 0.4, 3: 0.15}


def effects_text(effects):
    """Several effects as one sentence-ish line: "Heal 6 HP. -1 max Red charge." """
    return " ".join(effect_text(e).rstrip(".") + "." for e in effects)


def effect_text(eff):
    """Plain words for what an effect does (after the event is settled)."""
    kind = eff[0]
    if kind == "heal":
        return "Heal %d HP" % eff[1]
    if kind == "hp":
        return "Lose %d HP" % -eff[1]
    if kind == "maxhp":
        return "%+d max HP" % eff[1]
    if kind == "cap":
        name = COLOR_NAMES[eff[1]]
        return "%+d max %s charge%s" % (eff[2], name, "s" if abs(eff[2]) > 1 else "")
    if kind == "glint":
        return ("Get %d glint" if eff[1] > 0 else "Pay %d glint") % abs(eff[1])
    if kind == "facet":
        return "New facet, %s: %s" % (RELICS[eff[1]]["name"], RELICS[eff[1]]["desc"])
    if kind == "gamble":
        good = ", ".join(effect_text(e) for e in eff[2])
        bad = ", ".join(effect_text(e) for e in eff[3])
        return "%d%%: %s. Otherwise: %s" % (eff[1] * 100, good, bad.lower())
    return "Nothing happens"


def shapes_for(act, layer):
    """Which shapes the Set can be at this point of the climb. New shapes are
    introduced one at a time: first triangles only (learn patterns and colour),
    then squares (now cutting your light to fit matters), then circles."""
    if act <= 1:
        return (("triangle", 1),) if layer <= 1 else (("triangle", 3), ("square", 2))
    if act == 2:
        return (("triangle", 2), ("square", 3), ("circle", 2))
    return (("triangle", 1), ("square", 2), ("circle", 3))


def grade(turns, par):
    """How a win compares to par: a GRADES entry as a dict, or None."""
    if turns is None or par is None:
        return None
    for name, over, glint in GRADES:
        if turns <= par + over:
            return {"name": name, "turns": turns, "par": par, "glint": glint}
    return {"name": "Messy", "turns": turns, "par": par, "glint": 0}


def _pattern_option(pt):
    return {"id": "pattern:" + pt, "label": "Learn a pattern: %s" % PATTERNS[pt]["name"],
            "desc": PATTERNS[pt]["desc"]}


def save_run(run, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(run.to_dict(), f)
    os.replace(tmp, path)                   # never leave a half-written save


def load_run(path):
    """The saved run, or None if there isn't a usable one."""
    try:
        with open(path) as f:
            return Run.from_dict(json.load(f))
    except (OSError, ValueError, KeyError, TypeError):
        return None


class Meta:
    """Tiny persistent record across runs."""

    def __init__(self, path=None):
        self.path = path
        self.data = {"runs": 0, "wins": 0, "best_act": 0, "seen_intro": False,
                     "seen_board_key": False, "seen_danger_tip": False}
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    self.data.update(json.load(f))
            except (OSError, ValueError):
                pass

    def record(self, act_reached, won):
        self.data["runs"] += 1
        self.data["wins"] += 1 if won else 0
        self.data["best_act"] = max(self.data["best_act"], act_reached)
        self.save()

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f)


def tower_difficulty(position):
    """(tier, rooms) for the tower at `position` in your world: the first is
    gentle (tier 1, four rooms), the middle ones tougher, the last ones
    toughest (tier 3, six rooms)."""
    tier = 1 + (position >= 1) + (position >= 5)
    rooms = 4 + (position >= 2) + (position >= 5)
    return tier, rooms


def route_signature(route):
    """A route's layout as a string (to tell one climb's floors from the last)."""
    return "|".join(",".join("%s>%s" % (n.kind, "".join(map(str, n.nexts))) for n in layer)
                    for layer in route.layers)


class Run:
    def __init__(self, seed=None, tower=None, position=None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.player = Player()
        self.tower = tower             # None: the Sorter. Else a TOWERS id, climbed as a circle
        self.position = position       # where that tower is in your world's order (0: the first)
        self.again = False             # a tower whose friend is already out: a climb just for fun
        self.act = 1
        self.gold = 0
        self.relics = []
        if tower:
            t = TOWERS[tower]
            self.act = t["act"]
            p = self.player
            p.rolls = True                         # you're a circle now
            p.patterns = ["beam", "slant", "halo", "lob"]
            p.max_hp = p.hp = 18
            for c in PRIMARIES:
                p.cap[c] += 1
            self.route = generate_route(self.rng, self.act, depth=self.depth())
        else:
            self.route = generate_route(self.rng, 1)
        self.layer = -1
        self.node = None
        self.visited = set()           # (layer, index) of nodes entered this act
        self.state = None
        self.finished = None           # None | "victory" | "defeat"
        self.shop = []
        self.event = None
        self.grade = None              # how the last fight went against par
        self.seen_shapes = set()       # shapes met so far this climb (new ones get announced)
        self.gift = None               # the pattern the last new form brought
        self.door_heal = 0             # what the last door's light mended
        self.event_outcome = None      # what the last Oddity choice actually did
        self.last_kind = None          # the kind of the last fight won
        self.last_patterns = set()     # patterns the last fight's enemies used

    # -- saving (only ever on the floor map, between rooms)
    SAVE_VERSION = 1

    def to_dict(self):
        p = self.player
        version, internal, gauss = self.rng.getstate()
        return {
            "version": self.SAVE_VERSION, "seed": self.seed, "tower": self.tower, "position": self.position,
            "again": self.again,
            "rng": [version, list(internal), gauss],
            "act": self.act, "gold": self.gold, "relics": list(self.relics),
            "layer": self.layer, "node": self.node, "visited": sorted(self.visited),
            "route": [[{"kind": n.kind, "nexts": list(n.nexts)} for n in layer]
                      for layer in self.route.layers],
            "player": {"hp": p.hp, "max_hp": p.max_hp, "cap": dict(p.cap),
                       "patterns": list(p.patterns), "mods": dict(p.mods), "rolls": p.rolls},
            "seen_shapes": sorted(self.seen_shapes), "last_patterns": sorted(self.last_patterns),
            "last_kind": self.last_kind, "gift": self.gift, "door_heal": self.door_heal,
        }

    @classmethod
    def from_dict(cls, d):
        if d.get("version") != cls.SAVE_VERSION:
            raise ValueError("save from another version")
        run = cls(d["seed"], d.get("tower"), d.get("position"))
        run.again = d.get("again", False)
        version, internal, gauss = d["rng"]
        run.rng.setstate((version, tuple(internal), gauss))
        run.act, run.gold, run.relics = d["act"], d["gold"], list(d["relics"])
        run.layer, run.node = d["layer"], d["node"]
        run.visited = {tuple(v) for v in d["visited"]}
        run.route = Route([[Node(n["kind"], list(n["nexts"])) for n in layer] for layer in d["route"]])
        p, pd = run.player, d["player"]
        p.hp, p.max_hp = pd["hp"], pd["max_hp"]
        p.cap = dict(pd["cap"])
        p.palette = {c: min(p.cap[c], v) for c, v in p.palette.items()}
        p.patterns = list(pd["patterns"])
        p.mods = dict(pd["mods"])
        p.rolls = pd.get("rolls", False)
        run.seen_shapes = set(d["seen_shapes"])
        run.last_patterns = set(d["last_patterns"])
        run.last_kind, run.gift, run.door_heal = d["last_kind"], d["gift"], d["door_heal"]
        return run

    # -- where you are
    def place(self):
        """The look and name of where you are: a Sorter floor or another tower."""
        return TOWERS[self.tower] if self.tower else FLOORS[max(1, min(self.act, len(FLOORS)))]

    def keeper(self):
        """The kind of the boss waiting at the end of this floor."""
        return TOWERS[self.tower]["boss"] if self.tower else BOSS_FOR_ACT[min(self.act, 3)]

    # -- story
    def form(self):
        """The shape you are right now (a FORMS entry). Past the Round Door
        (and in the towers) you're round enough: `self.sides` sides, which
        grow as you get friends out (world.your_sides); 0 is a circle."""
        if self.finished == "victory" or self.tower:
            from .world import ROUND_ENOUGH, shape_of
            sides = getattr(self, "sides", ROUND_ENOUGH) if self.tower else ROUND_ENOUGH
            form = dict(FORMS[len(FORMS)])
            form["shape"] = shape_of(sides)
            form["sides"] = sides
            form["name"] = "Round" if not sides else "%d sides" % sides
            return form
        return FORMS[min(self.act, len(FORMS) - 1)]

    def grow_to(self, act):
        """Jump to floor `act` as if every Keeper below had been beaten (for
        testing mode and tests): the forms, their perks and their patterns."""
        for a in range(self.act + 1, act + 1):
            self.act = a
            self._grow_side()
        return self

    def _grow_side(self):
        """Beating a Keeper: you take its spare side and become the next form."""
        f = FORMS[self.act]
        p = self.player
        p.max_hp += f["max_hp"]
        p.hp += f["max_hp"]
        # slotting through the new door's light mends you: half of what you're missing
        self.door_heal = (p.max_hp - p.hp + 1) // 2
        p.hp += self.door_heal
        for c in PRIMARIES:
            p.cap[c] += f["cap"]
        # every form brings its own pattern; if you already learned it from the
        # Set, you get the next one you don't know instead
        self.gift = None
        if f["gift"]:
            wanted = [f["gift"]] + [pt for pt in PATTERN_ORDER if pt != f["gift"]]
            self.gift = next((pt for pt in wanted if pt not in p.patterns), None)
            if self.gift:
                p.patterns.append(self.gift)

    # -- navigation
    def choices(self):
        """[(index, Node)] the player may enter next."""
        if self.layer == -1:
            return list(enumerate(self.route.layers[0]))
        cur = self.route.layers[self.layer][self.node]
        nxt = self.route.layers[self.layer + 1]
        return [(i, nxt[i]) for i in cur.nexts]

    def enter(self, idx):
        valid = [i for i, _ in self.choices()]
        if idx not in valid:
            raise ValueError("node %r is not reachable from here" % (idx,))
        self.layer += 1
        self.node = idx
        self.visited.add((self.layer, idx))
        node = self.route.layers[self.layer][idx]
        self.state = None
        if node.kind in ("fight", "elite", "boss"):
            self.state = build_combat(self.rng, self.act, node.kind, self.player,
                                      shapes=shapes_for(self.act, self.layer), boss=self.keeper(),
                                      tier=self.tier(), portals=self.portal_pairs(),
                                      twists=self.twists())
        elif node.kind == "shop":
            self.shop = self._make_shop()
        elif node.kind == "event":
            self.event = self.make_event()
        return node

    def tier(self):
        """How much tougher than the Sorter the shapes here are (0 in the
        Sorter). It rises with the tower's place in your world: whatever order
        you put them in, the towers get harder as you go (see tower_difficulty)."""
        if not self.tower:
            return 0
        if self.position is None:
            return TOWERS[self.tower].get("tier", 1)
        return tower_difficulty(self.position)[0]

    def depth(self):
        """How many rooms before the tower's Keeper."""
        if self.position is None:
            return TOWERS[self.tower]["depth"]
        return tower_difficulty(self.position)[1]

    def twists(self):
        """The special floor tiles this tower has (consts.TWISTS)."""
        return tuple(TOWERS[self.tower].get("twists", ())) if self.tower else ()

    def portal_pairs(self):
        """Pairs of holes in each floor here (only the harder towers have them)."""
        return TOWERS[self.tower].get("portals", 0) if self.tower else 0

    def current_kind(self):
        return self.route.layers[self.layer][self.node].kind

    def finish_combat(self, victory, turns=None, par=None):
        """Call when a fight ends. Returns gold earned. With `turns` and the
        fight's `par`, a quick win is graded and pays extra (see GRADES)."""
        kind = self.current_kind()
        self.last_kind = kind
        if self.state is not None:
            self.last_patterns = getattr(self.state, "seen_patterns", None) or \
                {KINDS[e.kind]["pattern"] for e in self.state.enemies}
        self.state = None
        self.grade = None
        if not victory:
            self.finished = "defeat"
            return 0
        gold = 10 + 5 * self.act + (10 if kind == "elite" else 0) + (20 if kind == "boss" else 0)
        self.grade = grade(turns, par)
        if self.grade:
            gold += self.grade["glint"]
        self.gold += gold
        return gold

    def leave_node(self):
        """Advance after a node is fully resolved (rewards taken etc)."""
        if self.current_kind() == "boss" and self.tower:
            self.finished = "rescued"          # you reached the window
            return
        if self.current_kind() == "boss":
            self.act += 1
            if self.act > ACTS:
                self.finished = "victory"
                return
            self._grow_side()
            self.route = generate_route(self.rng, self.act)
            self.layer = -1
            self.node = None
            self.visited = set()
        self.shop = []
        self.event = None

    # -- rewards
    def unknown_patterns(self):
        return [pt for pt in PATTERN_ORDER if pt not in self.player.patterns]

    def reward_options(self):
        """Three rewards (four after a clean sort). If the Set you just beat
        used a pattern you don't know, learning it is always one of them."""
        n = 4 if self.grade and self.grade["name"] == "Clean" else 3
        pool = []
        fixed = []
        unknown = self.unknown_patterns()
        seen = [pt for pt in unknown if pt in self.last_patterns]
        if seen:
            fixed.append(_pattern_option(seen[0]))
        elif unknown and self.rng.random() < 0.35:
            fixed.append(_pattern_option(self.rng.choice(unknown)))
        owned = set(self.relics)
        relics = [r for r in RELICS if r not in owned]
        self.rng.shuffle(relics)
        facet = lambda r: {"id": "relic:" + r, "label": "Facet: " + RELICS[r]["name"],
                           "desc": "Lasting: " + RELICS[r]["desc"]}
        if self.last_kind == "elite" and relics:
            fixed.append(facet(relics.pop()))           # a Hard Set always leaves a facet
        for r in relics[:2]:
            pool.append(facet(r))
        color = min(PRIMARIES, key=lambda c: self.player.cap[c])
        cap = self.player.cap[color]
        pool.append({"id": "cap:" + color, "label": "Deeper %s" % COLOR_NAMES[color],
                     "desc": "Hold one more %s charge (max %d -> %d)." % (COLOR_NAMES[color], cap,
                                                                         cap + 1)})
        pool.append({"id": "maxhp", "label": "Thick Edge", "desc": "+3 max HP, and heal 3."})
        pool.append({"id": "heal", "label": "Warm Light", "desc": "Heal 6 HP."})
        self.rng.shuffle(pool)
        return fixed + pool[:n - len(fixed)]

    def apply_reward(self, opt):
        rid = opt["id"]
        p = self.player
        if rid.startswith("relic:"):
            self._grant_relic(rid.split(":", 1)[1])
        elif rid.startswith("cap:"):
            c = rid.split(":", 1)[1]
            p.cap[c] += 1
        elif rid == "maxhp":
            p.max_hp += 3
            p.hp = min(p.max_hp, p.hp + 3)
        elif rid == "heal":
            p.hp = min(p.max_hp, p.hp + 6)
        elif rid.startswith("pattern:"):
            pt = rid.split(":", 1)[1]
            if pt not in PATTERNS:
                raise ValueError("unknown pattern %r" % pt)
            if pt not in p.patterns:
                p.patterns.append(pt)
        else:
            raise ValueError("unknown reward %r" % rid)

    def _grant_relic(self, rid):
        if rid in self.relics:
            return False
        self.relics.append(rid)
        for k, v in RELICS[rid]["mods"].items():
            self.player.mods[k] += v
        return True

    # -- shop
    def _make_shop(self):
        """Wares: `name` and `desc` are what the Tinter's counter shows;
        `label` is the one-line version used in messages."""
        items = [
            {"id": "heal", "name": "Warm Light", "desc": "A jar of it. Heal 6 HP.", "cost": 12},
            {"id": "maxhp", "name": "Thick Edge", "desc": "Harder to crack: +3 max HP.", "cost": 30},
        ]
        color = self.rng.choice(PRIMARIES)
        items.append({"id": "cap:" + color, "name": "Deeper %s" % COLOR_NAMES[color],
                      "desc": "Hold one more %s charge." % COLOR_NAMES[color].lower(), "cost": 25})
        relics = [r for r in RELICS if r not in self.relics]
        if relics:
            r = self.rng.choice(relics)
            items.append({"id": "relic:" + r, "name": RELICS[r]["name"],
                          "desc": "A facet. " + RELICS[r]["desc"], "cost": 45})
        unknown = self.unknown_patterns()
        if unknown:
            pt = self.rng.choice(unknown)
            items.append({"id": "pattern:" + pt, "name": "Learn %s" % PATTERNS[pt]["name"],
                          "desc": "A new pattern. " + PATTERNS[pt]["desc"], "cost": 40})
        for it in items:
            it["label"] = it["name"]
        return items

    def buy(self, index):
        if index < 0 or index >= len(self.shop):
            return False, "No such item."
        item = self.shop[index]
        if item.get("sold"):
            return False, "Already sold."
        if self.gold < item["cost"]:
            return False, "Not enough glint (%d needed)." % item["cost"]
        self.gold -= item["cost"]
        item["sold"] = True
        self.apply_reward({"id": item["id"]})
        return True, "Bought %s." % item["label"]

    # -- rest
    def rest(self, choice):
        p = self.player
        if choice == "heal":
            amount = max(1, (p.max_hp * 4) // 10)
            p.hp = min(p.max_hp, p.hp + amount)
            return "Healed %d." % amount
        if choice == "focus":
            c = min(PRIMARIES, key=lambda col: p.cap[col])
            p.cap[c] += 1
            return "%s cap is now %d." % (COLOR_NAMES[c], p.cap[c])
        raise ValueError("unknown rest choice %r" % choice)

    # -- events
    def make_event(self, event=None, variant=None):
        """Pick an Oddity (or use `event`), choose gift or deal by floor, and
        settle everything the choices refer to: which colour is "low", which
        facets are on offer. Returns the event as it will be shown."""
        ev = event or self.rng.choice(EVENTS)
        if variant is None:
            variant = "gift" if self.rng.random() < GIFT_CHANCE.get(self.act, 0.15) else "deal"
        p = self.player
        low = min(PRIMARIES, key=lambda c: p.cap[c])
        high = max((c for c in PRIMARIES if c != low), key=lambda c: p.cap[c])   # never the same one
        facets = [r for r in RELICS if r not in self.relics]
        self.rng.shuffle(facets)

        def settle(eff):
            if eff[0] == "cap":
                return ("cap", low if eff[1] == "low" else high, eff[2])
            if eff[0] == "facet":
                if eff[1] < len(facets):
                    return ("facet", facets[eff[1]])
                return ("maxhp", 3)                  # every facet owned: a thicker edge instead
            if eff[0] == "gamble":
                return ("gamble", eff[1], [settle(e) for e in eff[2]], [settle(e) for e in eff[3]])
            return eff

        choices = [(cid, label, [settle(e) for e in effs]) for cid, label, effs in ev[variant]]
        return {"id": ev["id"], "title": ev["title"], "variant": variant, "choices": choices}

    def _check(self, effects):
        """Raise ValueError if these effects can't be paid for right now."""
        p = self.player
        for eff in effects:
            if eff[0] == "glint" and eff[1] < 0 and self.gold < -eff[1]:
                raise ValueError("Not enough glint (%d needed)." % -eff[1])
            if eff[0] == "hp" and p.hp + eff[1] < 1:
                raise ValueError("Too cracked for that: it would take %d HP." % -eff[1])

    def _apply(self, effects):
        p = self.player
        for eff in effects:
            kind = eff[0]
            if kind == "heal":
                p.hp = min(p.max_hp, p.hp + eff[1])
            elif kind == "hp":
                p.hp = max(1, p.hp + eff[1])
            elif kind == "maxhp":
                p.max_hp = max(1, p.max_hp + eff[1])
                p.hp = max(1, min(p.max_hp, p.hp + max(0, eff[1])))
            elif kind == "cap":
                p.cap[eff[1]] = max(1, p.cap[eff[1]] + eff[2])
                p.palette[eff[1]] = min(p.palette[eff[1]], p.cap[eff[1]])
            elif kind == "glint":
                self.gold += eff[1]
            elif kind == "facet":
                self._grant_relic(eff[1])

    def resolve_event(self, choice):
        """Do what the choice says. Returns a message; raises ValueError for a
        choice you can't pay for (nothing happens then)."""
        found = [c for c in self.event["choices"] if c[0] == choice]
        if not found:
            raise ValueError("unknown event choice %r" % choice)
        effects = found[0][2]
        if not effects:
            return "You click onward."
        self._check(effects)
        self.event_outcome = {"ok": True, "effects": effects}
        done = []
        for eff in effects:
            if eff[0] == "gamble":
                self._check(eff[3])
                won = self.rng.random() < eff[1]
                branch = eff[2] if won else eff[3]
                self._apply(branch)
                self.event_outcome = {"ok": won, "effects": branch}
                done += branch
            else:
                self._apply([eff])
                done.append(eff)
        return effects_text(done)
