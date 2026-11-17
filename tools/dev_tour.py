"""Launch the game in dev mode headlessly and visit every screen, saving a
screenshot of each to shots/. Fails loudly if anything breaks.

    ./.venv/bin/python tools/dev_tour.py            # -> shots/tour_*.png
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from prism import dev  # noqa: E402
from prism.app import App  # noqa: E402
from prism.run import EVENTS  # noqa: E402

OUT = os.path.join(ROOT, "shots")


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):                      # last tour's pictures, so none go stale
        if old.startswith("tour_") and old.endswith(".png"):
            os.remove(os.path.join(OUT, old))
    app = App(meta_path=os.path.join(OUT, "tour_meta.json"), seed=7, tips=True, dev=True)
    shots = []

    def snap(name, seconds=0.6):
        for _ in range(int(seconds / 0.05)):
            app.tick(0.05)
        path = os.path.join(OUT, "tour_%02d_%s.png" % (len(shots), name))
        app.screenshot(path)
        shots.append(path)

    def key(k):
        app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    snap("title", 1.0)
    key(pygame.K_F1)
    snap("dev_menu")
    for act in (1, 2, 3):
        for room in ("fight", "boss"):
            dev.jump_to_room(app, act, room)
            snap("floor%d_%s" % (act, room), 1.0)
            while type(app.screen).__name__ != "CombatScreen":       # first fight: the board key
                snap("floor%d_board_key" % act, 0.3)
                key(pygame.K_RETURN)
            cs = app.screen
            cs.banner = None
            cs.slot_hover = 1
            snap("floor%d_%s_beat2" % (act, room), 0.2)
            cs.slot_hover = None
            key(pygame.K_RETURN)
            snap("floor%d_%s_resolving" % (act, room), 1.2)
            key(pygame.K_F2)
            snap("floor%d_%s_reward" % (act, room), 0.8)
    from prism.node_screens import EventScreen
    for ev in EVENTS:
        for variant in ("gift", "deal"):
            dev.jump_to_room(app, 1, "event")
            app.run.gold = 40
            app.run.event = app.run.make_event(ev, variant)
            app.replace(EventScreen(app))
            snap("event_%s_%s" % (ev["id"], variant))
            app.screen.pick(app.run.event["choices"][0][0])
            snap("event_%s_%s_chosen" % (ev["id"], variant), 2.4)
    for room in ("rest", "shop"):
        dev.jump_to_room(app, 2, room)
        snap(room)
    for scene in ("story", "ascend", "roll", "meadow", "rolled", "sorted", "hub", "tower", "rescue"):
        dev.jump_to_scene(app, 3, scene)
        snap(scene, 2.0 if scene == "roll" else 1.2)
    from prism.consts import TOWER_ORDER
    for tid in TOWER_ORDER:                              # every tower: intro, a Keeper fight, the rescue
        dev.jump_to_scene(app, 3, "towerintro", tid)
        for page in range(3):
            snap("towerintro_%s_%d" % (tid, page), 2.0)
            key(pygame.K_RETURN)
        dev.jump_to_scene(app, 3, "towerboss", tid)
        app.screen.banner = None
        snap("tower_%s_keeper" % tid, 1.0)
        dev.jump_to_scene(app, 3, "rescue", tid)
        snap("rescue_%s_window" % tid, 1.0)
        snap("rescue_%s_down" % tid, 3.0)
        snap("rescue_%s_landed" % tid, 6.0)
    saved = app.hub_rescued
    dev.jump_to_scene(app, 3, "finale")                  # the Grand Roll, once everyone's out
    for name, secs in (("lineup", 1.0), ("ramp", 6.0), ("field", 5.0), ("wheel", 5.0), ("card", 6.0)):
        snap("finale_" + name, secs)
    app.hub_rescued = saved
    from prism.world import World, plan_of
    app.hub_rescued = list(TOWER_ORDER)                  # the whole hub, zone by zone
    world = World(plan_of(app.meta.data), app.hub_rescued)
    for z in world.zones:
        for dx in (300, 2600, z.wall - z.start - 500):
            dev.jump_to_scene(app, 3, "hub", at=z.start + dx)
            snap("hub_%s_%d" % (z.kind, dx), 0.6)
    app.hub_rescued = list(TOWER_ORDER[:3])              # partway: the map, and climbing a tower again
    dev.jump_to_scene(app, 3, "hub", at=world.zones[2].start + 300)
    key(pygame.K_m)
    snap("map", 0.4)
    app.pop()
    app.climb_tower("hollow")
    snap("again_route", 0.4)
    app.run.finished = "rescued"
    from prism.story import RescueScreen
    app.replace(RescueScreen(app))
    snap("again_window", 1.0)
    snap("again_down", 3.0)
    snap("again_landed", 6.0)
    from prism.screens import FloorPickScreen
    app.meta.data["best_act"] = 2
    app.replace(FloorPickScreen(app))                    # New Run: slot in at any floor you've reached
    snap("floor_pick", 0.4)
    from prism.world import GAMES, ZONES
    for zone, spec in ZONES.items():                     # every zone's game
        app.show_game(spec["game"], zone, 3000)
        snap("game_%s" % spec["game"], 0.4)
        key(pygame.K_SPACE)
        snap("game_%s_playing" % spec["game"], 1.6)
        app.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE, mod=0, unicode="", scancode=0))
        snap("game_%s_later" % spec["game"], 1.5)
    assert len(GAMES) == len(ZONES)
    for mode in ("bump", "tilt"):
        app.show_game("rolloff", "meadow")
        app.screen.start(mode)
        snap("rolloff_%s" % mode, 1.0)
    from prism.gallery import GalleryScreen
    app.push(GalleryScreen(app))
    snap("gallery", 0.3)
    app.pop()
    print("dev tour ok: %d screens -> %s" % (len(shots), OUT))


if __name__ == "__main__":
    main()
