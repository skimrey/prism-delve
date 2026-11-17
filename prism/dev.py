"""Testing mode: `python -m prism --dev`.

Adds a Dev menu to the title screen (jump to any floor, room, Keeper or story
scene, with cheats), a DEV badge in the corner, and hotkeys that work on any
screen:

    F1  dev menu            F6  climb to the next floor (as if you beat the Keeper)
    F2  win this fight      F7  learn every pattern
    F3  lose this fight     F8  +100 glint
    F4  skip to the Keeper  F9  heal to full (and +20 max HP)

The menu has two tabs: the Sorter (floors, rooms, story scenes) and the
Meadow & towers (where in the hub to start, which towers' friends to pretend
you've rescued, each tower's climb, intro, Keeper fight and rescue, and the
Meadow's games).

Command line jumps (with --dev): --floor=1..3 --room=fight|elite|boss|shop|rest|event
--scene=story|ascend|roll|meadow|sorted|rolled|hub|wilds|tower|towerintro|towerboss|rescue|finale|<game>
[--tower=leaning|hollow] [--at=X (where in the hub)] [--rescued=leaning,hollow|none]
and --event=polisher|well|trader [--variant=gift|deal].
"""

import pygame

from .consts import PATTERN_ORDER, RELICS
from .dungeon import generate_route
from .run import Run
from .scene import TITLE_SKY, Backdrop, heading
from .screens import RouteScreen, Screen
from .widgets import DIM, GOOD, INK, draw_card, draw_text, font

ROOMS = (("fight", "The Set"), ("elite", "Hard Set"), ("boss", "Keeper"), ("shop", "Tinter"),
         ("rest", "Still Tile"), ("event", "Oddity"))
SCENES = (("story", "Intro story"), ("ascend", "Grow a side"), ("roll", "The roll"),
          ("meadow", "Meadow epilogue"), ("sorted", "End: sorted"), ("rolled", "End: rolled"))
# the Meadow & towers tab
TOWER_SCENES = (("tower", "Climb"), ("towerintro", "Intro"), ("towerboss", "Keeper"),
                ("rescue", "Rescue"))
GAMES = (("rolloff", "Roll-Off"), ("pinball", "Side Show"), ("sporedrop", "Spore Drop"), ("curl", "Curl"),
         ("duneputt", "Dune Putt"), ("glimmerpop", "Glimmer Pop"), ("beachbowl", "Beach Bowl"),
         ("skyball", "Sky Ball"))
HOTKEYS = {pygame.K_F1: "menu", pygame.K_F2: "win", pygame.K_F3: "lose", pygame.K_F4: "keeper",
           pygame.K_F6: "climb", pygame.K_F7: "patterns", pygame.K_F8: "glint", pygame.K_F9: "heal"}


def start_run_at(app, act, tough=False, patterns=False, facets=False, glint=0):
    """A fresh run that starts on floor `act`, grown as if you had climbed there."""
    run = Run(app.seed).grow_to(act)
    run.route = generate_route(run.rng, act)
    _cheats(run, tough, patterns, facets, glint)
    app.run = run
    app.recorded = False
    return run


def _cheats(run, tough=False, patterns=False, facets=False, glint=0):
    if tough:
        run.player.max_hp = run.player.hp = 99
    if patterns:
        run.player.patterns = list(PATTERN_ORDER)
    if facets:
        for rid in RELICS:
            run._grant_relic(rid)
    run.gold += glint


def jump_to_room(app, act, kind, **kw):
    run = start_run_at(app, act, **kw)
    # late on the floor, so the shapes are the ones that floor really uses
    run.layer = len(run.route.layers) - 3
    run.node = 0
    run.route.layers[run.layer + 1][0].kind = kind
    run.route.layers[run.layer][0].nexts = [0]
    app.enter_node(0)


def jump_to_scene(app, act, scene, tower="leaning", at=None, **kw):
    from .story import AscendScreen, RollScreen, StoryScreen
    run = start_run_at(app, max(act, 2) if scene == "ascend" else act, **kw)
    if scene == "story":
        app.replace(StoryScreen(app, then=app.to_title))
    elif scene == "ascend":
        app.replace(AscendScreen(app))
    elif scene == "roll":
        run.finished = "victory"
        app.replace(RollScreen(app))
    elif scene == "meadow":
        run.finished = "victory"
        app.show_meadow()
    elif scene == "hub":
        app.show_hub(start_x=at)
    elif scene == "wilds":
        open_wilds(app)
        app.show_hub(start_x=at or 5190)
    elif scene == "tower":
        app.climb_tower(tower)
        _cheats(app.run, **kw)
    elif scene == "towerboss":                  # straight to the tower's Keeper
        app.climb_tower(tower)
        run = app.run
        _cheats(run, **kw)
        layers = run.route.layers
        run.layer, run.node = len(layers) - 2, 0
        layers[run.layer][0].nexts = [0]
        app.enter_node(0)
    elif scene == "towerintro":
        from .story import TowerIntroScreen
        app.replace(TowerIntroScreen(app, tower, then=lambda: jump_to_scene(app, act, "tower", tower, **kw)))
    elif scene in dict(GAMES):
        from .world import ZONES
        zone = next((k for k, z in ZONES.items() if z["game"] == scene), "meadow")
        app.show_game(scene, zone)
    elif scene == "finale":                     # the Grand Roll (everyone who asked is out)
        from .finale import FinaleScreen
        from .world import plan_of
        app.hub_rescued = list(plan_of(app.meta.data))
        app.replace(FinaleScreen(app, then=lambda: app.show_hub()))
    elif scene == "rescue":
        from .story import RescueScreen
        app.climb_tower(tower)
        _cheats(app.run, **kw)
        app.run.finished = "rescued"
        real = app.meta.data.get("friends", [])
        pretend = app.hub_rescued if app.hub_rescued is not None else real
        from .world import plan_of
        plan = plan_of(app.meta.data)
        before = plan[:plan.index(tower) + 1] if tower in plan else [tower]
        app.hub_rescued = sorted(set(pretend) | set(before))   # so the hub after shows them out
        app.replace(RescueScreen(app))
    else:
        run.finished = "victory" if scene == "rolled" else "defeat"
        app.show_end()


def open_wilds(app):
    """Dev: make sure the Wilds are open (pretend the hexagon is out)."""
    real = app.meta.data.get("friends", [])
    pretend = app.hub_rescued if app.hub_rescued is not None else real
    if "leaning" not in pretend:
        app.hub_rescued = sorted(set(pretend) | {"leaning"})


def hotkey(app, key):
    """Handle a dev hotkey. Returns True if it did something."""
    from .combat_ui import CombatScreen
    what = HOTKEYS.get(key)
    if what == "menu":
        app.push(DevScreen(app))
        return True
    run = app.run
    if run is None or run.finished:
        return False
    screen = app.screen
    if what in ("win", "lose") and isinstance(screen, CombatScreen) and screen.mode == "anim":
        screen.skip_anim()                # finish the turn first (it may even end the fight)
        screen = app.screen
    if what in ("win", "lose") and isinstance(screen, CombatScreen) and screen.mode == "plan":
        if what == "win":
            run.state.enemies.clear()
            run.state.outcome = "victory"
            app.combat_won()
        else:
            run.player.hp = 0
            run.state.outcome = "defeat"
            app.combat_lost()
        return True
    if what == "keeper" and isinstance(screen, RouteScreen) and screen.travel is None:
        layers = run.route.layers
        run.layer = len(layers) - 2
        run.node = 0
        layers[run.layer][0].nexts = [0]
        app.replace(RouteScreen(app, "DEV: the Keeper is next."))
        return True
    if what == "climb" and run.act < 3:
        run.layer, run.node = len(run.route.layers) - 1, 0
        app.leave_node()
        return True
    if what == "patterns":
        run.player.patterns = list(PATTERN_ORDER)
    elif what == "glint":
        run.gold += 100
    elif what == "heal":
        run.player.max_hp += 20
        run.player.hp = run.player.max_hp
    else:
        return False
    if isinstance(screen, CombatScreen):
        screen.refresh()
    return True


def draw_badge(surf):
    r = pygame.Rect(4, 618, 150, 20)
    pygame.draw.rect(surf, INK, r, border_radius=6)
    draw_text(surf, font(16), "DEV  F1 menu  F2 win", r.center, (255, 214, 72), center=True)


class DevScreen(Screen):
    """Pick a floor, then jump straight into any room or scene. A second tab
    does the Meadow hub, the towers and the games."""

    def __init__(self, app):
        super().__init__(app)
        self.backdrop = Backdrop(TITLE_SKY, seed=13, n=10)
        self.act = getattr(app.run, "act", 1) if app.run and not app.run.finished else 1
        self.opts = {"tough": False, "patterns": False, "facets": False, "glint": 0}
        self.tab = "sorter"
        self.tower = "leaning"                   # the tower the Meadow tab's buttons act on
        self.build()

    def build(self):
        self.buttons = []
        self.add((120, 96, 180, 34), "The Sorter", lambda: self.set_tab("sorter"), small=True,
                 active=self.tab == "sorter", tag="tab:sorter")
        self.add((306, 96, 220, 34), "Meadow & towers", lambda: self.set_tab("meadow"), small=True,
                 active=self.tab == "meadow", tag="tab:meadow", key=pygame.K_TAB)
        toggles = (("tough", "99 HP"), ("patterns", "Patterns"), ("facets", "Facets"))
        for i, (k, label) in enumerate(toggles):
            self.add((510 + i * 88, 140, 84, 36), label, lambda k=k: self.toggle(k),
                     active=bool(self.opts[k]), tag="opt:" + k, small=True)
        self.add((774, 140, 84, 36), "+200 glint", self.add_glint, tag="opt:glint", small=True,
                 active=self.opts["glint"] > 0)
        self.add((380, 588, 200, 40), "Back", self.app.pop, key=pygame.K_ESCAPE, tag="back")
        if self.tab == "sorter":
            self._build_sorter()
        else:
            self._build_meadow()

    def _build_sorter(self):
        for a in (1, 2, 3):
            self.add((120 + (a - 1) * 130, 140, 120, 36), "Floor %d" % a, lambda a=a: self.set_act(a),
                     active=self.act == a, tag="floor%d" % a, key=pygame.K_1 + a - 1)
        for i, (kind, label) in enumerate(ROOMS):
            self.add((120 + (i % 3) * 250, 230 + (i // 3) * 50, 240, 42), label,
                     lambda k=kind: jump_to_room(self.app, self.act, k, **self.opts), tag="room:" + kind)
        for i, (scene, label) in enumerate(SCENES):
            self.add((120 + (i % 3) * 250, 374 + (i // 3) * 44, 240, 38), label,
                     lambda s=scene: jump_to_scene(self.app, self.act, s, **self.opts), tag="scene:" + scene)

    def _build_meadow(self):
        from .consts import TOWER_ORDER, TOWERS
        from .world import ZONES, plan_of
        plan = plan_of(self.app.meta.data)
        now = self.app.hub_rescued
        # how many friends are out (= how many tower Keepers you've beaten), in your world's order
        self.add((120, 198, 86, 30), "Save", lambda: self.set_rescued(None), small=True,
                 active=now is None, tag="rescued:save")
        for k in range(len(plan) + 1):
            val = list(plan[:k])
            self.add((210 + k * 40, 198, 36, 30), str(k), lambda v=val: self.set_rescued(v), small=True,
                     active=now == val, tag="rescued:%d" % k)
        from . import world as W
        self.add((600, 198, 34, 30), "-", lambda: self.nudge_sides(-1), small=True, tag="sides-")
        self.add((638, 198, 34, 30), "+", lambda: self.nudge_sides(1), small=True, tag="sides+")
        self.add((676, 198, 52, 30), "auto", lambda: self.nudge_sides(None), small=True,
                 active=W.DEV_SIDES is None, tag="sides:auto")
        self.add((732, 198, 52, 30), "round", lambda: self.nudge_sides(0), small=True,
                 active=W.DEV_SIDES == 0, tag="sides:round")
        # the hub: its start, the Roll-Off, then the start of every zone in your plan's order
        self.add((120, 254, 92, 30), "Start", lambda: self.go_hub(160, 0), small=True, tag="hub:start")
        self.add((216, 254, 92, 30), "Roll-Off", lambda: self.go_hub(560, 0), small=True, tag="hub:rolloff")
        for k, tid in enumerate(plan):
            zone = ZONES[TOWERS[tid]["zone"]]["name"].replace("The ", "")
            self.add((312 + (k % 5) * 110, 254 + (k // 5) * 34, 106, 30), zone[:12],
                     lambda k=k: self.go_zone(k), small=True, tag="hub:zone%d" % k)
        # the towers: pick one, then climb it, see its intro, fight its Keeper, or watch its rescue
        for i, tid in enumerate(TOWER_ORDER):
            self.add((120 + (i % 4) * 186, 348 + (i // 4) * 30, 180, 27), TOWERS[tid]["name"].replace("The ", ""),
                     lambda t=tid: self.pick(t), small=True, active=self.tower == tid, tag="pick:" + tid)
        for i, (scene, label) in enumerate(TOWER_SCENES):
            self.add((120 + i * 120, 414, 114, 34), label,
                     lambda s=scene: jump_to_scene(self.app, 3, s, self.tower, **self.opts),
                     tag="scene:%s:%s" % (scene, self.tower))
        self.add((600, 414, 120, 34), "Gallery", self.gallery, tag="gallery")
        self.add((726, 414, 120, 34), "Finale", lambda: jump_to_scene(self.app, 3, "finale", **self.opts),
                 tag="scene:finale")
        for i, (game, label) in enumerate(GAMES):
            self.add((120 + (i % 4) * 104, 474 + (i // 4) * 30, 100, 27), label,
                     lambda g=game: jump_to_scene(self.app, 3, g, **self.opts), tag="scene:" + game, small=True)
        self.add((540, 474, 100, 27), "Hub", lambda: jump_to_scene(self.app, 3, "hub", **self.opts),
                 tag="scene:hub", small=True)
        opened = bool(getattr(self.app, "dev_open_zones", False))
        self.add((646, 474, 200, 27), "All zones open: %s" % ("on" if opened else "off"), self.toggle_open,
                 small=True, active=opened, tag="open_zones")

    def nudge_sides(self, d):
        """Dev: pretend you have this many sides (None: however many you've earned)."""
        from . import world as W
        if d is None or d == 0:
            W.DEV_SIDES = d
        else:
            cur = W.DEV_SIDES if W.DEV_SIDES not in (None, 0) else W.your_sides(self.app.meta.data,
                                                                               self.app.hub_rescued) or 40
            W.DEV_SIDES = max(3, min(60, cur + d * (1 if cur < 12 else 2)))
        self.build()

    def toggle_open(self):
        self.app.dev_open_zones = not getattr(self.app, "dev_open_zones", False)
        self.build()

    def pick(self, tid):
        self.tower = tid
        self.build()

    def gallery(self):
        from .gallery import GalleryScreen
        self.app.push(GalleryScreen(self.app, back=lambda: (self.app.pop(), self.build())))

    def go_zone(self, k):
        """The start of zone k in the plan (opening everything before it, dev only)."""
        from .world import World, plan_of
        plan = plan_of(self.app.meta.data)
        real = self.app.meta.data.get("friends", [])
        pretend = self.app.hub_rescued if self.app.hub_rescued is not None else real
        self.app.hub_rescued = sorted(set(pretend) | set(plan[:k]))
        world = World(plan, self.app.hub_rescued)
        x = world.zones[k].start + 300 if k else 3900
        jump_to_scene(self.app, 3, "hub", at=x, **self.opts)

    def set_tab(self, tab):
        self.tab = tab
        self.build()

    def set_rescued(self, val):
        self.app.hub_rescued = None if val is None else list(val)
        self.build()

    def go_hub(self, x, _zone=0):
        jump_to_scene(self.app, 3, "hub", at=x, **self.opts)

    def set_act(self, a):
        self.act = a
        self.build()

    def toggle(self, k):
        self.opts[k] = not self.opts[k]
        self.build()

    def add_glint(self):
        self.opts["glint"] += 200
        self.build()

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def draw(self, surf):
        self.backdrop.draw(surf)
        heading(surf, "DEV: jump anywhere", (480, 40), 44, center=True)
        draw_card(surf, (90, 84, 780, 494))
        if self.tab == "sorter":
            draw_text(surf, font(20), "Start on", (120, 184), DIM)
            draw_text(surf, font(22), "Jump into a room (the floor's late rooms, its real shapes)",
                      (120, 206), INK)
            draw_text(surf, font(22), "Or a scene", (120, 350), INK)
        else:
            from .consts import TOWERS, twist_name
            real = self.app.meta.data.get("friends", [])
            from . import world as W
            sides = W.your_sides(self.app.meta.data, self.app.hub_rescued)
            draw_text(surf, font(17), "Friends out / Keepers beaten (save: %d). Dev only, never saved." % len(real),
                      (120, 178), INK)
            draw_text(surf, font(17), "you: %s" % ("round" if not sides else "%d sides" % sides), (600, 178), INK)
            draw_text(surf, font(18), "Go to: the hub's start, the Roll-Off, or the start of a zone (opens it)",
                      (120, 234), INK)
            t = TOWERS[self.tower]
            twists = ", ".join(twist_name(w, self.tower) for w in t.get("twists", ())) or "no twist"
            draw_text(surf, font(18), "Towers: pick one, then jump in  (%s: tier %d, %s)" % (
                t["name"], t.get("tier", 1), twists), (120, 324), INK)
            draw_text(surf, font(16), "Games (one per zone)", (120, 454), INK)
        draw_text(surf, font(18), "Hotkeys anywhere: F2 win fight, F3 lose, F4 skip to Keeper, F6 next "
                  "floor, F7 patterns, F8 glint, F9 heal", (480, 552), DIM, center=True)
        if self.opts["glint"]:
            draw_text(surf, font(18), "+%d glint" % self.opts["glint"], (858, 182), GOOD, right=True)
        self.draw_buttons(surf)


def apply_cli(app, argv):
    """--floor / --room / --scene jumps, for the command line."""
    opts = dict(a[2:].split("=", 1) for a in argv if a.startswith("--") and "=" in a)
    act = max(1, min(3, int(opts.get("floor", 1))))
    if "event" in opts:                      # --event=polisher|well|trader [--variant=gift|deal]
        from .run import EVENTS
        ev = next((e for e in EVENTS if e["id"] == opts["event"]), None)
        if ev is not None:
            jump_to_room(app, act, "event")
            app.run.gold += 40
            app.run.event = app.run.make_event(ev, opts.get("variant"))
            from .node_screens import EventScreen
            app.replace(EventScreen(app))
            return
    if "rescued" in opts:                    # --rescued=leaning,hollow (or none)
        names = [n for n in opts["rescued"].split(",") if n and n != "none"]
        app.hub_rescued = names
    if "room" in opts:
        jump_to_room(app, act, opts["room"], tough="tough" in argv or "--tough" in argv)
    elif "scene" in opts:
        at = int(opts["at"]) if "at" in opts else None
        jump_to_scene(app, act, opts["scene"], opts.get("tower", "leaning"), at=at)
