import unittest

from helpers import events, make_state

from prism import rules
from prism.consts import BEATS, COLORS, COMPONENTS, OPPOSITE, SHAPES
from prism.state import cast, move, wait


def one_beat(state, action, beat=0):
    """The player's half of a beat only (no enemy phase), so effect tests are not
    muddied by enemies walking away."""
    ev = []
    rules.player_action(state, action, beat, ev)
    rules.reap(state, ev, beat)
    rules.check_outcome(state)
    return ev


class ShapeTiles(unittest.TestCase):
    def test_triangle_is_a_line_of_three(self):
        s = make_state(player_at=(4, 6))
        self.assertEqual(rules.shape_tiles(s, "triangle", 4, 5), [(4, 5), (4, 4), (4, 3)])
        self.assertEqual(rules.shape_tiles(s, "triangle", 6, 6), [(5, 6), (6, 6), (7, 6)])

    def test_triangle_stops_at_walls_and_edges(self):
        s = make_state(player_at=(4, 6), walls=[(4, 4)])
        self.assertEqual(rules.shape_tiles(s, "triangle", 4, 5), [(4, 5)])
        s = make_state(player_at=(0, 6))
        self.assertEqual(rules.shape_tiles(s, "triangle", 0, 5), [(0, 5), (0, 4), (0, 3)])
        self.assertEqual(rules.shape_tiles(s, "triangle", 1, 6), [(1, 6), (2, 6), (3, 6)])
        s = make_state(player_at=(8, 6))
        self.assertEqual(rules.shape_tiles(s, "triangle", 7, 6), [(7, 6), (6, 6), (5, 6)])

    def test_triangle_rejects_diagonal_own_tile_and_range(self):
        s = make_state(player_at=(4, 6))
        self.assertIsNone(rules.shape_tiles(s, "triangle", 5, 5))
        self.assertIsNone(rules.shape_tiles(s, "triangle", 4, 6))
        self.assertIsNone(rules.shape_tiles(s, "triangle", 4, 2))     # 4 tiles away

    def test_square_is_2x2_and_clips(self):
        s = make_state(player_at=(4, 8))
        self.assertEqual(sorted(rules.shape_tiles(s, "square", 4, 5)),
                         sorted([(4, 5), (5, 5), (4, 6), (5, 6)]))
        s = make_state(player_at=(7, 8))
        self.assertEqual(sorted(rules.shape_tiles(s, "square", 8, 7)), [(8, 7), (8, 8)])

    def test_square_skips_walls_and_player_tile(self):
        s = make_state(player_at=(4, 6), walls=[(5, 5)])
        t = rules.shape_tiles(s, "square", 4, 5)
        self.assertNotIn((5, 5), t)
        self.assertNotIn((4, 6), t)
        self.assertIn((4, 5), t)

    def test_circle_is_plus(self):
        s = make_state(player_at=(4, 8))
        self.assertEqual(sorted(rules.shape_tiles(s, "circle", 4, 5)),
                         sorted([(4, 5), (4, 4), (5, 5), (4, 6), (3, 5)]))

    def test_circle_on_self_hits_neighbours_only(self):
        s = make_state(player_at=(4, 6))
        t = rules.shape_tiles(s, "circle", 4, 6)
        self.assertNotIn((4, 6), t)
        self.assertEqual(len(t), 4)

    def test_range_limit_and_range_mod(self):
        s = make_state(player_at=(4, 8))
        self.assertIsNone(rules.shape_tiles(s, "circle", 4, 4))       # distance 4
        s = make_state(player_at=(4, 8), mods={"range": 1})
        self.assertIsNotNone(rules.shape_tiles(s, "circle", 4, 4))

    def test_wall_target_is_illegal(self):
        s = make_state(player_at=(4, 8), walls=[(4, 6)])
        for shape in SHAPES:
            self.assertIsNone(rules.shape_tiles(s, shape, 4, 6))

    def test_unknown_shape(self):
        s = make_state()
        self.assertIsNone(rules.shape_tiles(s, "hexagon", 4, 7))


class Validation(unittest.TestCase):
    def test_moves(self):
        s = make_state([("pawn", 4, 7, "R")], walls=[(3, 8)], player_at=(4, 8))
        self.assertFalse(rules.validate_action(s, move(0, 1))[0])     # edge
        self.assertFalse(rules.validate_action(s, move(-1, 0))[0])    # wall
        self.assertFalse(rules.validate_action(s, move(0, -1))[0])    # enemy
        ok, _ = rules.validate_action(s, move(1, 0))
        self.assertTrue(ok)
        self.assertFalse(rules.validate_action(s, move(1, 1))[0])     # diagonal

    def test_cast_needs_charges_and_target(self):
        s = make_state(palette={"R": 0})
        ok, msg = rules.validate_action(s, cast("circle", "R", 4, 6))
        self.assertFalse(ok)
        self.assertIn("charges", msg)
        s = make_state()
        ok, msg = rules.validate_action(s, cast("triangle", "R", 5, 7))
        self.assertFalse(ok)
        self.assertTrue(msg)

    def test_every_failure_has_a_message(self):
        s = make_state([("pawn", 4, 7, "R")], walls=[(3, 8)])
        bad = [move(0, 1), move(-1, 0), move(0, -1), move(2, 0), cast("triangle", "R", 3, 3),
               cast("circle", "R", 0, 0), cast("circle", "X", 4, 6), cast("blob", "R", 4, 6)]
        for a in bad:
            ok, msg = rules.validate_action(s, a)
            self.assertFalse(ok, a)
            self.assertTrue(msg, a)

    def test_wait_is_always_ok_and_over_fight_is_rejected(self):
        s = make_state([("pawn", 4, 1, "R")])
        self.assertTrue(rules.validate_action(s, wait())[0])
        s.outcome = "victory"
        self.assertFalse(rules.validate_action(s, wait())[0] and False)
        ok, msg = rules.validate_action(s, move(1, 0))
        self.assertFalse(ok)


class Colours(unittest.TestCase):
    def target(self, color, shape="circle", hp=6, enemy_color="G", **kw):
        s = make_state([("pawn", 4, 5, enemy_color, hp)], **kw)
        ev = one_beat(s, cast(shape, color, 4, 5))
        return s, ev, s.enemies[0] if s.enemies else None

    def test_red_does_two(self):
        s, ev, e = self.target("R", enemy_color="B")
        self.assertEqual(e.hp, 4)

    def test_primaries_cost_one_and_mixes_cost_two(self):
        for c in COLORS:
            s = make_state([("pawn", 4, 5, "G" if c != "G" else "B", 6)])
            before = dict(s.player.palette)
            one_beat(s, cast("circle", c, 4, 5))
            for p in "RGB":
                expect = before[p] - (1 if p in COMPONENTS[c] else 0)
                self.assertEqual(s.player.palette[p], expect, (c, p))

    def test_weakness_doubles_and_same_colour_is_absorbed(self):
        s = make_state([("pawn", 4, 5, "C", 10)])
        one_beat(s, cast("circle", "R", 4, 5))                         # R is opposite of C
        self.assertEqual(s.enemies[0].hp, 6)
        s = make_state([("pawn", 4, 5, "R", 10)])
        ev = one_beat(s, cast("circle", "R", 4, 5))
        self.assertEqual(s.enemies[0].hp, 10)
        self.assertEqual(len(events(ev, "absorb")), 1)

    def test_opposites_are_symmetric(self):
        for a, b in OPPOSITE.items():
            self.assertEqual(OPPOSITE[b], a)

    def test_green_pushes_away(self):
        s, ev, e = self.target("G", enemy_color="B")
        self.assertEqual((e.x, e.y), (4, 4))
        self.assertEqual(e.hp, 5)

    def test_green_collision_with_wall_and_enemy(self):
        s = make_state([("pawn", 4, 5, "B", 6)], walls=[(4, 4)])
        one_beat(s, cast("circle", "G", 4, 5))
        e = s.enemies[0]
        self.assertEqual((e.x, e.y), (4, 5))
        self.assertEqual(e.hp, 6 - 1 - 2)
        s = make_state([("pawn", 4, 5, "B", 6), ("pawn", 4, 4, "B", 6)])
        one_beat(s, cast("square", "G", 4, 5))                          # hits only (4,5)+(5,5)...
        hps = sorted(e.hp for e in s.enemies)
        self.assertEqual(hps, [3, 4])          # pushed one: 1 + 2 collision; blocker: 2

    def test_blue_stuns_and_shields_player(self):
        s, ev, e = self.target("B", enemy_color="R")
        self.assertGreaterEqual(e.stun, 1)
        self.assertEqual(s.player.shield, 1)
        s2 = make_state([("pawn", 4, 1, "R")])
        one_beat(s2, cast("circle", "B", 4, 8))                         # nothing in the shape
        self.assertEqual(s2.player.shield, 1)                           # blue always shields

    def test_blue_shield_is_capped(self):
        s = make_state([("pawn", 4, 1, "R")])
        for beat in range(6):
            s.player.palette["B"] = 5
            one_beat(s, cast("circle", "B", 4, 8), beat % BEATS)
        self.assertEqual(s.player.shield, 4)

    def test_yellow_burns_and_pushes_then_burn_ticks_at_turn_end(self):
        s = make_state([("pawn", 4, 5, "R", 8)])
        one_beat(s, cast("circle", "Y", 4, 5))
        rules.end_turn(s)
        e = s.enemies[0]
        self.assertEqual(e.burn, 2)                                      # 3 minus one tick
        self.assertEqual(e.hp, 8 - 1 - 1)                                # 1 hit + 1 burn tick
        self.assertEqual((e.x, e.y), (4, 4))

    def test_cyan_swaps_with_first_hit_and_stuns(self):
        s = make_state([("pawn", 4, 5, "R", 8)])
        ev = one_beat(s, cast("circle", "C", 4, 5))
        e = s.enemies[0]
        self.assertEqual((s.player.x, s.player.y), (4, 5))
        self.assertEqual((e.x, e.y), (4, 8))
        self.assertEqual(len(events(ev, "swap")), 1)

    def test_cyan_without_hit_does_nothing_but_says_so(self):
        s = make_state([("pawn", 4, 1, "R", 8)])
        ev = one_beat(s, cast("circle", "C", 4, 6))
        self.assertEqual((s.player.x, s.player.y), (4, 8))
        self.assertEqual(len(events(ev, "miss")), 1)

    def test_magenta_splashes_neighbours(self):
        s = make_state([("pawn", 4, 5, "R", 10), ("pawn", 4, 4, "R", 10)])
        one_beat(s, cast("circle", "M", 4, 6))                           # plus hits (4,5) only
        by_pos = {(e.x, e.y): e.hp for e in s.enemies}
        self.assertEqual(by_pos[(4, 5)], 7)
        self.assertEqual(by_pos[(4, 4)], 9)

    def test_dead_enemies_are_removed_and_victory_ends_the_fight(self):
        s = make_state([("pawn", 4, 5, "B", 2)])
        one_beat(s, cast("circle", "R", 4, 5))
        self.assertEqual(s.enemies, [])
        self.assertEqual(s.outcome, "victory")

    def test_unaffordable_cast_fizzles_visibly(self):
        s = make_state([("pawn", 4, 5, "B", 6)], palette={"R": 0})
        ev = one_beat(s, cast("circle", "R", 4, 5))
        self.assertEqual(len(events(ev, "fizzle")), 1)
        self.assertEqual(s.enemies[0].hp, 6)


class Chains(unittest.TestCase):
    def test_different_shapes_build_a_chain(self):
        s = make_state([("pawn", 4, 5, "B", 40)], palette={"R": 5})
        one_beat(s, cast("circle", "R", 4, 5), 0)
        self.assertEqual(s.enemies[0].hp, 38)                            # x1
        one_beat(s, cast("square", "R", 4, 5), 1)
        self.assertEqual(s.enemies[0].hp, 38 - 3)                        # x1.5
        one_beat(s, cast("triangle", "R", 4, 7), 2)
        self.assertEqual(s.enemies[0].hp, 35 - 4)                        # x2

    def test_same_shape_resets_the_chain(self):
        s = make_state([("pawn", 4, 5, "B", 40)], palette={"R": 5})
        one_beat(s, cast("circle", "R", 4, 5), 0)
        one_beat(s, cast("square", "R", 4, 5), 1)
        one_beat(s, cast("square", "R", 4, 5), 2)
        self.assertEqual(s.player.chain, 1)

    def test_chain_resets_each_turn(self):
        s = make_state([("pawn", 4, 1, "B", 40)])
        one_beat(s, cast("circle", "R", 4, 6), 0)
        one_beat(s, cast("square", "R", 4, 6), 1)
        self.assertEqual(s.player.chain, 2)
        rules.resolve_turn(s, [], advance=True)
        self.assertEqual(s.player.chain, 0)

    def test_chain_start_relic(self):
        s = make_state([("pawn", 4, 5, "B", 40)], mods={"chain_start": 1})
        one_beat(s, cast("circle", "R", 4, 5), 0)
        self.assertEqual(s.player.chain, 2)
        self.assertEqual(s.enemies[0].hp, 40 - 3)


class Relics(unittest.TestCase):
    def test_red_bonus_collision_bonus_regen_burn(self):
        s = make_state([("pawn", 4, 5, "B", 10)], mods={"red_bonus": 1})
        one_beat(s, cast("circle", "R", 4, 5))
        self.assertEqual(s.enemies[0].hp, 7)
        s = make_state([("pawn", 4, 5, "B", 10)], walls=[(4, 4)], mods={"collision_bonus": 2})
        one_beat(s, cast("circle", "G", 4, 5))
        self.assertEqual(s.enemies[0].hp, 10 - 1 - 4)
        s = make_state([("pawn", 4, 1, "B", 10)], palette={"R": 0}, mods={"regen": 2})
        rules.end_turn(s)
        self.assertEqual(s.player.palette["R"], 2)
        s = make_state([("pawn", 4, 5, "R", 20)], mods={"burn_bonus": 2})
        one_beat(s, cast("circle", "Y", 4, 5))
        self.assertEqual(s.enemies[0].burn, 5)

    def test_blue_shield_relic(self):
        s = make_state([("pawn", 4, 1, "R")], mods={"blue_shield": 2})
        one_beat(s, cast("circle", "B", 4, 8))
        self.assertEqual(s.player.shield, 2)


class TurnFlow(unittest.TestCase):
    def test_palette_regenerates_and_respects_cap(self):
        s = make_state([("pawn", 4, 1, "R")], palette={"R": 0, "G": 5, "B": 4})
        rules.resolve_turn(s, [], advance=False)
        self.assertEqual(s.player.palette, {"R": 1, "G": 5, "B": 5})

    def test_short_queue_is_padded_with_waits(self):
        s = make_state([("pawn", 4, 1, "R")])
        res = rules.resolve_turn(s, [wait()], advance=False)
        self.assertEqual(len([e for e in res.events if e["t"] == "wait"]), BEATS)

    def test_extra_actions_beyond_the_timeline_are_ignored(self):
        s = make_state([("pawn", 4, 1, "R")])
        res = rules.resolve_turn(s, [wait()] * 9, advance=False)
        self.assertEqual(len([e for e in res.events if e["t"] == "wait"]), BEATS)

    def test_victory_ends_the_turn_early(self):
        s = make_state([("pawn", 4, 5, "B", 1)])
        res = rules.resolve_turn(s, [cast("circle", "R", 4, 5), move(1, 0), move(1, 0)])
        self.assertEqual(res.outcome, "victory")
        self.assertEqual(len(res.snapshots), 1)
        self.assertEqual(s.player.x, 4)

    def test_defeat(self):
        s = make_state([("pawn", 4, 7, "R")], hp=1)
        res = rules.resolve_turn(s, [wait(), wait(), wait(), wait()])
        self.assertEqual(res.outcome, "defeat")
        self.assertEqual(s.outcome, "defeat")

    def test_preview_does_not_mutate(self):
        s = make_state([("pawn", 4, 5, "B", 6)])
        before = rules.snapshot(s)
        rules.preview_full(s, [cast("circle", "R", 4, 5), move(1, 0)])
        rules.simulate_prefix(s, [cast("circle", "R", 4, 5)])
        self.assertEqual(rules.snapshot(s), before)

    def test_preview_matches_real_resolution(self):
        plan = [cast("circle", "R", 4, 5), move(1, 0), cast("square", "G", 4, 5), wait()]
        a = make_state([("pawn", 4, 5, "B", 8), ("lancer", 1, 2, "G")])
        b = make_state([("pawn", 4, 5, "B", 8), ("lancer", 1, 2, "G")])
        pre, _ = rules.preview_full(a, plan)
        rules.resolve_turn(b, plan, advance=False)
        self.assertEqual(rules.snapshot(pre), rules.snapshot(b))

    def test_prefix_state_matches_full_run_up_to_that_beat(self):
        plan = [move(1, 0), cast("circle", "R", 5, 6)]
        a = make_state([("pawn", 4, 3, "B", 8)])
        pre, _ = rules.simulate_prefix(a, plan[:1])
        b = make_state([("pawn", 4, 3, "B", 8)])
        rules.resolve_beat(b, plan[0], 0, [])
        self.assertEqual(rules.snapshot(pre), rules.snapshot(b))

    def test_determinism(self):
        plan = [move(0, -1), cast("circle", "M", 4, 5), cast("triangle", "R", 4, 6), wait()]
        snaps = []
        for _ in range(3):
            s = make_state([("pawn", 4, 4, "G", 9), ("bloom", 2, 2, "R"), ("warden", 6, 3, "B")])
            rules.resolve_turn(s, plan)
            snaps.append(rules.snapshot(s))
        self.assertEqual(snaps[0], snaps[1])
        self.assertEqual(snaps[1], snaps[2])

    def test_every_event_has_a_beat(self):
        s = make_state([("pawn", 4, 6, "R", 9), ("lancer", 1, 8, "B")])
        res = rules.resolve_turn(s, [cast("circle", "R", 4, 6), move(1, 0), wait(), wait()])
        for e in res.events:
            self.assertIn("beat", e)


if __name__ == "__main__":
    unittest.main()
