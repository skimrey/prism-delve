"""Headless UI tests. Events go through App.handle exactly like real input.

Covers: every button and key on every screen, cancel/Esc paths, repeat
clicks (no stuck 'armed' state), invalid input (always a visible message),
animation skip, victory/defeat flows, and a random-input stress run.
"""

import os
import random
import tempfile
import unittest

from helpers import make_state

import pygame

from prism import rules
from prism.app import App
from prism.consts import BEATS, COLORS, COMPONENTS, SHAPES
from prism.node_screens import EndScreen, EventScreen, RestScreen, RewardScreen, ShopScreen
from prism.run import EVENTS, Run
from prism.combat_ui import BoardKeyScreen, CombatScreen
from prism.screens import HelpScreen, RouteScreen, TitleScreen
from prism.state import cast, move, wait
from prism.meadow import FRIENDS, NEWCOMERS, WORLD, MeadowScreen
from prism.story import AscendScreen, RescueScreen, RollScreen, StoryScreen, TowerIntroScreen
from prism.rolloff import RollOffScreen
from prism.pinball import PinballScreen


class UITestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(meta_path=os.path.join(self.tmp.name, "meta.json"), seed=21, tips=False)

    def tearDown(self):
        self.tmp.cleanup()

    # -- input helpers (real event path)
    def click(self, pos, button=1):
        self.app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))

    def hover(self, pos):
        self.app.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))

    def key(self, k):
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    def btn(self, tag):
        for b in self.app.screen.buttons:
            if b.tag == tag:
                return b
        self.fail("no button %r on %s" % (tag, type(self.app.screen).__name__))

    def click_btn(self, tag):
        b = self.btn(tag)
        self.click(b.rect.center)
        return b

    def tile_pos(self, gx, gy):
        r = self.app.screen.tile_rect(gx, gy)
        return r.center

    def draw_ok(self):
        self.app.draw()
        small = pygame.transform.scale(self.app.surface, (64, 40))
        colours = {tuple(small.get_at((x, y)))[:3] for x in range(64) for y in range(40)}
        self.assertGreater(len(colours), 8, "screen looks blank")

    PATTERN_KEYS = {"beam": pygame.K_1, "slant": pygame.K_2, "halo": pygame.K_3,
                    "leap": pygame.K_4, "lob": pygame.K_5}
    COLOUR_KEYS = {"R": pygame.K_r, "G": pygame.K_g, "B": pygame.K_b, "Y": pygame.K_y,
                   "C": pygame.K_c, "M": pygame.K_m}

    def arm(self, pattern, shape, color):
        """Pick a pattern (key), a shape (button) and a colour (key)."""
        self.key(self.PATTERN_KEYS[pattern])
        self.click_btn("shape:" + shape)
        self.key(self.COLOUR_KEYS[color])

    def cast_at(self, pattern, shape, color, tile):
        self.arm(pattern, shape, color)
        self.click(self.tile_pos(*tile))

    def arrive(self):
        """Skip the walk on the floor map (joins the room-building thread)."""
        rs = self.app.screen
        self.assertIsInstance(rs, RouteScreen)
        self.assertIsNotNone(rs.travel, "no walk in progress")
        self.key(pygame.K_SPACE)

    def finish_anim(self, via="key"):
        cs = self.app.screen
        if cs.mode == "anim":
            if via == "key":
                self.key(pygame.K_SPACE)
            elif via == "click":
                self.click((10, 10))
            else:
                for _ in range(200):
                    self.app.tick(0.2)
                    if cs.mode != "anim":
                        break
        return cs

    # -- scenario builders
    def combat(self, enemies, walls=(), hp=None, palette=None, mods=None, player_at=(4, 8)):
        self.app.new_run()
        run = self.app.run
        run.route.layers[0][0].kind = "fight"
        run.enter(0)
        st = make_state(enemies, walls=walls, hp=hp, palette=palette, mods=mods, player_at=player_at)
        run.state = st
        run.player = st.player
        self.app.replace(CombatScreen(self.app, run))
        return self.app.screen

    def node(self, kind):
        self.app.new_run()
        run = self.app.run
        run.route.layers[0][0].kind = kind
        self.app.enter_node(0)
        return self.app.screen


class TitleAndHelp(UITestCase):
    def test_title_buttons(self):
        self.assertIsInstance(self.app.screen, TitleScreen)
        self.draw_ok()
        labels = [b.label for b in self.app.screen.buttons]
        self.assertEqual(labels, ["New Run", "The Story", "How to Play", "Settings", "Quit"])

    def test_first_new_run_plays_the_story_once(self):
        self.click_btn("new")
        self.assertIsInstance(self.app.screen, StoryScreen)
        self.draw_ok()
        self.key(pygame.K_ESCAPE)                   # skip
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertTrue(self.app.meta.data["seen_intro"])
        self.app.to_title()
        self.key(pygame.K_RETURN)                   # second time: straight in
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_story_pages_advance_by_key_click_and_button(self):
        self.click_btn("story")
        st = self.app.screen
        self.assertIsInstance(st, StoryScreen)
        n = 0
        while isinstance(self.app.screen, StoryScreen):
            self.app.tick(0.7)
            self.draw_ok()
            [lambda: self.key(pygame.K_RETURN), lambda: self.click((480, 200)),
             lambda: self.click_btn("next")][n % 3]()
            n += 1
            self.assertLess(n, 10)
        from prism.story import STORY
        self.assertEqual(n, len(STORY))
        self.assertIsInstance(self.app.screen, TitleScreen)      # replayed from the title

    def test_help_open_close_twice_and_pages(self):
        for _ in range(2):
            self.click_btn("help")
            self.assertIsInstance(self.app.screen, HelpScreen)
            self.draw_ok()
            self.click_btn("page:rules")
            self.assertEqual(self.app.screen.page, "rules")
            self.draw_ok()
            self.key(pygame.K_TAB)
            self.assertEqual(self.app.screen.page, "world")
            self.click(self.app.screen.buttons[0].rect.center)
            self.assertIsInstance(self.app.screen, TitleScreen)
        self.key(pygame.K_h)
        self.assertIsInstance(self.app.screen, HelpScreen)
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, TitleScreen)

    def test_quit_button_key_and_window_close(self):
        self.click_btn("quit")
        self.assertFalse(self.app.running)
        self.app.running = True
        self.key(pygame.K_ESCAPE)
        self.assertFalse(self.app.running)
        self.app.running = True
        self.app.handle(pygame.event.Event(pygame.QUIT))
        self.assertFalse(self.app.running)

    def test_clicking_empty_space_does_nothing(self):
        self.click((5, 5))
        self.assertIsInstance(self.app.screen, TitleScreen)


class Route(UITestCase):
    def setUp(self):
        super().setUp()
        self.app.new_run()

    def test_click_every_choice_leads_to_the_right_screen(self):
        expected = {"fight": CombatScreen, "elite": CombatScreen, "boss": CombatScreen,
                    "shop": ShopScreen, "rest": RestScreen, "event": EventScreen}
        for kind, screen_cls in expected.items():
            self.app.new_run()
            self.app.run.route.layers[0][0].kind = kind
            self.click(self.btn("node").rect.center)
            self.assertIsInstance(self.app.screen, RouteScreen)     # walking there first
            self.draw_ok()
            self.arrive()
            self.assertIsInstance(self.app.screen, screen_cls, kind)
            self.draw_ok()

    def test_walk_finishes_by_itself(self):
        self.app.run.route.layers[0][0].kind = "rest"
        self.click(self.btn("node").rect.center)
        for _ in range(100):
            self.app.tick(0.05)
            if not isinstance(self.app.screen, RouteScreen):
                break
        self.assertIsInstance(self.app.screen, RestScreen)

    def test_number_keys_pick_nodes(self):
        n = len(self.app.run.choices())
        self.key(pygame.K_1 + n - 1)
        self.arrive()
        self.assertEqual(self.app.run.node, n - 1)

    def test_arrows_choose_and_enter_goes(self):
        n = len(self.app.run.choices())
        want = self.app.run.choices()[(n - 1) % n][0]
        rs = self.app.screen
        self.key(pygame.K_DOWN)
        self.assertEqual(rs.sel, 1 % n)
        self.key(pygame.K_UP)
        self.key(pygame.K_UP)
        self.assertEqual(rs.sel, (n - 1) % n)
        self.draw_ok()
        self.key(pygame.K_RETURN)
        self.arrive()
        self.assertEqual(self.app.run.node, want)

    def test_input_during_the_walk_only_skips_it(self):
        self.key(pygame.K_1)
        rs = self.app.screen
        self.key(pygame.K_2)                 # does not start a second walk
        self.assertIsNot(self.app.screen, rs)
        self.assertEqual(self.app.run.layer, 0)

    def test_wrong_key_number_is_ignored(self):
        self.key(pygame.K_9)
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_escape_explains_itself(self):
        self.key(pygame.K_ESCAPE)
        self.assertTrue(self.app.screen.msg)

    def test_abandon_needs_two_clicks_and_esc_cancels(self):
        self.click_btn("abandon")
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertIn("confirm", self.app.screen.msg.lower())
        self.key(pygame.K_ESCAPE)
        self.assertIn("cancel", self.app.screen.msg.lower())
        self.assertFalse(self.app.screen.confirm)
        self.click_btn("abandon")
        self.click_btn("abandon")
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.app.meta.data["runs"], 1)
        self.assertEqual(self.app.run.finished, "defeat")

    def test_route_draw_through_a_whole_act(self):
        self.draw_ok()
        self.app.run.relics.append("crimson_lens")
        self.draw_ok()
        run = self.app.run
        for _ in range(len(run.route.layers) - 1):
            for node in run.route.layers[run.layer + 1]:
                node.kind = "rest"                 # keep it fast: no fights to build
            self.key(pygame.K_1)
            self.arrive()
            self.app.tick(0.1)
            self.draw_ok()
            self.key(pygame.K_1)
            self.click_btn("continue")
            self.assertIsInstance(self.app.screen, RouteScreen)
            self.app.tick(0.1)
            self.draw_ok()
        self.assertEqual(run.choices()[0][1].kind, "boss")

    def test_every_floor_draws(self):
        for act in (1, 2, 3):
            self.app.new_run()
            self.app.run.act = act
            self.app.replace(RouteScreen(self.app))
            self.app.tick(0.3)
            self.draw_ok()


class CombatInput(UITestCase):
    def setUp(self):
        super().setUp()
        # a square far up the board, blue and tough, so casts are predictable
        self.cs = self.combat([("pawn", 4, 6, "B", 30)], walls=[(0, 2)])

    def test_pattern_buttons_each_click_twice_and_locked_ones_explain(self):
        for pt in ("beam", "slant", "halo"):
            for _ in range(2):
                self.click_btn("pattern:" + pt)
                self.assertEqual(self.cs.pattern, pt)
                self.assertEqual(self.cs.tool, "cast")
                self.assertTrue(self.btn("pattern:" + pt).active)
        for pt in ("leap", "lob"):
            self.assertFalse(self.btn("pattern:" + pt).enabled)
            self.click(self.btn("pattern:" + pt).rect.center)
            self.assertEqual(self.cs.pattern, "halo")
        self.key(pygame.K_4)
        self.assertIn("learned", self.cs.msg)
        self.assertEqual(self.cs.queue, [])

    def test_shape_buttons_and_tab_cycle(self):
        for sh in ("square", "circle", "triangle"):
            self.click_btn("shape:" + sh)
            self.assertEqual(self.cs.shape, sh)
            self.assertTrue(self.btn("shape:" + sh).active)
        seen = []
        for _ in range(3):
            self.key(pygame.K_TAB)
            seen.append(self.cs.shape)
        self.assertEqual(sorted(seen), ["circle", "square", "triangle"])
        self.assertIn("passes through", self.cs.msg)

    def test_every_colour_button_arms_and_can_be_repicked(self):
        for c in COLORS:
            for _ in range(2):
                self.click_btn("color:" + c)
                self.assertEqual(self.cs.color, c)
                self.assertTrue(self.btn("color:" + c).active)

    def test_unaffordable_colours_are_disabled_and_keys_explain(self):
        cs = self.combat([("pawn", 4, 2, "B", 30)], palette={"R": 0})
        for c in ("R", "Y", "M"):
            self.assertFalse(self.btn("color:" + c).enabled, c)
            self.click(self.btn("color:" + c).rect.center)
            self.assertIsNone(cs.color)
        for c in ("G", "B", "C"):
            self.assertTrue(self.btn("color:" + c).enabled, c)
        self.key(pygame.K_r)
        self.assertIn("charges", cs.msg.lower())

    def test_cast_lands_in_the_queue_with_pattern_shape_colour_and_aim(self):
        self.cast_at("beam", "square", "G", (4, 6))
        self.assertEqual(self.cs.queue, [cast("beam", "square", "G", 0, -1)])

    def test_aim_is_read_from_the_clicked_tile(self):
        self.cast_at("beam", "square", "R", (7, 7))       # mostly to the right
        self.assertEqual((self.cs.queue[-1].dx, self.cs.queue[-1].dy), (1, 0))
        self.cast_at("slant", "square", "R", (2, 6))
        self.assertEqual((self.cs.queue[-1].dx, self.cs.queue[-1].dy), (-1, -1))
        self.cast_at("halo", "square", "R", (0, 0))       # Halo: anywhere will do
        self.assertEqual((self.cs.queue[-1].pattern, self.cs.queue[-1].dx), ("halo", 0))

    def test_bad_aims_are_refused_with_a_message(self):
        self.cast_at("slant", "square", "R", (4, 6))       # straight up is not a diagonal
        self.assertEqual(self.cs.queue, [])
        self.assertIn("diagonal", self.cs.msg)
        cs = self.combat([("pawn", 4, 2, "B", 30)], walls=[(4, 7)])
        self.cast_at("beam", "square", "R", (4, 5))        # straight into a wall
        self.assertEqual(cs.queue, [])
        self.assertIn("straight", cs.msg)

    def test_a_pattern_is_spent_once_cast_and_undo_returns_it(self):
        self.cast_at("beam", "square", "R", (4, 6))
        self.assertIsNone(self.cs.pattern)
        self.assertEqual(self.cs.color, "R")              # colour and shape stay picked
        self.assertFalse(self.btn("pattern:beam").enabled)
        self.assertTrue(self.btn("pattern:beam").used)
        self.key(pygame.K_1)
        self.assertIn("once per turn", self.cs.msg)
        self.click(self.tile_pos(4, 6))                    # nothing armed: explains, no cast
        self.assertEqual(len(self.cs.queue), 1)
        self.key(pygame.K_z)
        self.assertTrue(self.btn("pattern:beam").enabled)

    def test_mixed_colours_spend_both_charges_in_the_preview(self):
        self.cast_at("beam", "square", "M", (4, 6))
        pal = self.cs.cur.player.palette
        self.assertEqual((pal["R"], pal["B"], pal["G"]), (2, 2, 3))

    def test_charges_run_out_inside_one_plan(self):
        for pt, tile in (("beam", (4, 6)), ("slant", (5, 7)), ("halo", (4, 7))):
            self.cast_at(pt, "square", "R", tile)
        self.assertEqual(len(self.cs.queue), 3)
        self.assertFalse(self.btn("color:R").enabled)
        self.key(pygame.K_r)
        self.assertIn("charges", self.cs.msg.lower())

    def test_hover_preview_predicts_damage_and_what_fits(self):
        self.arm("beam", "square", "R")
        self.hover(self.tile_pos(4, 6))
        a, tiles, ev = self.cs.hover_preview()
        self.assertIn((4, 6), tiles)
        self.assertEqual([e["took"] for e in ev if e["t"] == "dmg"], [3])
        self.draw_ok()
        self.click_btn("shape:circle")
        a, tiles, ev = self.cs.hover_preview()
        self.assertEqual([e for e in ev if e["t"] == "dmg"], [])
        self.draw_ok()
        self.assertEqual(self.cs.queue, [])                # previews never queue

    def test_move_tool_and_keys(self):
        self.click_btn("tool_move")
        self.click(self.tile_pos(5, 8))
        self.assertEqual(self.cs.queue[-1], move(1, 0))
        self.key(pygame.K_LEFT)
        self.key(pygame.K_a)
        self.key(pygame.K_UP)
        self.assertEqual(len(self.cs.queue), 4)
        self.assertEqual(self.cs.queue, [move(1, 0), move(-1, 0), move(-1, 0), move(0, -1)])
        self.key(pygame.K_w)                       # timeline full: refused with a message
        self.assertEqual(len(self.cs.queue), 4)
        self.assertIn("full", self.cs.msg.lower())

    def test_arrow_keys_move_even_with_a_cast_armed(self):
        self.arm("beam", "square", "R")
        self.key(pygame.K_RIGHT)
        self.assertEqual(self.cs.queue, [move(1, 0)])

    def test_every_direction_key(self):
        for k, d in ((pygame.K_UP, (0, -1)), (pygame.K_w, (0, -1)), (pygame.K_RIGHT, (1, 0)),
                     (pygame.K_d, (1, 0)), (pygame.K_DOWN, (0, 1)), (pygame.K_s, (0, 1)),
                     (pygame.K_LEFT, (-1, 0)), (pygame.K_a, (-1, 0))):
            cs = self.combat([("pawn", 4, 1, "B", 30)], player_at=(4, 4))
            self.key(k)
            self.assertEqual(cs.queue, [move(*d)], k)

    def test_move_into_wall_enemy_and_edge_explain(self):
        cs = self.combat([("pawn", 4, 7, "B", 30)], walls=[(3, 8)], player_at=(4, 8))
        for k in (pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN):
            self.key(k)
            self.assertEqual(cs.queue, [])
            self.assertTrue(cs.msg)

    def test_click_far_tile_with_move_tool_and_own_tile_explain(self):
        self.click(self.tile_pos(0, 0))
        self.assertEqual(self.cs.queue, [])
        self.assertTrue(self.cs.msg)
        self.click(self.tile_pos(4, 8))
        self.assertEqual(self.cs.queue, [])
        self.assertIn("you", self.cs.msg.lower())

    def test_wait_button_and_space(self):
        self.click_btn("wait")
        self.key(pygame.K_SPACE)
        self.assertEqual(self.cs.queue, [wait(), wait()])

    def test_timeline_full_message(self):
        for _ in range(BEATS):
            self.key(pygame.K_SPACE)
        self.key(pygame.K_SPACE)
        self.assertEqual(len(self.cs.queue), BEATS)
        self.assertIn("full", self.cs.msg.lower())
        self.click_btn("wait")
        self.assertEqual(len(self.cs.queue), BEATS)

    def test_undo_clear_buttons_keys_and_empty_cases(self):
        self.click(self.btn("undo").rect.center)          # disabled: nothing happens
        self.assertEqual(self.cs.queue, [])
        self.key(pygame.K_BACKSPACE)
        self.assertIn("nothing", self.cs.msg.lower())
        self.key(pygame.K_z)
        self.key(pygame.K_x)
        self.assertTrue(self.cs.msg)
        self.assertFalse(self.btn("undo").enabled)
        self.assertFalse(self.btn("clear").enabled)
        for _ in range(3):
            self.key(pygame.K_SPACE)
        self.click_btn("undo")
        self.assertEqual(len(self.cs.queue), 2)
        self.key(pygame.K_BACKSPACE)
        self.assertEqual(len(self.cs.queue), 1)
        self.key(pygame.K_z)
        self.assertEqual(len(self.cs.queue), 0)
        for _ in range(3):
            self.key(pygame.K_SPACE)
        self.click_btn("clear")
        self.assertEqual(self.cs.queue, [])
        for _ in range(2):
            self.key(pygame.K_SPACE)
        self.key(pygame.K_x)
        self.assertEqual(self.cs.queue, [])

    def test_timeline_slots_cut_the_plan_back(self):
        for _ in range(4):
            self.key(pygame.K_SPACE)
        self.click_btn("slot2")
        self.assertEqual(len(self.cs.queue), 2)
        self.assertFalse(self.btn("slot3").enabled)
        self.click(self.btn("slot3").rect.center)
        self.assertEqual(len(self.cs.queue), 2)
        self.click_btn("slot0")
        self.assertEqual(len(self.cs.queue), 0)

    def test_escape_and_right_click_cancel_a_half_finished_cast(self):
        self.key(pygame.K_1)
        self.key(pygame.K_r)
        self.key(pygame.K_ESCAPE)
        self.assertIsNone(self.cs.color)
        self.assertIsNone(self.cs.pattern)
        self.assertEqual(self.cs.tool, "move")
        self.assertIn("cancel", self.cs.msg.lower())
        self.click(self.tile_pos(4, 6))            # no longer armed: must not cast
        self.assertEqual(self.cs.queue, [])
        self.key(pygame.K_r)
        self.click((600, 600), button=3)
        self.assertIsNone(self.cs.color)
        self.key(pygame.K_ESCAPE)
        self.assertIn("nothing", self.cs.msg.lower())

    def test_half_armed_click_asks_for_the_missing_part(self):
        self.key(pygame.K_1)
        self.click(self.tile_pos(4, 6))
        self.assertEqual(self.cs.queue, [])
        self.assertIn("colour", self.cs.msg)
        self.key(pygame.K_ESCAPE)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
        self.assertEqual(self.cs.queue, [])
        self.assertIn("pattern", self.cs.msg)

    def test_pattern_keys_and_colour_keys(self):
        for k, pt in ((pygame.K_1, "beam"), (pygame.K_2, "slant"), (pygame.K_3, "halo")):
            self.key(k)
            self.assertEqual(self.cs.pattern, pt)
        for k, c in ((pygame.K_r, "R"), (pygame.K_g, "G"), (pygame.K_b, "B"),
                     (pygame.K_y, "Y"), (pygame.K_c, "C"), (pygame.K_m, "M")):
            self.key(k)
            self.assertEqual(self.cs.color, c)

    def test_unknown_key_does_nothing_and_does_not_crash(self):
        self.key(pygame.K_F5)
        self.key(pygame.K_F6)
        self.assertEqual(self.cs.queue, [])

    def test_help_overlay_returns_to_the_same_fight(self):
        self.key(pygame.K_SPACE)
        self.click_btn("help")
        self.assertIsInstance(self.app.screen, HelpScreen)
        self.assertEqual(self.app.screen.page, "rules")
        self.key(pygame.K_ESCAPE)
        self.assertIs(self.app.screen, self.cs)
        self.assertEqual(len(self.cs.queue), 1)

    def test_hovering_draws_without_error_and_flags_bad_targets(self):
        self.arm("slant", "square", "R")
        for pos in (self.tile_pos(4, 6), self.tile_pos(0, 0), (700, 300), (10, 10)):
            self.hover(pos)
            self.draw_ok()
        self.key(pygame.K_ESCAPE)
        self.hover(self.tile_pos(4, 6))            # an enemy under the move tool: tooltip
        self.draw_ok()

    def test_learned_patterns_become_usable(self):
        cs = self.combat([("pawn", 3, 6, "B", 30)])
        cs.state.player.patterns.append("leap")
        cs.refresh()
        self.assertTrue(self.btn("pattern:leap").enabled)
        self.cast_at("leap", "square", "R", (0, 0))
        self.assertEqual(cs.queue[-1].pattern, "leap")
        self.assertEqual(cs.cur.enemies[0].hp, 27)


class CombatResolve(UITestCase):
    def test_resolve_animates_skips_and_returns_to_planning_every_way(self):
        for how in ("key", "click", "ticks"):
            cs = self.combat([("pawn", 4, 2, "B", 30)])
            self.key(pygame.K_SPACE)
            self.click_btn("resolve")
            self.assertEqual(cs.mode, "anim")
            self.assertFalse(self.btn("resolve").enabled)
            self.draw_ok()
            self.app.tick(0.3)
            self.draw_ok()
            self.finish_anim(how)
            self.assertEqual(cs.mode, "plan", how)
            self.assertEqual(cs.queue, [])
            self.assertEqual(cs.state.turn, 2)
            self.assertIn("Turn done", cs.msg)
            self.assertTrue(self.btn("resolve").enabled)

    def test_board_clicks_are_ignored_while_animating(self):
        cs = self.combat([("pawn", 4, 2, "B", 30)])
        self.key(pygame.K_RETURN)
        self.assertEqual(cs.mode, "anim")
        self.click(self.tile_pos(5, 8))                    # skips, does not queue
        self.assertEqual(cs.mode, "plan")
        self.assertEqual(cs.queue, [])

    def test_enter_key_and_pass_turn_with_an_empty_queue(self):
        cs = self.combat([("pawn", 4, 1, "B", 30)])
        self.assertIn("Pass", self.btn("resolve").label)
        self.key(pygame.K_RETURN)
        self.finish_anim("ticks")
        self.assertEqual(cs.state.turn, 2)

    def test_partial_queue_label_and_two_turns_in_a_row(self):
        cs = self.combat([("pawn", 4, 1, "B", 30)], palette={"R": 0})
        self.key(pygame.K_SPACE)
        self.assertIn("Resolve 1 beat", self.btn("resolve").label)
        self.click_btn("resolve")
        self.finish_anim("ticks")
        self.key(pygame.K_SPACE)
        self.key(pygame.K_SPACE)
        self.assertIn("Resolve 2 beats", self.btn("resolve").label)
        self.click_btn("resolve")
        self.finish_anim("ticks")
        self.assertEqual(cs.state.turn, 3)
        self.assertEqual(cs.state.player.palette["R"], 2)      # regenerated twice

    def test_result_of_casts_lands_in_the_real_state(self):
        cs = self.combat([("pawn", 4, 6, "B", 30)])
        self.cast_at("beam", "square", "R", (4, 6))
        self.click_btn("resolve")
        self.finish_anim("key")
        e = cs.state.enemies[0]
        self.assertEqual(e.hp, 27)

    def test_telegraph_comes_from_the_exact_preview(self):
        cs = self.combat([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        hits = [e for e in cs.pre_events if e["t"] == "enemy_attack" and e["hit"]]
        self.assertTrue(hits)
        self.key(pygame.K_RIGHT)
        self.key(pygame.K_RIGHT)
        hits = [e for e in cs.pre_events if e["t"] == "enemy_attack" and e["hit"]]
        self.assertFalse(hits)               # two steps clear of its Halo dodges it
        self.draw_ok()

    def test_seven_enemies_draw(self):
        cs = self.combat([("pawn", x, 0, "R") for x in range(7)])
        self.draw_ok()
        self.click_btn("resolve")
        self.app.tick(0.3)
        self.draw_ok()

    def test_victory_flows_to_reward_then_route(self):
        cs = self.combat([("pawn", 4, 6, "B", 2)])
        self.cast_at("beam", "square", "R", (4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.assertIsInstance(self.app.screen, RewardScreen)
        run = self.app.run
        self.assertGreater(run.gold, 0)
        self.draw_ok()
        self.key(pygame.K_RETURN)                           # Continue is disabled until a pick
        self.assertIsInstance(self.app.screen, RewardScreen)
        self.assertFalse(self.btn("continue").enabled)
        self.click_btn("reward0")
        self.assertTrue(self.btn("continue").enabled)
        for i in range(3):
            self.assertFalse(self.btn("reward%d" % i).enabled)
        self.assertFalse(self.btn("skip").enabled)
        self.click_btn("reward1")                            # a second pick is ignored
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_reward_skip_path_and_number_keys(self):
        cs = self.combat([("pawn", 4, 6, "B", 2)])
        self.cast_at("beam", "square", "R", (4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        hp, relics = self.app.run.player.hp, list(self.app.run.relics)
        self.click_btn("skip")
        self.assertEqual(self.app.run.relics, relics)
        self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)
        cs = self.combat([("pawn", 4, 6, "B", 2)])
        self.cast_at("beam", "square", "R", (4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.key(pygame.K_2)
        self.assertTrue(self.btn("continue").enabled)

    def test_a_clean_sort_shows_its_grade_and_a_fourth_reward(self):
        cs = self.combat([("pawn", 4, 6, "B", 2)])
        cs.state.par = 1
        self.draw_ok()
        self.cast_at("beam", "square", "R", (4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.assertIsInstance(self.app.screen, RewardScreen)
        self.assertEqual(self.app.run.grade["name"], "Clean")
        self.assertEqual(len(self.app.screen.options), 4)
        self.draw_ok()
        self.click_btn("reward3")
        self.assertTrue(self.btn("continue").enabled)

    def test_past_par_is_called_out(self):
        cs = self.combat([("pawn", 4, 1, "B", 30)])
        cs.state.par = 1
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.assertIn("past par", cs.msg)
        self.draw_ok()

    def test_keeper_strip_and_shape_changes_draw(self):
        cs = self.combat([("colossus", 4, 3, "B", 30)], hp=99)
        self.draw_ok()
        for _ in range(3):
            self.key(pygame.K_SPACE)
            self.draw_ok()
        self.key(pygame.K_RETURN)
        for _ in range(12):
            self.app.tick(0.2)
            self.draw_ok()

    def test_defeat_ends_the_run_once(self):
        cs = self.combat([("pawn", 4, 7, "R")], hp=1)
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.app.run.finished, "defeat")
        self.assertEqual(self.app.meta.data["runs"], 1)
        self.app.end_run()
        self.assertEqual(self.app.meta.data["runs"], 1)
        self.draw_ok()
        self.click_btn("new")
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.app.run.finished = "defeat"
        self.app.end_run()
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, TitleScreen)

    def test_boss_victory_starts_the_next_act(self):
        self.app.new_run()
        run = self.app.run
        run.route.layers[0][0].kind = "boss"
        self.app.enter_node(0)
        st = make_state([("colossus", 4, 6, "B", 2)])
        run.state, run.player = st, st.player
        self.app.replace(CombatScreen(self.app, run))
        self.cast_at("beam", "square", "R", (4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.click_btn("reward0")
        hp = run.player.max_hp
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, AscendScreen)
        self.assertEqual(run.act, 2)
        self.assertEqual(run.form()["shape"], "square")
        self.assertEqual(run.player.max_hp, hp + 3)
        self.draw_ok()
        self.key(pygame.K_RETURN)                  # first press: skip to the end of the scene
        self.assertIsInstance(self.app.screen, AscendScreen)
        self.draw_ok()
        self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertIn("Floor of Four", self.app.screen.msg)

    def test_final_boss_wins_the_run(self):
        self.app.new_run()
        run = self.app.run
        run.act = 3
        run.route.layers[0][0].kind = "boss"
        self.app.enter_node(0)
        st = make_state([("prism", 4, 6, "B", 2)])
        run.state, run.player = st, st.player
        self.app.replace(CombatScreen(self.app, run))
        self.cast_at("beam", st.enemies[0].shape, "R", (4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.click_btn("skip")
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, RollScreen)
        self.assertEqual(self.app.run.finished, "victory")
        self.assertEqual(self.app.meta.data["wins"], 1)       # recorded before the scene
        for phase in ("door", "ramp"):
            self.assertEqual(self.app.screen.phase, phase)
            self.app.tick(0.5)
            self.draw_ok()
            self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, MeadowScreen)  # steer yourself for a while
        self.draw_ok()
        self.key(pygame.K_ESCAPE)                            # and rest whenever you like
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.app.meta.data["wins"], 1)
        self.draw_ok()

    def test_the_roll_plays_out_on_its_own(self):
        self.app.new_run()
        self.app.run.finished = "victory"
        self.app.replace(RollScreen(self.app))
        rs = self.app.screen
        seen = set()
        for _ in range(400):
            self.app.tick(0.05)
            seen.add(rs.phase)
            if not isinstance(self.app.screen, RollScreen):
                break
        self.assertEqual(seen, {"door", "ramp"})
        self.assertIsInstance(self.app.screen, MeadowScreen)    # the ramp ends in the Meadow
        self.draw_ok()


class NodeScreens(UITestCase):
    def test_shop_every_item_every_path(self):
        sh = self.node("shop")
        run = self.app.run
        self.draw_ok()
        n = len(run.shop)
        for i in range(n):
            self.click_btn("item%d" % i)
            self.assertIn("glint", sh.msg.lower())
        run.gold = 1000
        hp0 = run.player.hp
        run.player.hp = 3
        for i in range(n):
            gold = run.gold
            self.click_btn("item%d" % i)
            self.assertFalse(self.btn("item%d" % i).enabled)
            self.assertLess(run.gold, gold)
            self.assertIn("Bought", sh.msg)
            gold_after = run.gold
            self.click(self.btn("item%d" % i).rect.center)      # sold item: nothing happens
            self.assertEqual(run.gold, gold_after)
        self.draw_ok()
        self.click_btn("leave")
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_shop_number_keys_and_escape(self):
        sh = self.node("shop")
        self.app.run.gold = 500
        self.key(pygame.K_1)
        self.assertTrue(self.app.run.shop[0].get("sold"))
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_rest_heal_then_second_pick_is_ignored(self):
        rs = self.node("rest")
        run = self.app.run
        run.player.hp = 3
        self.draw_ok()
        self.click_btn("heal")
        self.assertGreater(run.player.hp, 3)
        hp = run.player.hp
        caps = dict(run.player.cap)
        self.assertFalse(self.btn("heal").enabled)
        self.assertFalse(self.btn("focus").enabled)
        self.click(self.btn("focus").rect.center)
        self.key(pygame.K_2)
        self.assertEqual(run.player.cap, caps)
        self.assertEqual(run.player.hp, hp)
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_rest_focus_path_and_keys(self):
        self.node("rest")
        run = self.app.run
        self.key(pygame.K_2)
        self.assertEqual(sorted(run.player.cap.values()), [5, 5, 6])
        self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.node("rest")
        self.app.run.player.hp = 2
        self.key(pygame.K_1)
        self.assertGreater(self.app.run.player.hp, 2)

    def test_every_event_choice_through_the_ui(self):
        for ev in EVENTS:
            for variant in ("gift", "deal"):
                for cid, _label, _effects in ev[variant]:
                    self.app.new_run()
                    run = self.app.run
                    run.route.layers[0][0].kind = "event"
                    self.app.enter_node(0)
                    run.event = run.make_event(ev, variant)
                    self.app.replace(EventScreen(self.app))
                    run.gold = 50
                    self.draw_ok()
                    self._pick_and_continue(cid)

    def _pick_and_continue(self, cid):
        self.click_btn("choice:" + cid)
        self.assertTrue(self.app.screen.msg)
        self.assertTrue(self.btn("continue").enabled, cid)
        self.assertFalse(self.btn("choice:" + cid).enabled)
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_event_unaffordable_choice_explains_and_stays(self):
        self.node("event")
        run = self.app.run
        run.event = run.make_event([e for e in EVENTS if e["id"] == "trader"][0], "deal")
        self.app.replace(EventScreen(self.app))
        run.gold = 0
        self.click_btn("choice:buy")
        self.assertIn("glint", self.app.screen.msg.lower())
        self.assertFalse(self.btn("continue").enabled)
        self.assertTrue(self.btn("choice:leave").enabled)
        self.click_btn("choice:leave")
        self.assertTrue(self.btn("continue").enabled)
        self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_end_screen_buttons(self):
        self.app.new_run()
        self.app.abandon_run()
        self.assertIsInstance(self.app.screen, EndScreen)
        self.draw_ok()
        self.click_btn("title")
        self.assertIsInstance(self.app.screen, TitleScreen)
        self.app.new_run()
        self.app.abandon_run()
        self.click_btn("new")
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_screenshot_writes_a_file(self):
        path = os.path.join(self.tmp.name, "shot.png")
        self.app.screenshot(path)
        self.assertGreater(os.path.getsize(path), 1000)


class Stress(UITestCase):
    """Random input everywhere must never raise or leave the app without a screen."""

    KEYS = [pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_BACKSPACE, pygame.K_1,
            pygame.K_2, pygame.K_3, pygame.K_r, pygame.K_g, pygame.K_b, pygame.K_y, pygame.K_c,
            pygame.K_m, pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_z, pygame.K_x,
            pygame.K_h, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_F1,
            pygame.K_TAB, pygame.K_4, pygame.K_5]

    def test_random_input_storm(self):
        for seed in (1, 2, 3, 4):
            rng = random.Random(seed)
            self.app = App(meta_path=os.path.join(self.tmp.name, "m%d.json" % seed), seed=seed,
                           tips=seed % 2 == 0)
            self.app.new_run()
            for step in range(700):
                roll = rng.random()
                if roll < 0.45:
                    self.click((rng.randrange(0, 960), rng.randrange(0, 640)), rng.choice((1, 1, 1, 3)))
                elif roll < 0.8:
                    self.key(rng.choice(self.KEYS))
                elif roll < 0.9:
                    self.hover((rng.randrange(0, 960), rng.randrange(0, 640)))
                else:
                    self.app.tick(rng.choice((0.05, 0.3, 0.6)))
                if step % 25 == 0:
                    self.app.draw()
                if not self.app.running:
                    self.app.running = True
                self.assertTrue(self.app.stack)
                if isinstance(self.app.screen, TitleScreen):
                    self.app.new_run()
            self.app.draw()


if __name__ == "__main__":
    unittest.main()


class ReadingTheBoard(UITestCase):
    def setUp(self):
        super().setUp()
        self.cs = self.combat([("pawn", 4, 6, "R"), ("lancer", 1, 1, "B")], player_at=(4, 8))

    def test_q_and_e_step_through_the_beats(self):
        self.assertIsNone(self.cs.focus)
        seen = []
        for _ in range(5):
            self.key(pygame.K_e)
            seen.append(self.cs.focus)
            self.draw_ok()
        self.assertEqual(seen, [0, 1, 2, 3, None])
        self.key(pygame.K_q)
        self.assertEqual(self.cs.focus, 3)
        self.key(pygame.K_ESCAPE)                  # nothing armed: Esc shows the whole turn again
        self.assertIsNone(self.cs.focus)

    def test_hovering_a_beat_slot_previews_that_beat(self):
        self.hover(self.cs.slot_rect(2).center)
        self.assertEqual(self.cs.focus, 2)
        a, b, _t, _s = self.cs.view()
        self.assertEqual(a, self.cs.pre_snaps[2])   # everyone where they'll be on beat 3
        self.draw_ok()
        self.hover(self.tile_pos(0, 0))
        self.assertIsNone(self.cs.focus)

    def test_each_beat_is_told_in_order_and_says_when_you_get_hit(self):
        story = [self.cs.beat_story(b) for b in range(BEATS)]
        self.assertTrue(all(s.startswith("You: wait") for s in story))
        self.assertTrue(any("HITS YOU" in s for s in story))
        self.key(pygame.K_RIGHT)
        self.key(pygame.K_RIGHT)
        self.assertIn("move right", self.cs.beat_story(0))

    def test_hovering_a_shape_shows_only_its_plan(self):
        self.hover(self.tile_pos(1, 1))
        lancer = self.cs.state.enemy_at(1, 1)
        self.assertEqual(self.cs.isolated(), lancer.id)
        self.assertEqual(set(self.cs.enemy_paths(lancer.id)), {lancer.id})
        self.assertGreater(len(self.cs.enemy_paths()), 1)          # the whole turn has both
        self.draw_ok()
        self.key(pygame.K_1)
        self.key(pygame.K_r)
        self.assertIsNone(self.cs.isolated())      # aiming a cast: back to everything

    def test_pink_marks_only_the_tile_you_will_be_on(self):
        cs = self.combat([("pawn", 4, 4, "R")], player_at=(4, 8))
        hits = [e for e in cs.pre_events if e["t"] == "enemy_attack" and e["hit"]]
        self.assertTrue(hits)
        beat = hits[0]["beat"]
        self.assertEqual(tuple(cs.pre_snaps[beat]["player"][:2]), (4, 8))
        self.draw_ok()

    def test_board_key_opens_from_button_and_key_and_closes(self):
        self.click_btn("key")
        self.assertIsInstance(self.app.screen, BoardKeyScreen)
        self.draw_ok()
        self.key(pygame.K_RETURN)
        self.assertIs(self.app.screen, self.cs)
        self.key(pygame.K_k)
        self.assertIsInstance(self.app.screen, BoardKeyScreen)
        self.key(pygame.K_ESCAPE)
        self.assertIs(self.app.screen, self.cs)
        self.assertTrue(self.app.meta.data["seen_board_key"])


class FirstTimeTips(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(meta_path=os.path.join(self.tmp.name, "meta.json"), seed=21, tips=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_board_key_opens_on_the_first_fight_only(self):
        for first in (True, False):
            self.app.new_run()
            self.app.run.route.layers[0][0].kind = "fight"
            self.app.enter_node(0)
            if first:
                self.assertIsInstance(self.app.screen, BoardKeyScreen)
                self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0,
                                                   unicode="", scancode=0))
            self.assertIsInstance(self.app.screen, CombatScreen)

    def test_new_shapes_are_announced_once(self):
        self.app.new_run()
        run = self.app.run
        run.route.layers[0][0].kind = "fight"
        run.enter(0)
        st = make_state([("pawn", 4, 2, "B", None, "triangle"), ("pawn", 6, 2, "B", None, "square")])
        run.state, run.player = st, st.player
        cs = CombatScreen(self.app, run)
        self.assertEqual(cs.banner["shapes"], ["triangle", "square"])
        self.assertTrue(cs.banner["first"])
        self.app.replace(cs)
        self.app.draw()
        for _ in range(5):
            self.app.tick(1.0)
        self.assertIsNone(cs.banner)
        self.assertIsNone(CombatScreen(self.app, run).banner)      # already met
        st.add_enemy("pawn", 1, 1, "R", 3, "circle")
        again = CombatScreen(self.app, run)
        self.assertEqual(again.banner["shapes"], ["circle"])
        self.assertFalse(again.banner["first"])


class Banter(UITestCase):
    def test_lines_are_rationed_and_keepers_always_speak(self):
        from prism.banter import Banter as B, KEEPER
        b = B(seed=1)
        said = [b.on_hit("square", "triangle") for _ in range(200)]
        self.assertTrue(any(said))
        self.assertEqual(sum(1 for s in said if s), 1)          # then the cooldown holds
        b.update(10)
        self.assertEqual(b.keeper("colossus", "intro"), KEEPER["colossus"]["intro"])
        self.assertIsNone(b.on_loose("circle"))                  # right after a line: quiet
        b.update(10)
        lines = set()
        for _ in range(300):
            b.update(10)
            for s in (b.on_hit("circle", "pentagon"), b.on_loose("triangle"), b.retort()):
                if s:
                    lines.add(s)
        self.assertGreater(len(lines), 15)

    def test_keeper_greets_you_and_bubbles_draw_and_fade(self):
        cs = self.combat([("colossus", 4, 3, "B", 30)], hp=99)
        self.assertEqual(len(cs.bubbles), 1)
        self.draw_ok()
        for _ in range(40):
            self.app.tick(0.1)
        self.assertEqual(cs.bubbles, [])


class DevMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(meta_path=os.path.join(self.tmp.name, "meta.json"), seed=21, tips=False,
                       dev=True)

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, k):
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    def btn(self, tag):
        return next(b for b in self.app.screen.buttons if b.tag == tag)

    def test_dev_menu_jumps_to_every_room_on_every_floor(self):
        from prism import dev
        expected = {"fight": CombatScreen, "elite": CombatScreen, "boss": CombatScreen,
                    "shop": ShopScreen, "rest": RestScreen, "event": EventScreen}
        for act in (1, 2, 3):
            for kind, cls in expected.items():
                self.app.to_title()
                self.key(pygame.K_F1)
                self.assertIsInstance(self.app.screen, dev.DevScreen)
                self.btn("floor%d" % act).click()
                self.btn("room:" + kind).click()
                self.assertIsInstance(self.app.screen, cls, (act, kind))
                self.assertEqual(self.app.run.act, act)
                self.app.draw()

    def test_dev_scenes_and_cheats(self):
        from prism import dev
        for scene, cls in (("story", StoryScreen), ("ascend", AscendScreen), ("roll", RollScreen),
                           ("meadow", MeadowScreen), ("sorted", EndScreen), ("rolled", EndScreen),
                           ("hub", MeadowScreen), ("tower:leaning", RouteScreen),
                           ("rescue:leaning", RescueScreen), ("towerintro:leaning", TowerIntroScreen),
                           ("rolloff", RollOffScreen), ("pinball", PinballScreen)):
            self.app.to_title()
            self.app.push(dev.DevScreen(self.app))
            self.btn("opt:tough").click()
            self.btn("opt:patterns").click()
            self.btn("opt:glint").click()
            if not any(b.tag == "scene:" + scene for b in self.app.screen.buttons):
                self.btn("tab:meadow").click()                 # the hub, towers and games tab
            self.btn("scene:" + scene).click()
            self.assertIsInstance(self.app.screen, cls, scene)
            self.app.draw()
        self.assertEqual(self.app.run.player.max_hp, 99)
        self.assertEqual(len(self.app.run.player.patterns), 5)

    def test_hotkeys_win_lose_skip_and_climb(self):
        from prism import dev
        dev.jump_to_room(self.app, 1, "fight")
        self.key(pygame.K_F2)
        self.assertIsInstance(self.app.screen, RewardScreen)
        self.app.screen.do_skip()
        self.app.leave_node()
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.key(pygame.K_F4)
        self.assertEqual(self.app.run.choices()[0][1].kind, "boss")
        self.key(pygame.K_F6)
        self.assertIsInstance(self.app.screen, AscendScreen)
        self.assertEqual(self.app.run.act, 2)
        for k in (pygame.K_F7, pygame.K_F8, pygame.K_F9):
            self.key(k)
        self.assertEqual(len(self.app.run.player.patterns), 5)
        self.assertGreaterEqual(self.app.run.gold, 100)
        dev.jump_to_room(self.app, 1, "fight")
        self.key(pygame.K_RETURN)                          # mid-animation, F2 still wins
        self.assertEqual(self.app.screen.mode, "anim")
        self.key(pygame.K_F2)
        self.assertNotIsInstance(self.app.screen, CombatScreen)
        dev.jump_to_room(self.app, 2, "boss")
        self.key(pygame.K_F3)
        self.assertIsInstance(self.app.screen, EndScreen)
        self.app.draw()

    def test_towers_and_the_hub_from_the_dev_menu(self):
        from prism import dev
        from prism.consts import TOWER_ORDER
        for tid in TOWER_ORDER:
            for scene, cls in (("tower", RouteScreen), ("towerintro", TowerIntroScreen),
                               ("towerboss", CombatScreen), ("rescue", RescueScreen)):
                self.app.to_title()
                self.app.push(dev.DevScreen(self.app))
                self.btn("tab:meadow").click()
                self.btn("pick:" + tid).click()                 # pick the tower, then jump
                self.btn("scene:%s:%s" % (scene, tid)).click()
                self.assertIsInstance(self.app.screen, cls, (scene, tid))
                if scene != "towerintro":
                    self.assertEqual(self.app.run.tower, tid)
                self.app.draw()
        self.app.to_title()
        self.app.push(dev.DevScreen(self.app))
        self.btn("tab:meadow").click()
        self.btn("rescued:0").click()
        self.btn("hub:zone3").click()                           # a zone's start opens it (dev only)
        self.assertIsInstance(self.app.screen, MeadowScreen)
        self.assertEqual(len(self.app.screen.world.zones), 4)
        self.app.to_title()
        self.app.push(dev.DevScreen(self.app))
        self.btn("tab:meadow").click()
        self.btn("gallery").click()
        from prism.gallery import GalleryScreen
        self.assertIsInstance(self.app.screen, GalleryScreen)
        self.app.draw()
        self.app.pop()
        self.assertNotIn("leaning", self.app.meta.data.get("friends", []))
        self.app.draw()
        dev.apply_cli(self.app, ["--dev", "--scene=tower", "--tower=hollow"])
        self.assertEqual(self.app.run.tower, "hollow")
        dev.apply_cli(self.app, ["--dev", "--scene=hub", "--at=7000", "--rescued=leaning"])
        self.assertEqual(int(self.app.screen.tri.x), 7000)
        dev.apply_cli(self.app, ["--dev", "--scene=pinball"])
        self.app.draw()

    def test_command_line_jumps(self):
        from prism import dev
        dev.apply_cli(self.app, ["--dev", "--floor=3", "--room=boss"])
        self.assertIsInstance(self.app.screen, CombatScreen)
        self.assertEqual(self.app.run.act, 3)
        dev.apply_cli(self.app, ["--dev", "--scene=roll"])
        self.assertIsInstance(self.app.screen, RollScreen)
        dev.apply_cli(self.app, ["--dev", "--event=polisher", "--variant=deal"])
        self.assertIsInstance(self.app.screen, EventScreen)
        self.assertEqual((self.app.run.event["id"], self.app.run.event["variant"]), ("polisher", "deal"))

    def test_without_dev_the_hotkeys_do_nothing(self):
        app = App(meta_path=os.path.join(self.tmp.name, "m2.json"), seed=3, tips=False)
        app.new_run()
        app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F6, mod=0, unicode="", scancode=0))
        self.assertEqual(app.run.act, 1)
        self.assertNotIn("dev", [b.tag for b in TitleScreen(app).buttons])


class Scenes(UITestCase):
    def test_every_encounter_choice_plays_out_as_a_scene(self):
        cases = [(ev, v, c[0]) for ev in EVENTS for v in ("gift", "deal") for c in ev[v]]
        for ev, variant, cid in cases:
            with self.subTest(event=ev["id"], variant=variant, choice=cid):
                self.app.new_run()
                run = self.app.run
                run.route.layers[0][0].kind = "event"
                self.app.enter_node(0)
                run.event = run.make_event(ev, variant)
                run.gold = 50
                self.app.replace(EventScreen(self.app))
                es = self.app.screen
                self.hover(self.btn("choice:" + cid).rect.center)     # a preview on the stage
                self.draw_ok()
                self.click_btn("choice:" + cid)
                self.assertEqual(es.chosen, cid)
                for _ in range(6):
                    self.app.tick(0.5)
                    self.draw_ok()
                self.assertTrue(self.btn("continue").enabled)

    def test_haggle_knows_whether_it_worked(self):
        for seed in range(6):
            self.app.new_run()
            run = self.app.run
            run.rng.seed(seed)
            run.route.layers[0][0].kind = "event"
            self.app.enter_node(0)
            run.event = run.make_event([e for e in EVENTS if e["id"] == "trader"][0], "deal")
            self.app.replace(EventScreen(self.app))
            run.gold = 30
            gold = run.gold
            self.click_btn("choice:haggle")
            self.assertEqual(self.app.screen.info["ok"], run.gold > gold)

    def test_still_tile_choices_animate(self):
        for cid in ("heal", "focus"):
            rs = self.node("rest")
            self.hover(self.btn(cid).rect.center)
            self.draw_ok()
            self.click_btn(cid)
            self.app.tick(1.0)
            self.draw_ok()
            self.assertEqual(rs.chosen, cid)

    def test_danger_tiles_say_who_and_when(self):
        cs = self.combat([("lancer", 4, 5, "B")], player_at=(4, 8))
        d = cs.danger_at((4, 7))
        self.assertTrue(d)
        beat, eid, you, dmg = d[0]
        self.assertEqual(eid, cs.state.enemies[0].id)
        self.assertFalse(you)                 # the ray passes (4, 7), but you stand on (4, 8)
        self.assertTrue(any(x[2] for x in cs.danger_at((4, 8))))
        self.hover(self.tile_pos(4, 7))
        self.draw_ok()
        self.assertTrue(self.app.meta.data["seen_danger_tip"])

    def test_the_story_introduces_the_stillwheel_before_the_end_mentions_it(self):
        from prism.story import STORY
        self.assertTrue(any("Stillwheel" in words for words, _scene, _fill in STORY))

    def test_the_round_door_takes_you_in(self):
        self.app.new_run()
        self.app.run.finished = "victory"
        self.app.replace(RollScreen(self.app))
        rs = self.app.screen
        while rs.phase == "door":
            self.app.tick(0.1)
            if rs.phase == "door" and rs.phase_t < 3.5:
                self.draw_ok()
            else:
                self.app.draw()                   # the white flash is meant to look blank
        self.assertEqual(rs.shaved, 5)
        self.assertEqual(rs.phase, "ramp")


class Meadow(UITestCase):
    def setUp(self):
        super().setUp()
        self.app.new_run()
        self.app.run.finished = "victory"
        self.app.show_meadow()
        self.ms = self.app.screen

    def hold(self, k, seconds):
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
        for _ in range(int(seconds / 0.05)):
            self.app.tick(0.05)
        self.app.handle(pygame.event.Event(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0))

    def test_you_steer_smoothly_and_it_rolls(self):
        x0 = self.ms.tri.x
        self.hold(pygame.K_RIGHT, 1.5)
        self.assertGreater(self.ms.tri.x, x0 + 200)
        self.assertNotEqual(self.ms.tri.rot, 0)
        x1 = self.ms.tri.x
        self.hold(pygame.K_LEFT, 2.0)
        self.assertLess(self.ms.tri.x, x1)
        self.draw_ok()

    def test_hop(self):
        self.key(pygame.K_UP)
        self.app.tick(0.1)
        self.assertGreater(self.ms.tri.lift, 0)
        for _ in range(30):
            self.app.tick(0.05)
        self.assertEqual(self.ms.tri.lift, 0)

    def test_every_circle_tells_its_story(self):
        for f in self.ms.everyone:
            self.ms.tri.x = f.x
            self.ms.tri.vx = 0
            self.assertIs(self.ms.nearest(), f)
            for i in range(len(f.lines)):
                self.key(pygame.K_SPACE)
                self.assertIs(self.ms.talking, f)
                self.assertEqual(f.line, i)
                self.draw_ok()
            self.key(pygame.K_SPACE)
            self.assertTrue(f.heard)
        self.assertEqual(len(self.ms.everyone), len(FRIENDS) + len(NEWCOMERS) + 1)

    def test_rolling_through_friends_doesnt_shove_them_away(self):
        homes = [f.home for f in self.ms.friends]
        self.hold(pygame.K_RIGHT, 8)
        for f, home in zip(self.ms.friends, homes):
            if not f.roamer:
                self.assertLess(abs(f.x - home), 400, f.lines[0])
        self.assertGreater(self.ms.tri.x, WORLD * 0.6)

    def test_nothing_to_win_just_rest(self):
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, EndScreen)


class SettingsAndSaves(UITestCase):
    def tearDown(self):
        from prism import settings
        settings.load({})                       # don't leak settings into other tests
        super().tearDown()

    def test_settings_toggle_persist_and_reload(self):
        from prism import settings
        self.click_btn("settings")
        self.draw_ok()
        self.click_btn("opt:marks")
        self.assertTrue(settings.SETTINGS["marks"])
        self.click_btn("opt:sound")
        self.assertFalse(settings.SETTINGS["sound"])
        v = settings.SETTINGS["volume"]
        self.click_btn("vol-")
        self.assertAlmostEqual(settings.SETTINGS["volume"], round(v - 0.1, 2))
        self.draw_ok()
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, TitleScreen)
        settings.load({})
        again = App(meta_path=self.app.meta.path, seed=3, tips=False)
        self.assertTrue(settings.SETTINGS["marks"])
        self.assertFalse(settings.SETTINGS["sound"])
        self.assertIsNotNone(again.surface)

    def test_colour_symbols_draw_everywhere_colour_matters(self):
        from prism import settings
        settings.SETTINGS["marks"] = True
        cs = self.combat([("pawn", 4, 5, "Y"), ("lancer", 2, 2, "C")])
        self.draw_ok()
        self.hover(self.tile_pos(4, 5))
        self.draw_ok()
        self.node("shop")
        self.draw_ok()
        self.node("rest")
        self.draw_ok()

    def test_colour_blind_mode_letters(self):
        from prism.settings import LETTERS
        self.assertEqual(set(LETTERS), set(COLORS))
        self.assertEqual(len(set(LETTERS.values())), 6)          # every colour its own letter

    def test_the_run_is_saved_on_the_map_and_continues_exactly(self):
        self.app.new_run()
        self.assertTrue(self.app.has_save())
        run = self.app.run
        run.route.layers[0][0].kind = "rest"
        self.app.enter_node(0)
        self.click_btn("heal")
        run.gold = 77
        run.relics.append("echo_stone")
        self.click_btn("continue")                      # back on the map: saved
        expected = run.rng.random()                      # what the run would roll next
        self.app.to_title()
        self.assertIn("continue", [b.tag for b in self.app.screen.buttons])
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, RouteScreen)
        again = self.app.run
        self.assertIsNot(again, run)
        self.assertEqual((again.gold, again.relics, again.layer, again.node), (77, ["echo_stone"], 0, 0))
        self.assertEqual(again.rng.random(), expected)   # the same fights will come
        self.draw_ok()

    def test_the_save_goes_away_when_the_run_ends(self):
        self.app.new_run()
        self.assertTrue(self.app.has_save())
        self.app.abandon_run()
        self.assertFalse(self.app.has_save())
        self.app.to_title()
        self.assertNotIn("continue", [b.tag for b in self.app.screen.buttons])

    def test_a_broken_save_is_ignored(self):
        with open(self.app.save_path, "w") as f:
            f.write("{nope")
        self.assertTrue(self.app.has_save())
        self.app.continue_run()
        self.assertIsInstance(self.app.screen, TitleScreen)
        self.assertFalse(self.app.has_save())

    def test_sound_builds_and_plays_or_quietly_does_nothing(self):
        from prism import settings, sound
        for name in sound.NAMES:
            sound.play(name)
        sound.roll(0.5)
        sound.roll(0)
        settings.SETTINGS["sound"] = False
        sound.play("tick")
        sound.roll(1.0)
        self.assertIsNone(sound._state["roll"])


class MeadowHub(UITestCase):
    """The Meadow as a hub: the Leaning Tower, its window, and who's waiting."""

    def hub(self, wins=1):
        self.app.meta.data["wins"] = wins
        self.app.show_hub()
        return self.app.screen

    def test_the_hub_opens_from_the_title_only_after_rolling_out(self):
        self.assertNotIn("meadow", [b.tag for b in self.app.screen.buttons])
        self.app.meta.data["wins"] = 1
        self.app.to_title()
        self.click_btn("meadow")
        self.assertIsInstance(self.app.screen, MeadowScreen)
        self.assertTrue(self.app.screen.hub)
        self.draw_ok()
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, TitleScreen)

    def test_the_window_takes_a_fast_timed_hop_and_nothing_else(self):
        from prism.meadow import Ball, HUB_WORLD, LIP, TOWER_X, WINDOW, hub_ground_y

        def tries(hop_at, start=3500, vx=300, push=1.0):
            b = Ball(start, 26, hub_ground_y, HUB_WORLD)
            b.vx = vx
            hopped = False
            for _ in range(600):
                if hop_at is not None and not hopped and b.x >= LIP + hop_at:
                    b.hop()
                    hopped = True
                b.step(1 / 60, push)
                if b.x + b.r > TOWER_X:
                    return b.air is not None and abs(b.y - WINDOW[1]) < WINDOW[2] + b.r * 0.5
            return False
        self.assertFalse(tries(None))                          # no hop: the wall
        self.assertTrue(tries(-30))                            # a hop at the lip: in
        self.assertTrue(tries(40))                             # a hop just after it still counts
        self.assertFalse(tries(-200))                          # far too early
        self.assertFalse(tries(-20, start=4000, vx=150, push=0.3))   # not enough speed

    def test_through_the_window_you_climb_as_a_circle(self):
        from prism.story import TowerIntroScreen
        ms = self.hub()
        ms.entering = "leaning"
        self.app.tick(0.05)
        self.assertIsInstance(self.app.screen, TowerIntroScreen)   # the first time: who, what, why
        for _ in range(3):
            self.app.tick(2.0)
            self.draw_ok()
            self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)
        run = self.app.run
        self.assertEqual(run.tower, "leaning")
        self.assertTrue(run.player.rolls)
        self.assertEqual(run.form()["shape"], 10)             # round enough to roll (more sides come later)
        self.assertEqual(run.keeper(), "latch")
        self.assertEqual(len(run.route.layers), 5)             # four rooms, then the window
        self.draw_ok()

    def test_reaching_the_window_brings_a_friend_to_your_meadow(self):
        self.app.meta.data["wins"] = 1
        self.app.climb_tower("leaning")
        run = self.app.run
        run.route.layers[0][0].kind = "boss"
        self.app.enter_node(0)
        st = make_state([("latch", 4, 6, "B", 2)])
        st.player.rolls = True
        run.state, run.player = st, st.player
        self.app.replace(CombatScreen(self.app, run))
        self.key(pygame.K_UP)                                  # roll straight into it: bump
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.assertIsInstance(self.app.screen, RewardScreen)
        self.click_btn("skip")
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, RescueScreen)
        self.assertEqual(self.app.meta.data["friends"], ["leaning"])
        rs = self.app.screen
        self.app.tick(1.5)
        self.draw_ok()                                          # up at the window
        for _ in range(200):                                    # out, and ka-thunk all the way down
            self.app.tick(0.05)
            if rs.phase == "landed":
                break
        self.assertEqual(rs.phase, "landed")
        self.assertGreaterEqual(rs.sides, 10)                   # it grew sides on the way down
        self.draw_ok()
        self.key(pygame.K_RETURN)
        self.key(pygame.K_RETURN)
        ms = self.app.screen
        self.assertIsInstance(ms, MeadowScreen)
        self.assertTrue(ms.hub)
        self.assertFalse(ms.waiting)                           # nobody at the window now
        self.assertTrue(ms.wilds)                              # and the Wilds are open
        self.assertIsNotNone(ms.show)                          # it runs the Side Show now
        from prism.world import FRIEND_START
        self.assertEqual(self.app.meta.data["sides"]["leaning"], FRIEND_START)   # round enough: ten sides
        self.assertEqual(ms.show.sides, FRIEND_START)
        self.assertLess(abs(ms.tri.x - ms.show.x), 200)        # you arrive next to it
        self.draw_ok()

    def test_losing_in_a_tower_just_rolls_you_back_out(self):
        self.app.meta.data["wins"] = 1
        runs = self.app.meta.data["runs"]
        self.app.climb_tower("leaning")
        run = self.app.run
        run.route.layers[0][0].kind = "fight"
        self.app.enter_node(0)
        run.finish_combat(False)
        self.app.end_run()
        self.assertIsInstance(self.app.screen, EndScreen)
        self.draw_ok()
        self.assertEqual(self.app.meta.data["runs"], runs)     # climbs of the Sorter only
        self.click_btn("meadow")
        self.assertIsInstance(self.app.screen, MeadowScreen)

    def test_the_tower_intro_plays_once_and_can_be_skipped(self):
        from prism.story import TowerIntroScreen
        self.app.enter_tower("leaning")
        self.assertIsInstance(self.app.screen, TowerIntroScreen)
        self.assertEqual(len(self.app.screen.pages), 3)
        self.key(pygame.K_ESCAPE)                               # skip
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertIn("leaning", self.app.meta.data["towers_seen"])
        self.app.to_title()
        self.app.enter_tower("leaning")                         # the second time: straight in
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_a_tower_run_saves_and_continues_as_a_circle(self):
        self.app.climb_tower("leaning")
        self.assertTrue(self.app.has_save())
        self.app.to_title()
        self.click_btn("continue")
        self.assertEqual(self.app.run.tower, "leaning")
        self.assertTrue(self.app.run.player.rolls)

    def test_rolling_moves_in_combat(self):
        cs = self.combat([("pawn", 4, 2, "B", 9)], player_at=(4, 8))
        cs.state.player.rolls = True
        cs.refresh()
        self.draw_ok()                                          # the roll previews draw
        self.click(self.tile_pos(4, 5))                         # any tile straight up: roll up
        self.assertEqual(cs.queue, [move(0, -1)])
        self.assertEqual((cs.cur.player.x, cs.cur.player.y), (4, 3))
        self.assertEqual(cs.cur.enemies[0].hp, 9 - rules.ROLL_BUMP)


class RollOff(UITestCase):
    """The spheres' favourite game, from the host in the Meadow hub."""

    def hold(self, *keys):
        ro = self.app.screen
        ro.keys = set(keys)

    def play(self, secs, step=1 / 60):
        for _ in range(int(secs / step)):
            self.app.tick(step)

    def start(self, mode):
        self.app.meta.data["wins"] = 1
        self.app.show_rolloff()
        ro = self.app.screen
        self.assertIsInstance(ro, RollOffScreen)
        self.assertIsNone(ro.mode)                              # first, pick a game
        self.draw_ok()
        self.click_btn("mode:" + mode)
        self.assertEqual(ro.mode, mode)
        return ro

    def test_the_host_invites_you_and_the_game_brings_you_back_to_it(self):
        from prism.meadow import HOST_LINES, HOST_X
        self.app.meta.data["wins"] = 1
        self.app.show_hub()
        ms = self.app.screen
        self.assertIsNotNone(ms.host)
        self.assertIn(ms.host, ms.everyone)
        self.assertIn("BEST part", " ".join(HOST_LINES))       # spheres love falling off
        self.draw_ok()
        ms.tri.x = HOST_X - 40
        ms.tri.vx = 0
        for _ in range(len(HOST_LINES)):
            self.key(pygame.K_SPACE)
            self.assertIs(ms.talking, ms.host)
        self.draw_ok()
        self.key(pygame.K_SPACE)                                # "let's roll!"
        self.assertIsInstance(self.app.screen, RollOffScreen)
        self.key(pygame.K_ESCAPE)                               # back: next to the host, asking again
        back = self.app.screen
        self.assertIsInstance(back, MeadowScreen)
        self.assertLess(abs(back.tri.x - HOST_X), 120)
        self.assertIs(back.talking, back.host)
        self.key(pygame.K_SPACE)                                # one Space: straight back in
        self.assertIsInstance(self.app.screen, RollOffScreen)

    def test_no_host_in_the_epilogue_meadow(self):
        self.app.show_meadow()
        self.assertIsNone(self.app.screen.host)

    def test_bump_rounds_end_and_someone_wins(self):
        ro = self.start("bump")
        self.play(30)                                           # you sit still; the bowl shrinks
        self.assertIsNotNone(ro.over, "the round never ended")
        winners, _age = ro.over
        self.assertLessEqual(len(winners), 1)
        self.assertEqual(sum(m.wins for m in ro.marbles), len(winners))
        self.draw_ok()
        self.play(1.2)
        self.key(pygame.K_SPACE)                                # again!
        self.assertIsNone(ro.over)
        self.assertTrue(all(not m.out for m in ro.marbles))     # everyone bounces back on

    def test_driving_off_the_edge_is_a_splash_not_a_loss_of_anything(self):
        ro = self.start("bump")
        self.play(1.0)                                          # everyone drops onto the bowl
        ro.you.x, ro.you.y = 0.0, 0.0
        self.hold(pygame.K_RIGHT)
        for _ in range(600):
            self.app.tick(1 / 60)
            if ro.you.out:
                break
        self.assertTrue(ro.you.out)
        self.draw_ok()                                          # bobbing in the pool, happy
        self.key(pygame.K_SPACE)                                # Space when you're out: next round
        self.assertFalse(ro.you.out)
        self.assertEqual(self.app.meta.data.get("wins"), 1)     # nothing at stake

    def test_dashing_knocks_others_away(self):
        ro = self.start("bump")
        self.play(1.0)
        other = ro.marbles[1]
        for m in ro.marbles[2:]:
            m.x, m.y = 5.0, 5.0                                 # out of the way
        ro.you.x, ro.you.y, ro.you.vx, ro.you.vy = -1.0, 0.0, 0.0, 0.0
        other.x, other.y, other.vx, other.vy = 0.4, 0.0, 0.0, 0.0
        other.think_t = 9.0
        other.aim = (0.0, 0.0001)
        ro.you.dash_cd = 0.0
        self.hold(pygame.K_RIGHT)
        ro.dash(ro.you)
        for _ in range(6):
            ro._move(ro.you, 1 / 60, (1.0, 0.0))
            ro._collide()
        self.assertGreater(other.vx, 3.0)                       # bonk

    def test_tilting_the_bowl_rolls_everyone_that_way(self):
        ro = self.start("tilt")
        self.play(1.0)
        xs = {m.name: m.x for m in ro.marbles}
        self.hold(pygame.K_RIGHT)
        self.play(0.8)
        self.assertGreater(ro.tilt[0], 0.1)
        self.assertGreater(ro.you.x, xs["You"])                 # downhill is to the right...
        others = [m for m in ro.marbles[1:]]
        self.assertGreater(sum(m.x for m in others), sum(xs[m.name] for m in others))   # for all
        self.draw_ok()

    def test_tilt_rounds_can_be_won_by_tipping_them_off(self):
        import math
        ro = self.start("tilt")
        self.play(1.0)
        ro.you.x, ro.you.y = -3.5, 0.0                           # you at one side...
        for k, m in enumerate(ro.marbles[1:]):
            m.x, m.y = 4.8, (k - 1) * 1.3                        # ...them all at the other
        self.hold(pygame.K_RIGHT)
        for _ in range(600):
            self.app.tick(1 / 60)
            if ro.over:
                break
            if ro.you.x > 1.0:                                  # level out before you follow them
                self.hold()
        self.assertIsNotNone(ro.over)
        self.assertEqual(ro.over[0], [ro.you])
        self.assertEqual(ro.you.wins, 1)
        self.assertLess(math.hypot(ro.you.x, ro.you.y), 6.0)

    def test_everyone_plays_including_friends_you_rescued(self):
        from prism.rolloff import rivals
        base = rivals()
        self.assertEqual(len(base), 3)
        self.assertEqual(len(rivals(["leaning"])), 4)
        self.assertIn(("Cyan", "C", "hexagon"), rivals(["leaning"]))
        self.app.meta.data["friends"] = ["leaning"]
        self.app.show_rolloff()
        self.assertEqual(len(self.app.screen.marbles), 5)


class TheWilds(UITestCase):
    """The hub goes on zone after zone: through each tower once its friend is
    out, into the next zone (its game first, then its land), on to its tower."""

    def hub(self, rescued=("leaning",), at=None, plan=None):
        self.app.meta.data["wins"] = 1
        self.app.meta.data["friends"] = list(rescued)
        if plan is not None:
            self.app.meta.data["plan"] = list(plan)
        self.app.show_hub(start_x=at)
        return self.app.screen

    def roll_to(self, ms, x, push=pygame.K_RIGHT, secs=20.0, hop_at=None):
        ms.keys = {push}
        hopped = False
        for _ in range(int(secs * 60)):
            if hop_at is not None and not hopped and ms.tri.x >= hop_at:
                ms.tri.hop()
                hopped = True
            self.app.tick(1 / 60)
            if self.app.screen is not ms or ms.tri.x >= x:
                break
        ms.keys = set()

    def feature(self, ms, kind):
        for z in ms.world.zones:
            for k, fx, size in z.features:
                if k == kind:
                    return z, fx, size
        self.fail("no %s in this world" % kind)

    def test_closed_until_the_first_friend_is_out(self):
        from prism.meadow import HUB_WORLD
        from prism.world import TOWER_X
        ms = self.hub(rescued=())
        self.assertFalse(ms.wilds)
        self.assertEqual(len(ms.world.zones), 1)
        self.assertEqual(ms.width, TOWER_X + 340)
        self.assertLessEqual(ms.width, HUB_WORLD)
        ms.tri.x, ms.tri.vx = TOWER_X - 200, 300
        self.roll_to(ms, TOWER_X + 100, secs=3)
        self.assertLess(ms.tri.x, TOWER_X)                      # the wall: bounce

    def test_zones_open_one_rescue_at_a_time(self):
        from prism.consts import TOWER_ORDER, TOWERS
        for n in range(len(TOWER_ORDER) + 1):
            ms = self.hub(rescued=TOWER_ORDER[:n])
            self.assertEqual(len(ms.world.zones), min(n + 1, len(TOWER_ORDER)))
            for k, z in enumerate(ms.world.zones):
                self.assertEqual(z.tower, TOWER_ORDER[k])
                self.assertEqual(z.kind, TOWERS[z.tower]["zone"])
        # each zone's game is run by the friend whose rescue opened it
        ms = self.hub(rescued=TOWER_ORDER[:3])
        hosts = {h.theme: h for h in ms.hosts}
        self.assertEqual(set(hosts), {"meadow", "wilds", "grove", "frost"})
        self.assertEqual(hosts["wilds"].color, TOWERS["leaning"]["friend"]["color"])
        self.assertEqual(hosts["frost"].game, "curl")
        self.assertEqual(len(ms.keepers), 3)                    # each guardian, holding its door open

    def test_your_plan_sets_the_order(self):
        ms = self.hub(rescued=("icicle",), plan=("icicle", "lens", "leaning"))
        self.assertEqual([z.tower for z in ms.world.zones], ["icicle", "lens"])
        self.assertEqual(ms.world.zones[1].kind, "caves")

    def test_through_the_open_door_into_the_next_zone(self):
        from prism.world import TOWER_X
        ms = self.hub()
        self.assertTrue(ms.wilds)
        self.assertTrue(any(k.kind == "latch" for k in ms.keepers))     # holding the door open
        ms.tri.x, ms.tri.vx = TOWER_X - 150, 300
        self.roll_to(ms, TOWER_X + 400, secs=6)
        self.assertGreater(ms.tri.x, TOWER_X + 300)
        self.assertEqual(ms.region, "The Wilds")
        self.assertEqual(ms.title_text, "The Wilds")
        self.draw_ok()

    def test_roots_bonk_you_unless_you_hop_or_fly(self):
        probe = self.hub()
        _z, rx, _h = self.feature(probe, "root")
        ms = self.hub(at=rx - 120)
        self.roll_to(ms, rx + 120, secs=3)
        self.assertLess(ms.tri.x, rx)                           # slow: bonk
        self.assertGreater(ms.bonked, 0)
        ms = self.hub(at=rx - 120)
        self.roll_to(ms, rx + 120, secs=3, hop_at=rx - 60)
        self.assertGreater(ms.tri.x, rx)                        # hopped it
        ms = self.hub(at=rx - 900)
        ms.tri.vx = 640
        self.roll_to(ms, rx + 120, secs=4)
        self.assertGreater(ms.tri.x, rx)                        # fast: flung over

    def test_you_float_on_the_pools(self):
        probe = self.hub()
        z, c, hw = self.feature(probe, "pool")
        level = z.pool_at(c)[2]
        self.assertAlmostEqual(probe.world.ground(c), level, delta=1)   # the surface, not the bottom
        ms = self.hub(at=c - 40)
        ms.tri.vx = 200
        self.app.tick(1 / 60)
        self.assertTrue(ms.in_pool)
        self.draw_ok()

    def test_ice_slides_caps_throw_and_wind_pushes(self):
        from prism.consts import TOWER_ORDER
        probe = self.hub(rescued=TOWER_ORDER)
        z, x, size = self.feature(probe, "ice")
        ms = self.hub(rescued=TOWER_ORDER, at=x + size / 2)
        ms._ground_feel(ms.tri)
        self.assertLess(ms.tri.grip, 0.5)
        z, x, _s = self.feature(probe, "spring")
        ms = self.hub(rescued=TOWER_ORDER, at=x - 200)
        ms.tri.vx = 300
        thrown = False
        ms.keys = {pygame.K_RIGHT}
        for _ in range(180):
            self.app.tick(1 / 60)
            if ms.tri.vy < -500:
                thrown = True
                break
        self.assertTrue(thrown)                                 # the cap threw you up
        z, x, size = self.feature(probe, "gust")
        ms = self.hub(rescued=TOWER_ORDER, at=x + 20)
        ms._ground_feel(ms.tri)
        self.assertGreater(ms.tri.wind, 0)

    def test_every_tower_takes_the_same_timed_hop(self):
        from prism.consts import TOWER_ORDER
        from prism.meadow import Ball
        from prism.world import World

        world = World(TOWER_ORDER, TOWER_ORDER[:-1])

        def tries(z, hop_at, vx=300):
            b = Ball(z.h0 - 100, 26, world.ground, world.width)
            b.vx = vx
            hopped = False
            for _ in range(600):
                if hop_at is not None and not hopped and b.x >= z.lip + hop_at:
                    b.hop()
                    hopped = True
                b.step(1 / 60, 1.0)
                if b.x + b.r > z.wall:
                    wx, wy, wr = z.window
                    return b.air is not None and abs(b.y - wy) < wr + b.r * 0.5
            return False
        for z in world.zones[1:]:
            self.assertFalse(tries(z, None), z.kind)
            self.assertTrue(tries(z, -30), z.kind)
            self.assertFalse(tries(z, -200), z.kind)

    def test_in_through_the_knothole(self):
        ms = self.hub()
        self.assertTrue(ms.waiting_at("hollow"))
        ms.entering = "hollow"
        self.app.tick(0.05)
        self.assertIsInstance(self.app.screen, TowerIntroScreen)
        for _ in range(3):
            self.app.tick(2.0)
            self.draw_ok()
            self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)
        run = self.app.run
        self.assertEqual((run.tower, run.keeper(), run.tier(), run.portal_pairs()), ("hollow", "knot", 2, 2))
        self.draw_ok()

    def test_everyone_is_drawn_with_their_own_sides_in_every_zone(self):
        from prism.consts import TOWER_ORDER
        ms = self.hub(rescued=TOWER_ORDER)
        sides = {f.sides for f in ms.friends}
        self.assertIn(0, sides)                                # the old Bloom: too many to count
        self.assertIn(10, sides)                               # the ex-Set square: still new out here
        for z in ms.world.zones:
            for x in (z.start + 300, z.start + 2500, z.wall - 200):
                ms.tri.x = x
                ms.cam = max(0.0, min(ms.width - 960, x - 380))
                self.draw_ok()


class SideShow(UITestCase):
    """Pinball: you're the ball; each flipper paints you its colour."""

    def table(self):
        from prism.pinball import PinballScreen
        self.app.meta.data["friends"] = ["leaning"]
        self.app.show_game("pinball", "wilds", 5250)
        ps = self.app.screen
        self.assertIsInstance(ps, PinballScreen)
        return ps

    def test_the_host_invites_you_in(self):
        from prism.meadow import SHOW_LINES
        self.app.meta.data["wins"] = 1
        self.app.meta.data["friends"] = ["leaning"]
        self.app.show_hub()
        host = next(h for h in self.app.screen.hosts if h.game == "pinball")
        self.app.show_hub(start_x=host.home - 40)
        ms = self.app.screen
        self.assertIs(ms.nearest(), ms.show)
        for _ in range(len(SHOW_LINES)):
            self.key(pygame.K_SPACE)
        self.draw_ok()
        self.key(pygame.K_SPACE)
        from prism.pinball import PinballScreen
        self.assertIsInstance(self.app.screen, PinballScreen)
        self.draw_ok()
        self.key(pygame.K_ESCAPE)
        back = self.app.screen
        self.assertIsInstance(back, MeadowScreen)
        self.assertIs(back.talking, back.show)                # "another go?"

    def test_launch(self):
        ps = self.table()
        self.assertTrue(ps.in_lane)
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode="", scancode=0))
        for _ in range(30):
            self.app.tick(1 / 60)
        self.app.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE, mod=0, unicode="", scancode=0))
        for _ in range(40):
            self.app.tick(1 / 60)
        self.assertFalse(ps.in_lane)                           # up the lane and round the top
        self.assertIsNone(ps.color)                            # still white: no flipper yet
        self.draw_ok()

    def flip(self, ps, fl, frac=0.6):
        b = ps.balls[0]
        b.in_lane = False
        tx, ty = fl.tip()
        b.x = fl.px + (tx - fl.px) * frac
        b.y = fl.py + (ty - fl.py) * frac - 24
        b.vx, b.vy = 0.0, 40.0
        for _ in range(3):
            ps.update(1 / 60)
        fl.held = True
        fastest = 0.0
        for _ in range(10):
            ps.update(1 / 60)
            fastest = min(fastest, b.vy)
        fl.held = False
        return fastest

    def test_each_flipper_paints_you_its_colour(self):
        ps = self.table()
        a, b = ps.left.color, ps.right.color
        self.assertNotEqual(a, b)
        fastest = self.flip(ps, ps.right)
        self.assertEqual(ps.color, b)                          # the right flipper's colour
        self.assertLess(fastest, -400)                         # and away you go
        self.flip(ps, ps.left)
        self.assertEqual(ps.color, a)

    def test_only_the_stages_two_colours_on_the_table(self):
        ps = self.table()
        for _ in range(3):
            colours = {t.color for t in ps.targets}
            self.assertLessEqual(colours, {ps.left.color, ps.right.color})
            ps._stage_clear()                                  # on to the next stage
        self.assertEqual(ps.stage, 4)
        self.assertGreater(ps.targets[0].drift, 0)              # later shapes drift about

    def test_own_colour_grows_a_side_until_it_rolls_free(self):
        from prism.pinball import Target
        ps = self.table()
        t = Target(0, 3, ps.left.color)
        t.age = 1.0
        ps.targets = [t]
        self.assertFalse(ps.hit(t, ps.right.color))            # the other colour: just a bounce
        self.assertEqual(t.sides, 3)
        for _ in range(ps.grow_to - 3):
            t.happy = 0.0
            self.assertTrue(ps.hit(t, ps.left.color))
        self.assertEqual(ps.freed, 1)
        self.assertIsNotNone(t.free)                           # off it rolls
        self.draw_ok()

    def test_clearing_a_stage_brings_multiball_and_new_colours(self):
        ps = self.table()
        before = (ps.left.color, ps.right.color)
        ps.balls[0].in_lane = False
        ps._stage_clear()
        self.assertEqual(ps.stage, 2)
        self.assertNotEqual((ps.left.color, ps.right.color), before)
        self.assertEqual(len(ps.balls), 3)

    def test_knothole_and_drop_targets(self):
        from prism.pinball import DROPS, SAUCER, Target
        ps = self.table()
        t = Target(0, 3, ps.left.color)
        t.age = 1.0
        ps.targets = [t]
        b = ps.balls[0]
        b.in_lane, b.color = False, ps.left.color
        ps._knothole(b)
        self.assertEqual(t.sides, 4)                           # the burst fed every shape of your colour
        for _ in range(90):
            ps.update(1 / 60)
        self.assertGreater(b.x, SAUCER[0])                     # and spat you out
        ps.drops = [False, False, True]                        # knock the last one down
        t.happy = 0.0
        b.x, b.y, b.vx, b.vy = DROPS[2][0] - 30, DROPS[2][1], 600, 0
        for _ in range(10):
            ps.update(1 / 60)
        self.assertFalse(any(ps.drops))
        self.assertEqual(t.sides, 5)                           # everyone +1 side

    def test_ball_save_then_three_balls_then_again(self):
        ps = self.table()
        b = ps.balls[0]
        b.in_lane = False
        b.x, b.y, b.vx, b.vy = 210.0, 560.0, 0.0, 900.0      # straight down the middle, right away
        for _ in range(30):
            ps.update(1 / 60)
        self.assertEqual(ps.balls_left, 3)                     # saved!
        for _ in range(3):
            ps.save_t = 0.0
            b = ps.balls[0]
            b.in_lane = False
            b.x, b.y, b.vx, b.vy = 210.0, 560.0, 0.0, 900.0
            for _ in range(60):
                ps.update(1 / 60)
                if ps.over is not None:
                    break
        self.assertIsNotNone(ps.over)
        for _ in range(80):
            self.app.tick(1 / 60)
        self.draw_ok()
        self.key(pygame.K_SPACE)
        self.assertIsNone(ps.over)
        self.assertEqual(ps.balls_left, 3)


class KnotholeCombat(UITestCase):
    def test_holes_draw_explain_and_animate(self):
        from prism.state import Board
        cs = self.combat([("pawn", 8, 0, "B", 9)], player_at=(4, 8))
        cs.state.board = Board(portals=(((4, 5), (1, 2)),))
        cs.state.player.rolls = True
        cs.refresh()
        self.draw_ok()
        self.hover(self.tile_pos(4, 5))                         # the hole's tooltip
        self.draw_ok()
        self.hover(self.tile_pos(4, 7))
        self.key(pygame.K_UP)                                   # roll up: in at (4, 5), out at (1, 2)
        self.assertEqual((cs.cur.player.x, cs.cur.player.y), (1, 0))
        self.draw_ok()                                          # the trail, broken at the hole
        self.key(pygame.K_RETURN)
        for _ in range(12):
            self.app.tick(0.1)
            self.draw_ok()

    def test_through_holes_path(self):
        from prism.combat_ui import _through_holes
        via = [((4, 5), (1, 2))]
        self.assertEqual(_through_holes((4, 8), via, (1, 0), 0.0), (4, 8, 1.0))
        x, y, size = _through_holes((4, 8), via, (1, 0), 0.5)
        self.assertLess(size, 1.0)                              # half way: down the hole
        self.assertEqual(_through_holes((4, 8), via, (1, 0), 1.0), (1, 0, 1.0))

    def test_hollow_tree_fights_have_holes(self):
        from prism import dev
        dev.jump_to_scene(self.app, 3, "towerboss", "hollow")
        cs = self.app.screen
        self.assertIsInstance(cs, CombatScreen)
        self.assertEqual(len(cs.state.board.pairs), 2)
        self.assertEqual(cs.state.enemies[0].kind, "knot")
        self.draw_ok()


class Gallery(UITestCase):
    def test_pick_favourites_and_shuffle(self):
        from prism.consts import TOWER_ORDER
        from prism.gallery import GalleryScreen
        from prism.world import plan_of
        self.app.push(GalleryScreen(self.app))
        gs = self.app.screen
        self.draw_ok()
        self.click(gs.card_rect(TOWER_ORDER.index("lens")).center)       # take the Lens out
        self.assertNotIn("lens", plan_of(self.app.meta.data))
        self.click(gs.card_rect(TOWER_ORDER.index("lens")).center)       # and put it back (last)
        self.assertEqual(plan_of(self.app.meta.data)[-1], "lens")
        self.click_btn("curated")
        self.assertEqual(plan_of(self.app.meta.data), list(TOWER_ORDER))
        self.click_btn("shuffle")
        self.assertEqual(sorted(plan_of(self.app.meta.data)), sorted(TOWER_ORDER))
        self.draw_ok()
        self.click_btn("done")
        self.assertIsInstance(self.app.screen, TitleScreen)

    def test_from_settings(self):
        from prism.gallery import GalleryScreen
        from prism.screens import SettingsScreen
        self.app.push(SettingsScreen(self.app))
        self.click_btn("gallery")
        self.assertIsInstance(self.app.screen, GalleryScreen)


class AllTowers(UITestCase):
    """Every tower: its intro plays (all three cards), its fights have its
    twist tiles, and its rescue lands."""

    def test_every_tower(self):
        from prism import dev
        from prism.consts import TOWER_ORDER, TOWERS
        for tid in TOWER_ORDER:
            dev.jump_to_scene(self.app, 3, "towerintro", tid)
            for _ in range(3):
                self.app.tick(2.0)
                self.draw_ok()
                self.key(pygame.K_RETURN)
            self.assertEqual(self.app.run.tower, tid)
            dev.jump_to_scene(self.app, 3, "towerboss", tid)
            cs = self.app.screen
            self.assertIsInstance(cs, CombatScreen)
            self.assertEqual(cs.state.enemies[0].kind, TOWERS[tid]["boss"])
            twists = TOWERS[tid]["twists"]
            self.assertEqual(bool(cs.state.board.pairs), "holes" in twists, tid)
            self.assertEqual(bool(cs.state.board.tiles), bool(set(twists) - {"holes"}), tid)
            self.draw_ok()
            dev.jump_to_scene(self.app, 3, "rescue", tid)
            self.app.tick(1.0)
            self.draw_ok()


class ZoneGames(UITestCase):
    """Every zone has its own arcade game; each one plays, scores, ends, and
    comes back to its host."""

    def key_up(self, k):
        self.app.handle(pygame.event.Event(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0))

    def play(self, game, zone, seconds=40, hold=0.5):
        from prism.world import GAMES
        self.app.meta.data["wins"] = 1
        self.app.show_game(game, zone, 3000)
        g = self.app.screen
        self.assertEqual(type(g).__name__, GAMES[game][2])
        self.draw_ok()
        t = 0.0
        while t < seconds and getattr(g, "over", None) is None:
            self.key(pygame.K_SPACE)
            for _ in range(int(hold * 60)):
                self.app.tick(1 / 60)
            self.key_up(pygame.K_SPACE)
            for _ in range(150):
                self.app.tick(1 / 60)
            t += hold + 2.5
        self.draw_ok()
        return g

    def test_every_zone_has_a_different_game(self):
        from prism.world import GAMES, ZONES
        games = [z["game"] for z in ZONES.values()]
        self.assertEqual(len(set(games)), len(ZONES))
        self.assertEqual(set(games), set(GAMES))

    def test_spore_drop(self):
        g = self.play("sporedrop", "grove", 60, hold=0.05)
        self.assertGreater(g.score, 0)
        self.assertTrue(any(p.goal for p in g.pegs) or g.level > 1)

    def test_curl(self):
        g = self.play("curl", "frost", 200, hold=0.4)
        self.assertIsNotNone(g.over)                       # three ends, done
        self.assertEqual(g.end_no, 3)

    def test_dune_putt(self):
        g = self.play("duneputt", "dunes", 300, hold=0.45)
        self.assertIsNotNone(g.over)
        self.assertEqual(len(g.cards), 6)

    def test_dune_putt_sinks_a_putt(self):
        from prism.duneputt import DunePuttScreen
        g = DunePuttScreen(self.app, back=lambda: None)
        cx, cy = g.hole["cup"]
        g.x, g.y = cx, cy + 60
        g.aim = 0.0
        g.putt(200)
        for _ in range(180):
            g.update(1 / 60)
            if g.sunk is not None:
                break
        self.assertIsNotNone(g.sunk)

    def test_glimmer_pop_matches_three(self):
        from prism.glimmerpop import GlimmerPopScreen
        g = GlimmerPopScreen(self.app, back=lambda: None)
        g.cells = {(0, 5): ("R", "triangle"), (0, 6): ("R", "triangle")}
        g.loaded = "R"
        g.flying = [g.centre(0, 5)[0] + 18, 60, 0, -900, "R"]
        for _ in range(60):
            g.update(1 / 60)
            if g.flying is None:
                break
        self.assertEqual(g.level, 2)                       # three reds popped: that cave's clear
        self.assertGreater(g.score, 1000)

    def test_beach_bowl(self):
        g = self.play("beachbowl", "coast", 200, hold=0.8)
        self.assertIsNotNone(g.over)
        self.assertGreater(sum(g.rolls), 0)

    def test_bowling_sums(self):
        from prism.beachbowl import BeachBowlScreen
        g = BeachBowlScreen(self.app, back=lambda: None)
        g.rolls = [10, 3, 4]                               # a strike, then 7
        self.assertEqual(g.total(), (17 + 7) * 10)
        g.rolls = [6, 4, 5, 0]                             # a spare, then 5
        self.assertEqual(g.total(), (15 + 5) * 10)

    def test_sky_ball(self):
        g = self.play("skyball", "heights", 200, hold=0.6)
        self.assertIsNotNone(g.over)
        self.assertEqual(len(g.landed), 9)

    def test_hosts_invite_you_to_each_zones_game(self):
        from prism.consts import TOWER_ORDER
        self.app.meta.data["wins"] = 1
        self.app.meta.data["friends"] = list(TOWER_ORDER)
        self.app.show_hub()
        ms = self.app.screen
        games = {h.game for h in ms.hosts}
        self.assertEqual(len(games), 8)
        host = next(h for h in ms.hosts if h.game == "curl")
        self.app.show_hub(start_x=host.home - 40)
        ms = self.app.screen
        h = ms.nearest()
        self.assertEqual(h.game, "curl")
        for _ in range(len(h.lines) + 1):
            self.key(pygame.K_SPACE)
        self.assertEqual(type(self.app.screen).__name__, "CurlScreen")
        self.key(pygame.K_ESCAPE)
        back = self.app.screen
        self.assertIs(back.talking.game, "curl")          # "another end?"


class OpenZones(UITestCase):
    def test_every_zone_open_as_a_setting(self):
        from prism.settings import SETTINGS
        from prism.world import TOWER_X
        self.app.meta.data["wins"] = 1
        SETTINGS["open_zones"] = True
        try:
            self.app.show_hub()
            ms = self.app.screen
            self.assertEqual(len(ms.world.zones), 8)        # all open, nobody out yet
            self.assertTrue(ms.waiting_at("leaning"))       # and everyone still waiting
            ms.tri.x, ms.tri.vx = TOWER_X - 150, 300
            ms.keys = {pygame.K_RIGHT}
            for _ in range(240):
                self.app.tick(1 / 60)
            self.assertGreater(ms.tri.x, TOWER_X + 100)     # through the open door
            self.draw_ok()
        finally:
            SETTINGS["open_zones"] = False

    def test_towers_get_harder_along_your_world(self):
        from prism.run import tower_difficulty
        tiers = [tower_difficulty(p)[0] for p in range(8)]
        rooms = [tower_difficulty(p)[1] for p in range(8)]
        self.assertEqual(tiers, sorted(tiers))
        self.assertEqual(rooms, sorted(rooms))
        self.assertLess(tiers[0], tiers[-1])
        self.app.meta.data["plan"] = ["windmill", "leaning"]
        self.app.climb_tower("windmill")
        self.assertEqual(self.app.run.tier(), 1)            # first in your world: gentle
        self.app.climb_tower("leaning")
        self.assertEqual(self.app.run.tier(), 2)


class DevSides(UITestCase):
    def test_choose_sides_and_keepers_beaten(self):
        from prism import dev, world
        self.app.dev = True
        self.app.push(dev.DevScreen(self.app))
        self.btn("tab:meadow").click()
        self.btn("rescued:3").click()
        self.assertEqual(len(self.app.hub_rescued), 3)
        self.btn("sides:round").click()
        try:
            self.assertEqual(world.your_sides(self.app.meta.data), 0)
            self.btn("sides:auto").click()
            self.btn("sides+").click()
            self.assertGreater(world.your_sides(self.app.meta.data), 15)
        finally:
            world.DEV_SIDES = None


class GrandRoll(UITestCase):
    """Once everyone who asked is out: everyone rolls down the Long Ramp
    together, forms a wheel around you, and rolls off. Then the hub."""

    def test_it_plays_through_every_phase(self):
        from prism import dev
        from prism.finale import FinaleScreen
        dev.jump_to_scene(self.app, 3, "finale")
        fs = self.app.screen
        self.assertIsInstance(fs, FinaleScreen)
        self.assertEqual(len(fs.riders), 1 + 8 + 1 + 3)       # you, everyone you got out, the Stillwheel,
        self.assertTrue(any(0 < r.sides <= 6 for r in fs.riders))   # and a few who only just started rolling
        seen = []
        for _ in range(int(40 / 0.05)):
            self.app.tick(0.05)
            if fs.phase not in seen:
                seen.append(fs.phase)
                self.draw_ok()
            if fs.card is not None:
                break
        self.assertEqual(seen, ["top", "roll", "gather", "wheel"])
        self.assertTrue(fs.cheered)                           # the Keepers cheered it past
        self.draw_ok()
        self.click_btn("again")
        self.assertIsNot(self.app.screen, fs)
        self.assertIsInstance(self.app.screen, FinaleScreen)
        self.key(pygame.K_RETURN)                             # skip straight to the card
        self.assertIsNotNone(self.app.screen.card)
        self.draw_ok()
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, MeadowScreen)
        self.assertTrue(self.app.meta.data.get("finale_seen"))

    def test_the_last_rescue_leads_to_it_once(self):
        from prism.finale import FinaleScreen
        data = self.app.meta.data
        data["wins"] = 1
        data["plan"] = ["leaning", "hollow"]
        data["friends"] = ["leaning"]
        for expect in (FinaleScreen, MeadowScreen):
            self.app.climb_tower("hollow")
            self.app.run.finished = "rescued"
            self.app.record()
            self.app.replace(RescueScreen(self.app))
            rs = self.app.screen
            self.assertEqual(rs.you_after, 0)                 # everyone in your world is out: round
            rs.advance()
            rs.advance()
            self.assertIsInstance(self.app.screen, expect)
            if expect is FinaleScreen:
                self.key(pygame.K_RETURN)
                self.click_btn("continue")
                self.assertIsInstance(self.app.screen, MeadowScreen)
        self.assertTrue(data.get("finale_seen"))


class Revisits(UITestCase):
    """Any tower you've reached can be climbed again, as often as you like;
    every climb is generated fresh, with the same twists and checks."""

    def setUp(self):
        super().setUp()
        data = self.app.meta.data
        data["wins"] = 1
        data["friends"] = ["leaning", "hollow"]
        data["towers_seen"] = ["leaning", "hollow", "toadstool"]

    def test_every_climb_is_freshly_generated_with_the_same_rules(self):
        from prism.run import route_signature
        sigs, kinds = [], []
        for _ in range(4):
            self.app.climb_tower("hollow")
            run = self.app.run
            self.assertTrue(run.again)                          # its friend's already out
            self.assertEqual(run.twists(), ("holes",))          # same mechanics
            self.assertEqual(run.tier(), 2)                     # same difficulty for its place in your world
            sigs.append(route_signature(run.route))
            kinds.append(run.route.layers[-1][0].kind)
        for a, b in zip(sigs, sigs[1:]):
            self.assertNotEqual(a, b)                           # never the same floors twice running
        self.assertEqual(set(kinds), {"boss"})
        # and its fights pass the same checks as ever: solved, a par, twist tiles in place
        run = self.app.run
        i, node = next((i, n) for i, n in run.choices() if n.kind in ("fight", "elite"))
        self.app.enter_node(i)
        st = run.state
        self.assertIsNotNone(st.par)
        self.assertTrue(st.board.pairs)
        self.assertIsInstance(self.app.screen, CombatScreen)
        self.draw_ok()

    def test_a_fixed_seed_still_shuffles_every_visit(self):
        from prism.run import route_signature
        self.app.seed = 1234
        self.app.climb_tower("leaning")
        a = route_signature(self.app.run.route)
        self.app.climb_tower("leaning")
        self.assertNotEqual(a, route_signature(self.app.run.route))

    def test_the_window_and_the_keeper_both_let_you_back_in(self):
        from prism.meadow import Keeper
        self.app.show_hub()
        ms = self.app.screen
        z = ms.world.zones[0]
        wx, wy, wr = z.window
        ms.tri.x, ms.tri.air, ms.tri.vx, ms.tri.vy = z.wall - ms.tri.r + 4, wy, 300.0, 0.0
        ms._tower_physics(ms.tri)
        self.assertEqual(ms.entering, "leaning")                # in through the window, friend or no friend
        self.app.show_hub(start_x=z.wall - 60)
        ms = self.app.screen
        keeper = next(k for k in ms.keepers if k.tower == "leaning")
        self.assertIsInstance(keeper, Keeper)
        ms.tri.x, ms.tri.vx = keeper.x, 0.0
        ms.everyone = [keeper]
        for _ in range(len(keeper.lines) + 1):
            self.key(pygame.K_SPACE)
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertEqual(self.app.run.tower, "leaning")
        self.assertTrue(self.app.run.again)

    def test_a_climb_for_fun_ends_with_a_roll_down_and_back_to_its_door(self):
        data = self.app.meta.data
        data["sides"] = {"leaning": 10}
        self.app.climb_tower("leaning")
        self.app.run.finished = "rescued"
        self.app.record()
        self.app.replace(RescueScreen(self.app))
        rs = self.app.screen
        self.assertTrue(rs.again)
        self.assertEqual(rs.you_before, rs.you_after)            # nobody new out: you're as round as before
        self.app.tick(1.0)
        self.draw_ok()
        for _ in range(300):
            self.app.tick(0.05)
            if rs.phase == "landed":
                break
        self.assertEqual(rs.phase, "landed")
        self.app.tick(1.2)
        self.draw_ok()
        self.key(pygame.K_RETURN)
        ms = self.app.screen
        self.assertIsInstance(ms, MeadowScreen)
        self.assertLess(abs(ms.tri.x - (ms.world.zones[0].wall - 260)), 5)
        self.assertEqual(data["friends"], ["leaning", "hollow"])
        self.assertEqual(data["sides"]["leaning"], 10)           # its friend didn't grow from this
        self.assertEqual(data["tower_climbs"]["leaning"], 1)

    def test_the_map_goes_anywhere_youve_reached(self):
        from prism.worldmap import MapScreen
        self.app.show_hub()
        self.key(pygame.K_m)
        mp = self.app.screen
        self.assertIsInstance(mp, MapScreen)
        self.draw_ok()
        tags = {b.tag for b in mp.buttons}
        self.assertIn("climb:leaning", tags)
        self.assertIn("climb:toadstool", tags)                  # reached: someone's at its window
        self.assertNotIn("climb:icicle", tags)                  # not reached yet
        self.click_btn("go:toadstool")
        ms = self.app.screen
        self.assertIsInstance(ms, MeadowScreen)
        self.assertEqual(ms.world.zone_at(ms.tri.x).tower, "toadstool")
        self.key(pygame.K_m)
        self.click_btn("climb:hollow")
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertEqual(self.app.run.tower, "hollow")
        self.assertEqual(len(self.app.stack), 1)                # the map's gone, not left underneath


class SlotInAnyFloor(UITestCase):
    """The Sorter remembers the floors you've reached: New Run lets you slot in at any of them."""

    def test_new_run_from_any_floor_youve_reached(self):
        from prism.screens import FloorPickScreen
        data = self.app.meta.data
        data["seen_intro"] = True
        self.click_btn("new")
        self.assertIsInstance(self.app.screen, RouteScreen)     # only the bottom so far: straight in
        self.assertEqual(self.app.run.act, 1)
        data["best_act"] = 2
        self.app.to_title()
        self.click_btn("new")
        pick = self.app.screen
        self.assertIsInstance(pick, FloorPickScreen)
        self.draw_ok()
        self.assertFalse(self.btn("floor:3").enabled)           # not reached yet
        self.click_btn("floor:2")
        run = self.app.run
        self.assertEqual(run.act, 2)
        self.assertEqual(run.form()["shape"], "square")          # grown as if the first Keeper were beaten
        self.assertIn("halo", run.player.patterns)
        self.assertEqual(run.gold, 45)

    def test_beating_a_keeper_marks_the_next_floor_reached(self):
        self.app.meta.data["seen_intro"] = True
        self.app.new_run()
        run = self.app.run
        run.layer = len(run.route.layers) - 1
        run.node = 0
        run.state = None
        run.leave_node = lambda: setattr(run, "act", 2)
        self.app.leave_node()
        self.assertEqual(self.app.meta.data["best_act"], 2)
        self.assertEqual(self.app.floors_reached(), 2)
