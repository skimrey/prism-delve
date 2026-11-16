"""Run state: the route through three acts, rewards, shops, rests, events."""

import json
import os
import random

from .consts import PRIMARIES, RELICS, COLOR_NAMES
from .dungeon import build_combat, generate_route
from .state import Player

ACTS = 3

EVENTS = [
    {"id": "altar", "title": "Prismatic Altar",
     "text": "A cracked altar hums with light. It asks for blood.",
     "choices": [("blood", "Offer 3 HP for a relic"), ("leave", "Walk away")]},
    {"id": "trader", "title": "Wandering Trader",
     "text": "A hooded trader eyes your pockets.",
     "choices": [("buy", "Pay 10 gold: heal 6"), ("steal", "Try to steal (50%): +20 gold or -4 HP"),
                 ("leave", "Walk away")]},
    {"id": "well", "title": "Colour Well",
     "text": "Pools of liquid colour swirl in a stone basin.",
     "choices": [("drink", "Drink: +1 cap on your lowest colour"), ("bathe", "Bathe: heal 5"),
                 ("leave", "Walk away")]},
]


class Meta:
    """Tiny persistent record across runs."""

    def __init__(self, path=None):
        self.path = path
        self.data = {"runs": 0, "wins": 0, "best_act": 0}
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


class Run:
    def __init__(self, seed=None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.player = Player()
        self.act = 1
        self.gold = 0
        self.relics = []
        self.route = generate_route(self.rng, 1)
        self.layer = -1
        self.node = None
        self.visited = set()           # (layer, index) of nodes entered this act
        self.state = None
        self.finished = None           # None | "victory" | "defeat"
        self.shop = []
        self.event = None

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
            self.state = build_combat(self.rng, self.act, node.kind, self.player)
        elif node.kind == "shop":
            self.shop = self._make_shop()
        elif node.kind == "event":
            self.event = self.rng.choice(EVENTS)
        return node

    def current_kind(self):
        return self.route.layers[self.layer][self.node].kind

    def finish_combat(self, victory):
        """Call when a fight ends. Returns gold earned."""
        kind = self.current_kind()
        self.state = None
        if not victory:
            self.finished = "defeat"
            return 0
        gold = 10 + 5 * self.act + (10 if kind == "elite" else 0) + (20 if kind == "boss" else 0)
        self.gold += gold
        return gold

    def leave_node(self):
        """Advance after a node is fully resolved (rewards taken etc)."""
        if self.current_kind() == "boss":
            self.act += 1
            if self.act > ACTS:
                self.finished = "victory"
                return
            self.route = generate_route(self.rng, self.act)
            self.layer = -1
            self.node = None
            self.visited = set()
        self.shop = []
        self.event = None

    # -- rewards
    def reward_options(self):
        pool = []
        owned = set(self.relics)
        relics = [r for r in RELICS if r not in owned]
        self.rng.shuffle(relics)
        for r in relics[:2]:
            pool.append({"id": "relic:" + r, "label": RELICS[r]["name"], "desc": RELICS[r]["desc"]})
        color = min(PRIMARIES, key=lambda c: self.player.cap[c])
        pool.append({"id": "cap:" + color, "label": "%s Reservoir" % COLOR_NAMES[color],
                     "desc": "+1 %s charge cap." % COLOR_NAMES[color]})
        pool.append({"id": "maxhp", "label": "Heartwood", "desc": "+3 max HP and heal 3."})
        pool.append({"id": "heal", "label": "Rest Stop", "desc": "Heal 6 HP."})
        self.rng.shuffle(pool)
        return pool[:3]

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
        items = [
            {"id": "heal", "label": "Bandage (heal 6)", "cost": 12},
            {"id": "maxhp", "label": "Heartwood (+3 max HP)", "cost": 30},
        ]
        color = self.rng.choice(PRIMARIES)
        items.append({"id": "cap:" + color,
                      "label": "%s Reservoir (+1 cap)" % COLOR_NAMES[color], "cost": 25})
        relics = [r for r in RELICS if r not in self.relics]
        if relics:
            r = self.rng.choice(relics)
            items.append({"id": "relic:" + r, "label": RELICS[r]["name"] + ": " + RELICS[r]["desc"],
                          "cost": 45})
        return items

    def buy(self, index):
        if index < 0 or index >= len(self.shop):
            return False, "No such item."
        item = self.shop[index]
        if item.get("sold"):
            return False, "Already sold."
        if self.gold < item["cost"]:
            return False, "Not enough gold (%d needed)." % item["cost"]
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
    def resolve_event(self, choice):
        """Returns a message. Raises ValueError for choices that cannot be afforded."""
        p = self.player
        ev = self.event["id"]
        if choice == "leave":
            return "You walk on."
        if ev == "altar" and choice == "blood":
            if p.hp <= 3:
                raise ValueError("Too weak to pay the price.")
            relics = [r for r in RELICS if r not in self.relics]
            if not relics:
                return "The altar is silent. You have everything it offers."
            p.hp -= 3
            r = self.rng.choice(relics)
            self._grant_relic(r)
            return "Lost 3 HP. Gained %s." % RELICS[r]["name"]
        if ev == "trader" and choice == "buy":
            if self.gold < 10:
                raise ValueError("Not enough gold.")
            self.gold -= 10
            p.hp = min(p.max_hp, p.hp + 6)
            return "Paid 10 gold and healed 6."
        if ev == "trader" and choice == "steal":
            if self.rng.random() < 0.5:
                self.gold += 20
                return "Got away with 20 gold."
            p.hp = max(1, p.hp - 4)
            return "Caught! Lost 4 HP."
        if ev == "well" and choice == "drink":
            c = min(PRIMARIES, key=lambda col: p.cap[col])
            p.cap[c] += 1
            return "%s cap is now %d." % (COLOR_NAMES[c], p.cap[c])
        if ev == "well" and choice == "bathe":
            p.hp = min(p.max_hp, p.hp + 5)
            return "Healed 5."
        raise ValueError("unknown event choice %r" % choice)
