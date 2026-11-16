"""The application shell: window, screen stack and the flow between screens."""

import os
import sys

import pygame

from .node_screens import EndScreen, EventScreen, RestScreen, RewardScreen, ShopScreen
from .run import Meta, Run
from .screens import CombatScreen, RouteScreen, TitleScreen

DEFAULT_META = os.path.join(os.path.expanduser("~"), ".prism_delve", "meta.json")


class App:
    def __init__(self, size=(960, 640), meta_path=None, seed=None):
        pygame.init()
        pygame.font.init()
        self.size = size
        self.surface = pygame.display.set_mode(size)
        pygame.display.set_caption("Prism Delve")
        self.fonts = {s: pygame.font.Font(None, s) for s in (18, 22, 26, 32, 44, 72)}
        self.meta = Meta(meta_path)
        self.seed = seed
        self.run = None
        self.recorded = False
        self.running = True
        self.dirty = True
        self.stack = [TitleScreen(self)]
        self.clock = pygame.time.Clock()

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
        self.stack = [screen]
        self.dirty = True

    # -- flow
    def quit(self):
        self.running = False

    def to_title(self):
        self.replace(TitleScreen(self))

    def new_run(self):
        self.run = Run(self.seed)
        self.recorded = False
        self.replace(RouteScreen(self))

    def abandon_run(self):
        self.run.finished = "defeat"
        self.end_run()

    def enter_node(self, idx):
        node = self.run.enter(idx)
        if node.kind in ("fight", "elite", "boss"):
            self.replace(CombatScreen(self, self.run))
        elif node.kind == "shop":
            self.replace(ShopScreen(self))
        elif node.kind == "rest":
            self.replace(RestScreen(self))
        else:
            self.replace(EventScreen(self))

    def combat_won(self):
        gold = self.run.finish_combat(True)
        self.replace(RewardScreen(self, gold))

    def combat_lost(self):
        self.run.finish_combat(False)
        self.end_run()

    def leave_node(self):
        was_boss = self.run.current_kind() == "boss"
        self.run.leave_node()
        if self.run.finished:
            self.end_run()
        else:
            self.replace(RouteScreen(self, "Act %d begins." % self.run.act if was_boss else ""))

    def end_run(self):
        if not self.recorded:
            self.meta.record(min(self.run.act, 3), self.run.finished == "victory")
            self.recorded = True
        self.replace(EndScreen(self))

    # -- loop
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
            return
        self.screen.handle(ev)

    def tick(self, dt):
        if self.screen.update(dt):
            self.dirty = True

    def draw(self):
        self.screen.draw(self.surface)
        self.dirty = False

    def screenshot(self, path):
        self.draw()
        pygame.image.save(self.surface, path)

    def loop(self):
        while self.running:
            for ev in pygame.event.get():
                self.handle(ev)
            self.tick(self.clock.tick(30) / 1000.0)
            if self.dirty:
                self.draw()
                pygame.display.flip()
        pygame.quit()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    seed = None
    for a in argv:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
    App(meta_path=DEFAULT_META, seed=seed).loop()


if __name__ == "__main__":
    main()
