"""The application shell: window, screen stack and the flow between screens."""

import os
import random
import sys
import zlib

import pygame

from . import dev, settings, sound
from .consts import FLOORS
from .node_screens import EndScreen, EventScreen, RestScreen, RewardScreen, ShopScreen
from .run import Meta, Run, load_run, route_signature, save_run
from .combat_ui import BoardKeyScreen, CombatScreen
from .screens import RouteScreen, TitleScreen
from .meadow import MeadowScreen
from .story import AscendScreen, RescueScreen, RollScreen, StoryScreen

DEFAULT_META = os.path.join(os.path.expanduser("~"), ".prism_delve", "meta.json")


class App:
    def __init__(self, size=(960, 640), meta_path=None, seed=None, tips=True, dev=False):
        pygame.mixer.pre_init(22050, -16, 1, 512)     # small and mono: every sound is synthesized
        pygame.init()
        pygame.font.init()
        self.size = size
        self.meta = Meta(meta_path)
        settings.load(self.meta.data.get("settings"))
        self.surface = self._open_window()
        pygame.display.set_caption("Prism Delve")
        sound.init()
        sound.warm()
        self.seed = seed
        self.tips = tips            # first-time explanations (the board key on your first fight)
        self.dev = dev              # testing mode: see dev.py
        self.run = None
        self.hub_rescued = None     # dev mode: pretend these towers' friends are out (see dev.py)
        self.recorded = False
        self.running = True
        self.dirty = True
        self.stack = [TitleScreen(self)]
        self.clock = pygame.time.Clock()

    def _open_window(self):
        flags = pygame.FULLSCREEN | pygame.SCALED if settings.SETTINGS["fullscreen"] else 0
        try:
            return pygame.display.set_mode(self.size, flags)
        except pygame.error:
            settings.SETTINGS["fullscreen"] = False
            return pygame.display.set_mode(self.size)

    def apply_settings(self, refresh_window=False):
        """Save the settings, and apply the ones that need it."""
        self.meta.data["settings"] = dict(settings.SETTINGS)
        self.meta.save()
        if refresh_window:
            self.surface = self._open_window()
        if not settings.SETTINGS["sound"]:
            sound.roll(0)
        self.dirty = True

    # -- saving between rooms
    @property
    def save_path(self):
        if not self.meta.path:
            return None
        return os.path.join(os.path.dirname(self.meta.path) or ".", "run.json")

    def autosave(self):
        """On the floor map, the run is saved: quit any time and Continue later."""
        if self.save_path and self.run is not None and not self.run.finished:
            save_run(self.run, self.save_path)

    def clear_save(self):
        if self.save_path and os.path.exists(self.save_path):
            os.remove(self.save_path)

    def has_save(self):
        return bool(self.save_path and os.path.exists(self.save_path))

    def continue_run(self):
        run = load_run(self.save_path) if self.has_save() else None
        if run is None:
            self.clear_save()
            self.to_title()
            return
        self.run = run
        if run.tower:
            from .world import your_sides
            run.sides = your_sides(self.meta.data)
        self.recorded = False
        self.replace(RouteScreen(self, "Welcome back."))

    # -- screen stack
    @property
    def screen(self):
        return self.stack[-1]

    def push(self, screen):
        self.stack.append(screen)
        self.dirty = True

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()
        self.dirty = True

    def replace(self, screen):
        sound.roll(0)                 # the rolling hum belongs to the screen that made it
        self.stack = [screen]
        self.dirty = True

    # -- flow
    def quit(self):
        self.running = False

    def to_title(self):
        self.replace(TitleScreen(self))

    def start_run(self):
        """Title -> New Run. The story plays once, the first time. Once you've
        reached a higher floor, you can slot in at any floor you've reached."""
        if not self.meta.data.get("seen_intro"):
            self.replace(StoryScreen(self, then=self.new_run))
        elif self.floors_reached() > 1:
            from .screens import FloorPickScreen
            self.replace(FloorPickScreen(self))
        else:
            self.new_run()

    def floors_reached(self):
        """How high in the Sorter you've been (1-3; all three once you've rolled out)."""
        d = self.meta.data
        return 3 if d.get("wins", 0) else max(1, min(3, d.get("best_act", 1)))

    def show_intro(self):
        self.replace(StoryScreen(self, then=self.to_title))

    def new_run(self, act=1):
        """A fresh climb of the Sorter from floor `act` (1: the bottom). Starting
        higher, you're grown as if you'd beaten the Keepers below (their sides,
        their patterns), with a little glint for the rooms you skipped."""
        self.run = Run(self.seed)
        if act > 1:
            from .dungeon import generate_route
            self.run.grow_to(act)
            self.run.route = generate_route(self.run.rng, act)
            self.run.gold += 45 * (act - 1)
        self.recorded = False
        self.autosave()
        self.replace(RouteScreen(self, "You slot in at the %s." % FLOORS[act]["name"] if act > 1 else ""))

    def abandon_run(self):
        self.run.finished = "defeat"
        self.end_run()

    def enter_node(self, idx):
        self.show_node(self.run.enter(idx))

    def show_node(self, node):
        """Open the screen for a node the run has already entered."""
        if node.kind in ("fight", "elite", "boss"):
            self.replace(CombatScreen(self, self.run))
            if self.tips and not self.meta.data.get("seen_board_key"):
                self.push(BoardKeyScreen(self))
        elif node.kind == "shop":
            self.replace(ShopScreen(self))
        elif node.kind == "rest":
            self.replace(RestScreen(self))
        else:
            self.replace(EventScreen(self))

    def combat_won(self):
        st = self.run.state
        gold = self.run.finish_combat(True, turns=st.turn, par=getattr(st, "par", None))
        self.replace(RewardScreen(self, gold))

    def combat_lost(self):
        self.run.finish_combat(False)
        self.end_run()

    def leave_node(self):
        was_boss = self.run.current_kind() == "boss"
        self.run.leave_node()
        if self.run.finished == "victory":
            self.record()
            self.replace(RollScreen(self))
        elif self.run.finished == "rescued":
            self.record()
            self.replace(RescueScreen(self))
        elif self.run.finished:
            self.end_run()
        elif was_boss:
            if not self.run.tower and self.run.act > self.meta.data.get("best_act", 1):
                self.meta.data["best_act"] = min(3, self.run.act)   # a floor reached: you can start there now
                self.meta.save()
            self.autosave()
            self.replace(AscendScreen(self))
        else:
            self.autosave()
            self.replace(RouteScreen(self))

    def enter_floor(self):
        """After growing a side: the map of the next floor."""
        self.replace(RouteScreen(self, "You climbed to the %s." % FLOORS[self.run.act]["name"]))

    def record(self):
        self.clear_save()
        if self.recorded:
            return
        self.recorded = True
        if self.run.tower:                 # a tower in the Meadow: what counts is who you reached
            if self.run.finished == "rescued":
                friends = self.meta.data.setdefault("friends", [])
                if self.run.tower not in friends:
                    friends.append(self.run.tower)
                climbs = self.meta.data.setdefault("tower_climbs", {})
                climbs[self.run.tower] = climbs.get(self.run.tower, 0) + 1
                self.meta.save()
            return
        self.meta.record(min(self.run.act, 3), self.run.finished == "victory")

    def end_run(self):
        self.record()
        self.show_end()

    def show_meadow(self):
        """After the Long Ramp: the one place with no grid and no points."""
        self.replace(MeadowScreen(self))

    def hub_open(self):
        """The Meadow opens as a hub once you've rolled out of the Sorter."""
        return self.dev or self.meta.data.get("wins", 0) > 0

    def show_hub(self, start_x=None, back_from=None):
        self.replace(MeadowScreen(self, hub=True, start_x=start_x, back_from=back_from))

    def show_game(self, game, theme="meadow", home_x=None):
        """A host in the Meadow hub has talked you into its game (in its
        zone's colours). Back to the host after, who asks for another go."""
        from .meadow import HOST_X
        home_x = home_x if home_x is not None else (HOST_X if theme == "meadow" else None)
        key = "%s:%s" % (game, theme)

        def back():
            self.show_hub(start_x=(home_x - 60) if home_x else None, back_from=key)
        if game == "rolloff":
            from .rolloff import RollOffScreen, rivals
            self.replace(RollOffScreen(self, rivals(self.meta.data.get("friends", [])), back=back, theme=theme))
        elif game == "pinball":
            from .pinball import PinballScreen
            self.replace(PinballScreen(self, back=back, theme=theme))
        else:
            import importlib
            from .world import GAMES
            _name, module, cls = GAMES[game]
            screen = getattr(importlib.import_module("." + module, "prism"), cls)
            self.replace(screen(self, back=back, theme=theme if theme != "meadow" else None))

    def show_rolloff(self):
        self.show_game("rolloff", "meadow")

    def show_pinball(self, theme="wilds"):
        """The Side Show (the Wilds' game, unless a theme says otherwise)."""
        from .world import World, plan_of
        world = World(plan_of(self.meta.data), self.meta.data.get("friends", []) if self.hub_rescued is None
                      else self.hub_rescued)
        zone = next((z for z in world.zones if z.kind == theme), None)
        self.show_game("pinball", theme, zone.host_x if zone else None)

    def enter_tower(self, tower):
        """Through a window in the Meadow: a climb up another tower, as a circle.
        The first time, three cards say who asked, what's different, and who's in the way."""
        if tower not in self.meta.data.get("towers_seen", []):
            from .story import TowerIntroScreen
            self.replace(TowerIntroScreen(self, tower, then=lambda: self.climb_tower(tower)))
        else:
            self.climb_tower(tower)

    def climb_tower(self, tower):
        """Up a tower. Any tower you've reached, as often as you like: every
        climb is freshly generated (a new seed, and never the same route as
        last time), with the same twists, the same difficulty for its place
        in your world, and every fight checked by the solver as usual."""
        from .world import plan_of, your_sides
        data = self.meta.data
        plan = plan_of(data)
        out = data.get("friends", []) if self.hub_rescued is None else self.hub_rescued
        visits = data.setdefault("tower_visits", {})
        visits[tower] = visits.get(tower, 0) + 1
        last = data.setdefault("tower_routes", {})
        position = plan.index(tower) if tower in plan else None
        run = None
        for attempt in range(12):
            if self.seed is None:
                seed = random.randrange(1 << 30)
            else:                                        # a fixed --seed: still a new climb every visit
                seed = (self.seed * 7919 + zlib.crc32(tower.encode()) + visits[tower] * 104729 + attempt) % (1 << 30)
            run = Run(seed, tower=tower, position=position)
            if route_signature(run.route) != last.get(tower):
                break
        last[tower] = route_signature(run.route)
        self.meta.save()
        self.run = run
        self.run.again = tower in out                    # its friend's already out: just climbing for fun
        self.run.sides = your_sides(data, self.hub_rescued)
        self.recorded = False
        self.autosave()
        words = ("Back in through the window. The floors have all shuffled since." if self.run.again
                 else "In through the window. Now up to the one who asked.")
        self.replace(RouteScreen(self, words))

    def show_end(self):
        self.replace(EndScreen(self))

    # -- loop
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
            return
        if self.dev and ev.type == pygame.KEYDOWN and ev.key in dev.HOTKEYS:
            if dev.hotkey(self, ev.key):
                self.dirty = True
                return
        self.screen.handle(ev)

    def tick(self, dt):
        if self.screen.update(dt):
            self.dirty = True

    def draw(self):
        self.screen.draw(self.surface)
        if self.dev:
            dev.draw_badge(self.surface)
        self.dirty = False

    def screenshot(self, path):
        self.draw()
        pygame.image.save(self.surface, path)

    def loop(self):
        while self.running:
            for ev in pygame.event.get():
                self.handle(ev)
            self.tick(min(0.1, self.clock.tick(30) / 1000.0))
            if self.dirty:
                self.draw()
                pygame.display.flip()
        pygame.quit()


def main(argv=None):
    """python -m prism [--seed=N] [--dev [--floor=N] [--room=KIND | --scene=NAME]]"""
    argv = argv if argv is not None else sys.argv[1:]
    seed = None
    for a in argv:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
    is_dev = "--dev" in argv
    app = App(meta_path=DEFAULT_META, seed=seed, dev=is_dev)
    if is_dev:
        dev.apply_cli(app, argv)
    app.loop()


if __name__ == "__main__":
    main()
