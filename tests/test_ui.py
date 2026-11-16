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
from prism.screens import CombatScreen, HelpScreen, RouteScreen, TitleScreen
from prism.state import cast, move, wait


class UITestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(meta_path=os.path.join(self.tmp.name, "meta.json"), seed=21)

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
        self.assertEqual(labels, ["New Run", "How to Play", "Quit"])

    def test_new_run_button_and_enter_key(self):
        self.click(self.app.screen.buttons[0].rect.center)
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.app.to_title()
        self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_help_open_close_twice(self):
        for _ in range(2):
            self.click(self.app.screen.buttons[1].rect.center)
            self.assertIsInstance(self.app.screen, HelpScreen)
            self.draw_ok()
            self.click(self.app.screen.buttons[0].rect.center)
            self.assertIsInstance(self.app.screen, TitleScreen)
        self.key(pygame.K_h)
        self.assertIsInstance(self.app.screen, HelpScreen)
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, TitleScreen)

    def test_quit_button_key_and_window_close(self):
        self.click(self.app.screen.buttons[2].rect.center)
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
            self.assertIsInstance(self.app.screen, screen_cls, kind)
            self.draw_ok()

    def test_number_keys_pick_nodes(self):
        n = len(self.app.run.choices())
        self.key(pygame.K_1 + n - 1)
        self.assertEqual(self.app.run.node, n - 1)

    def test_wrong_key_number_is_ignored(self):
        self.key(pygame.K_9)
        self.assertIsInstance(self.app.screen, RouteScreen)

    def test_escape_explains_itself(self):
        self.key(pygame.K_ESCAPE)
        self.assertTrue(self.app.screen.msg)

    def test_abandon_needs_two_clicks_and_esc_cancels(self):
        self.click_btn("")
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertIn("confirm", self.app.screen.msg.lower())
        self.key(pygame.K_ESCAPE)
        self.assertIn("cancel", self.app.screen.msg.lower())
        self.assertFalse(self.app.screen.confirm)
        self.click_btn("")
        self.click_btn("")
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.app.meta.data["runs"], 1)
        self.assertEqual(self.app.run.finished, "defeat")

    def test_route_draw_through_a_whole_act(self):
        self.draw_ok()
        self.app.run.relics.append("crimson_lens")
        self.draw_ok()


class CombatInput(UITestCase):
    def setUp(self):
        super().setUp()
        # enemy far away and harmless (own colour so casts at it are absorbed or hit predictably)
        self.cs = self.combat([("pawn", 4, 6, "B", 30)], walls=[(0, 2)])

    def test_shape_buttons_each_click_twice(self):
        for s in SHAPES:
            for _ in range(2):
                b = self.click_btn("shape:" + s)
                self.assertEqual(self.cs.shape, s)
                self.assertEqual(self.cs.tool, "cast")
                self.assertTrue(self.btn("shape:" + s).active)
        self.assertEqual(self.cs.queue, [])

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

    def test_cast_twice_in_a_row_keeps_working(self):
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
        self.assertEqual(len(self.cs.queue), 1)
        self.click(self.tile_pos(4, 6))
        self.assertEqual(len(self.cs.queue), 2)
        self.assertEqual(self.cs.queue[1].shape, "circle")

    def test_cast_lands_in_the_queue_with_the_chosen_shape_colour_and_target(self):
        self.click_btn("shape:square")
        self.click_btn("color:G")
        self.click(self.tile_pos(4, 6))
        a = self.cs.queue[0]
        self.assertEqual((a.kind, a.shape, a.color, a.tx, a.ty), ("cast", "square", "G", 4, 6))

    def test_out_of_range_cast_is_rejected_with_a_message_and_queue_unchanged(self):
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(0, 0))
        self.assertEqual(self.cs.queue, [])
        self.assertIn("range", self.cs.msg.lower())

    def test_triangle_off_line_is_rejected(self):
        self.key(pygame.K_1)
        self.key(pygame.K_r)
        self.click(self.tile_pos(5, 7))
        self.assertEqual(self.cs.queue, [])
        self.assertIn("straight", self.cs.msg.lower())

    def test_mixed_colours_spend_both_charges_in_the_preview(self):
        self.key(pygame.K_3)
        self.key(pygame.K_m)
        self.click(self.tile_pos(4, 6))
        pal = self.cs.cur.player.palette
        self.assertEqual((pal["R"], pal["B"], pal["G"]), (2, 2, 3))

    def test_charges_run_out_inside_one_plan(self):
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        for _ in range(3):
            self.click(self.tile_pos(4, 6))
        self.assertEqual(len(self.cs.queue), 3)
        self.assertFalse(self.btn("color:R").enabled)
        self.click(self.tile_pos(4, 6))
        self.assertEqual(len(self.cs.queue), 3)
        self.assertIn("charges", self.cs.msg.lower())

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
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.key(pygame.K_ESCAPE)
        self.assertIsNone(self.cs.color)
        self.assertEqual(self.cs.tool, "move")
        self.assertIn("cancel", self.cs.msg.lower())
        self.click(self.tile_pos(4, 6))            # no longer armed: must not cast
        self.assertEqual(self.cs.queue, [])
        self.key(pygame.K_r)
        self.click((600, 600), button=3)
        self.assertIsNone(self.cs.color)
        self.key(pygame.K_ESCAPE)
        self.assertIn("nothing", self.cs.msg.lower())

    def test_shape_keys_and_colour_keys(self):
        for k, s in ((pygame.K_1, "triangle"), (pygame.K_2, "square"), (pygame.K_3, "circle")):
            self.key(k)
            self.assertEqual(self.cs.shape, s)
        for k, c in ((pygame.K_r, "R"), (pygame.K_g, "G"), (pygame.K_b, "B"),
                     (pygame.K_y, "Y"), (pygame.K_c, "C"), (pygame.K_m, "M")):
            self.key(k)
            self.assertEqual(self.cs.color, c)

    def test_unknown_key_does_nothing_and_does_not_crash(self):
        self.key(pygame.K_F5)
        self.key(pygame.K_TAB)
        self.assertEqual(self.cs.queue, [])

    def test_help_overlay_returns_to_the_same_fight(self):
        self.key(pygame.K_SPACE)
        self.click_btn("help")
        self.assertIsInstance(self.app.screen, HelpScreen)
        self.key(pygame.K_ESCAPE)
        self.assertIs(self.app.screen, self.cs)
        self.assertEqual(len(self.cs.queue), 1)

    def test_hovering_draws_without_error_and_flags_bad_targets(self):
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        for pos in (self.tile_pos(4, 6), self.tile_pos(0, 0), (700, 300), (10, 10)):
            self.hover(pos)
            self.draw_ok()
        self.key(pygame.K_ESCAPE)
        self.hover(self.tile_pos(4, 7))
        self.draw_ok()


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
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
        self.click_btn("resolve")
        self.finish_anim("key")
        e = cs.state.enemies[0]
        self.assertEqual(e.hp, 28)

    def test_telegraph_comes_from_the_exact_preview(self):
        cs = self.combat([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        hits = [e for e in cs.pre_events if e["t"] == "enemy_attack" and e["hit"]]
        self.assertTrue(hits)
        self.key(pygame.K_RIGHT)
        hits = [e for e in cs.pre_events if e["t"] == "enemy_attack" and e["hit"]]
        self.assertFalse(hits)               # stepping aside dodges the telegraphed strike
        self.draw_ok()

    def test_seven_enemies_draw(self):
        cs = self.combat([("pawn", x, 0, "R") for x in range(7)])
        self.draw_ok()
        self.click_btn("resolve")
        self.app.tick(0.3)
        self.draw_ok()

    def test_victory_flows_to_reward_then_route(self):
        cs = self.combat([("pawn", 4, 6, "B", 2)])
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
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
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        hp, relics = self.app.run.player.hp, list(self.app.run.relics)
        self.click_btn("skip")
        self.assertEqual(self.app.run.relics, relics)
        self.key(pygame.K_RETURN)
        self.assertIsInstance(self.app.screen, RouteScreen)
        cs = self.combat([("pawn", 4, 6, "B", 2)])
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.key(pygame.K_2)
        self.assertTrue(self.btn("continue").enabled)

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
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.click_btn("reward0")
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, RouteScreen)
        self.assertEqual(run.act, 2)
        self.assertIn("Act 2", self.app.screen.msg)

    def test_final_boss_wins_the_run(self):
        self.app.new_run()
        run = self.app.run
        run.act = 3
        run.route.layers[0][0].kind = "boss"
        self.app.enter_node(0)
        st = make_state([("prism", 4, 6, "B", 2)])
        run.state, run.player = st, st.player
        self.app.replace(CombatScreen(self.app, run))
        self.key(pygame.K_3)
        self.key(pygame.K_r)
        self.click(self.tile_pos(4, 6))
        self.key(pygame.K_RETURN)
        self.finish_anim("key")
        self.click_btn("skip")
        self.click_btn("continue")
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.app.run.finished, "victory")
        self.assertEqual(self.app.meta.data["wins"], 1)
        self.draw_ok()


class NodeScreens(UITestCase):
    def test_shop_every_item_every_path(self):
        sh = self.node("shop")
        run = self.app.run
        self.draw_ok()
        n = len(run.shop)
        for i in range(n):
            self.click_btn("item%d" % i)
            self.assertIn("gold", sh.msg.lower())
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
            for cid, _label in ev["choices"]:
                self.app.new_run()
                run = self.app.run
                run.route.layers[0][0].kind = "event"
                self.app.enter_node(0)
                run.event = ev
                self.app.replace(EventScreen(self.app))
                run.gold = 50
                self.draw_ok()
                self.click_btn("choice:" + cid)
                self.assertTrue(self.app.screen.msg)
                self.assertTrue(self.btn("continue").enabled, (ev["id"], cid))
                self.assertFalse(self.btn("choice:" + cid).enabled)
                self.click_btn("continue")
                self.assertIsInstance(self.app.screen, RouteScreen)

    def test_event_unaffordable_choice_explains_and_stays(self):
        self.node("event")
        run = self.app.run
        run.event = [e for e in EVENTS if e["id"] == "trader"][0]
        self.app.replace(EventScreen(self.app))
        run.gold = 0
        self.click_btn("choice:buy")
        self.assertIn("gold", self.app.screen.msg.lower())
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
            pygame.K_h, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_F1]

    def test_random_input_storm(self):
        for seed in (1, 2, 3, 4):
            rng = random.Random(seed)
            self.app = App(meta_path=os.path.join(self.tmp.name, "m%d.json" % seed), seed=seed)
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
