"""Non-combat screens: reward, shop, rest, event and the end of a run."""

import pygame

from .consts import RELICS
from .screens import CardButton, Screen
from .widgets import ACCENT, BAD, BG, DIM, GOOD, TEXT, WARN, draw_text, draw_wrapped


class RewardScreen(Screen):
    def __init__(self, app, gold):
        super().__init__(app)
        self.run = app.run
        self.gold = gold
        self.picked = False
        self.options = self.run.reward_options()
        for i, opt in enumerate(self.options):
            self.buttons.append(CardButton((200, 190 + i * 90, 560, 76), opt["label"], opt["desc"],
                                           lambda o=opt: self.pick(o), key=pygame.K_1 + i,
                                           tag="reward%d" % i))
        self.cont = self.add((380, 500, 200, 44), "Continue", app.leave_node, enabled=False,
                             key=pygame.K_RETURN, tag="continue")
        self.skip = self.add((380, 450, 200, 36), "Skip reward", self.do_skip, tag="skip")
        self.say("Choose a reward (1-3), or skip.", DIM)

    def pick(self, opt):
        if self.picked:
            return
        self.run.apply_reward(opt)
        self.picked = True
        for b in self.buttons:
            if b.tag.startswith("reward"):
                b.enabled = False
        self.skip.enabled = False
        self.cont.enabled = True
        self.say("Took %s." % opt["label"], GOOD)

    def do_skip(self):
        if self.picked:
            return
        self.picked = True
        for b in self.buttons:
            if b.tag.startswith("reward"):
                b.enabled = False
        self.skip.enabled = False
        self.cont.enabled = True
        self.say("Skipped.", DIM)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[44], "Victory", (480, 70), GOOD, center=True)
        draw_text(surf, f[26], "+%d gold   (total %d)" % (self.gold, self.run.gold), (480, 120), WARN,
                  center=True)
        draw_text(surf, f[22], self.msg, (480, 160), self.msg_color, center=True)
        self.draw_buttons(surf)


class ShopScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.build()
        self.say("Spend your gold. Prices are fixed.", DIM)

    def build(self):
        self.buttons = []
        for i, item in enumerate(self.run.shop):
            sold = item.get("sold")
            label = "%s   [%s]" % (item["label"], "SOLD" if sold else "%d gold" % item["cost"])
            self.buttons.append(CardButton((140, 150 + i * 84, 680, 70), label, "", lambda i=i: self.buy(i),
                                           enabled=not sold, key=pygame.K_1 + i, tag="item%d" % i))
        self.add((380, 520, 200, 44), "Leave shop", self.app.leave_node, key=pygame.K_ESCAPE,
                 tag="leave")

    def buy(self, i):
        ok, msg = self.run.buy(i)
        self.build()
        self.say(msg, GOOD if ok else BAD)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[44], "Shop", (480, 50), TEXT, center=True)
        draw_text(surf, f[26], "Gold %d    HP %d/%d" % (self.run.gold, self.run.player.hp,
                                                       self.run.player.max_hp), (480, 96), WARN, center=True)
        draw_text(surf, f[22], self.msg, (480, 128), self.msg_color, center=True)
        self.draw_buttons(surf)


class RestScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.done = False
        p = self.run.player
        heal = max(1, (p.max_hp * 4) // 10)
        self.buttons.append(CardButton((200, 200, 560, 80), "Rest", "Heal %d HP (40%% of max)." % heal,
                                       lambda: self.pick("heal"), key=pygame.K_1, tag="heal"))
        self.buttons.append(CardButton((200, 300, 560, 80), "Focus",
                                       "+1 charge cap on your lowest colour.",
                                       lambda: self.pick("focus"), key=pygame.K_2, tag="focus"))
        self.cont = self.add((380, 460, 200, 44), "Continue", app.leave_node, enabled=False,
                             key=pygame.K_RETURN, tag="continue")
        self.say("A quiet place. Choose one.", DIM)

    def pick(self, choice):
        if self.done:
            return
        msg = self.run.rest(choice)
        self.done = True
        for b in self.buttons:
            if b.tag in ("heal", "focus"):
                b.enabled = False
        self.cont.enabled = True
        self.say(msg, GOOD)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[44], "Rest Site", (480, 70), GOOD, center=True)
        p = self.run.player
        draw_text(surf, f[26], "HP %d/%d" % (p.hp, p.max_hp), (480, 120), TEXT, center=True)
        draw_text(surf, f[22], self.msg, (480, 160), self.msg_color, center=True)
        self.draw_buttons(surf)


class EventScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.event = self.run.event
        self.done = False
        for i, (cid, label) in enumerate(self.event["choices"]):
            self.buttons.append(CardButton((200, 230 + i * 84, 560, 70), label, "",
                                           lambda c=cid: self.pick(c), key=pygame.K_1 + i,
                                           tag="choice:" + cid))
        self.cont = self.add((380, 520, 200, 44), "Continue", app.leave_node, enabled=False,
                             key=pygame.K_RETURN, tag="continue")
        self.say("Choose how to respond.", DIM)

    def pick(self, cid):
        if self.done:
            return
        try:
            msg = self.run.resolve_event(cid)
        except ValueError as e:
            self.say(str(e), BAD)
            return
        self.done = True
        for b in self.buttons:
            if b.tag.startswith("choice:"):
                b.enabled = False
        self.cont.enabled = True
        self.say(msg, GOOD)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[44], self.event["title"], (480, 60), TEXT, center=True)
        draw_wrapped(surf, f[26], self.event["text"], (200, 120), 560, DIM)
        draw_text(surf, f[22], self.msg, (480, 190), self.msg_color, center=True)
        self.draw_buttons(surf)


class EndScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.won = self.run.finished == "victory"
        self.add((380, 400, 200, 48), "New Run", app.new_run, key=pygame.K_RETURN, tag="new")
        self.add((380, 460, 200, 40), "Title", app.to_title, key=pygame.K_ESCAPE, tag="title")

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        run = self.run
        draw_text(surf, f[72], "VICTORY" if self.won else "DEFEATED", (480, 120),
                  GOOD if self.won else BAD, center=True)
        draw_text(surf, f[26], "Reached act %d   Gold %d   Seed %d" % (min(run.act, 3), run.gold, run.seed),
                  (480, 200), TEXT, center=True)
        relics = ", ".join(RELICS[r]["name"] for r in run.relics) or "none"
        draw_text(surf, f[22], "Relics: " + relics, (480, 240), WARN, center=True)
        d = self.app.meta.data
        draw_text(surf, f[22], "Runs %d   Wins %d   Best act %d" % (d["runs"], d["wins"], d["best_act"]),
                  (480, 290), DIM, center=True)
        self.draw_buttons(surf)
