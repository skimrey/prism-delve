import unittest

from helpers import events, make_state

from prism import rules
from prism.consts import BEAM_LEN, BEATS, COLORS, COMPONENTS, OPPOSITE, PATTERN_ORDER, SLANT_LEN
from prism.state import cast, move, wait

UP = (0, -1)


def beam_up(color, shape="square"):
    """From the default start (4, 8) a Beam up covers (4, 7) .. (4, 4)."""
    return cast("beam", shape, color, *UP)


def one_beat(state, action, beat=0):
    """The player's half of a beat only (no enemy phase), so effect tests are not
    muddied by enemies walking away."""
    ev = []
    rules.player_action(state, action, beat, ev)
    rules.reap(state, ev, beat)
    rules.check_outcome(state)
    return ev


class Patterns(unittest.TestCase):
    def test_beam_is_a_straight_line_to_the_edge(self):
        s = make_state(player_at=(4, 6))
        self.assertEqual(rules.pattern_tiles(s, "beam", 0, -1),
                         [(4, 5), (4, 4), (4, 3), (4, 2), (4, 1), (4, 0)])
        self.assertEqual(rules.pattern_tiles(s, "beam", 1, 0), [(5, 6), (6, 6), (7, 6), (8, 6)])
        s = make_state(player_at=(0, 4))
        self.assertEqual(len(rules.pattern_tiles(s, "beam", 1, 0)), BEAM_LEN)

    def test_rays_stop_at_walls_and_edges(self):
        s = make_state(player_at=(4, 6), walls=[(4, 4)])
        self.assertEqual(rules.pattern_tiles(s, "beam", 0, -1), [(4, 5)])
        s = make_state(player_at=(0, 6))
        self.assertIsNone(rules.pattern_tiles(s, "beam", -1, 0))          # straight into the edge
        self.assertIsNone(rules.pattern_tiles(s, "slant", -1, -1))
        s = make_state(player_at=(4, 6), walls=[(4, 5)])
        self.assertIsNone(rules.pattern_tiles(s, "beam", 0, -1))          # straight into a wall

    def test_slant_is_a_diagonal_line_to_the_edge(self):
        s = make_state(player_at=(4, 6))
        self.assertEqual(rules.pattern_tiles(s, "slant", 1, -1), [(5, 5), (6, 4), (7, 3), (8, 2)])
        s = make_state(player_at=(0, 8))
        self.assertEqual(len(rules.pattern_tiles(s, "slant", 1, -1)), SLANT_LEN)

    def test_rays_need_the_right_kind_of_aim(self):
        s = make_state(player_at=(4, 6))
        self.assertIsNone(rules.pattern_tiles(s, "beam", 1, 1))
        self.assertIsNone(rules.pattern_tiles(s, "slant", 0, 1))
        self.assertIsNone(rules.pattern_tiles(s, "beam", 0, 0))

    def test_halo_is_the_eight_around_you(self):
        s = make_state(player_at=(4, 6), walls=[(5, 5)])
        t = rules.pattern_tiles(s, "halo")
        self.assertEqual(len(t), 7)
        self.assertNotIn((5, 5), t)
        self.assertNotIn((4, 6), t)

    def test_leap_jumps_over_walls(self):
        s = make_state(player_at=(4, 6), walls=[(4, 5), (4, 4), (5, 5)])
        t = rules.pattern_tiles(s, "leap")
        self.assertIn((5, 4), t)
        self.assertEqual(sorted(t), sorted([(5, 4), (6, 5), (6, 7), (5, 8), (3, 8), (2, 7), (2, 5),
                                            (3, 4)]))
        s = make_state(player_at=(0, 8))
        self.assertEqual(sorted(rules.pattern_tiles(s, "leap")), [(1, 6), (2, 7)])

    def test_lob_lands_exactly_three_away(self):
        s = make_state(player_at=(4, 8))
        self.assertEqual(sorted(rules.pattern_tiles(s, "lob", 0, -3)),
                         sorted([(4, 5), (4, 4), (5, 5), (4, 6), (3, 5)]))
        self.assertIsNone(rules.pattern_tiles(s, "lob", 0, -2))
        s = make_state(player_at=(4, 8), walls=[(4, 5)])
        self.assertIsNone(rules.pattern_tiles(s, "lob", 0, -3))          # can't land on a wall

    def test_every_pattern_has_aims_and_offsets(self):
        for pt in PATTERN_ORDER:
            aims = rules.pattern_aims(pt)
            self.assertTrue(aims)
            for aim in aims:
                self.assertTrue(rules.pattern_offsets(pt, *aim), (pt, aim))

    def test_pierce_facet_lets_rays_through_one_wall(self):
        s = make_state(player_at=(4, 8), walls=[(4, 6), (4, 3)], mods={"pierce": 1})
        self.assertEqual(rules.pattern_tiles(s, "beam", 0, -1), [(4, 7), (4, 5), (4, 4)])
        s = make_state(player_at=(4, 8), walls=[(5, 7)], mods={"pierce": 1})
        self.assertIn((6, 6), rules.pattern_tiles(s, "slant", 1, -1))
        self.assertNotIn((5, 7), rules.pattern_tiles(s, "halo"))      # Halo is not a ray


class ShapeFilter(unittest.TestCase):
    def test_light_only_touches_the_shape_it_is_cut_for(self):
        s = make_state([("pawn", 4, 6, "B", 9, "square"), ("pawn", 4, 5, "B", 9, "circle")])
        one_beat(s, beam_up("R", "circle"))
        by_pos = {(e.x, e.y): e.hp for e in s.enemies}
        self.assertEqual(by_pos[(4, 6)], 9)                 # passed straight through the square
        self.assertEqual(by_pos[(4, 5)], 6)

    def test_no_matching_shape_is_a_visible_miss_but_still_costs(self):
        s = make_state([("pawn", 4, 6, "B", 9, "square")])
        ev = one_beat(s, beam_up("R", "triangle"))
        self.assertEqual(s.enemies[0].hp, 9)
        self.assertEqual(len(events(ev, "miss")), 1)
        self.assertEqual(s.player.palette["R"], 2)

    def test_group_bonus_rewards_fitting_several_at_once(self):
        s = make_state([("pawn", 4, 7, "B", 20, "square"), ("pawn", 4, 6, "B", 20, "square"),
                        ("pawn", 4, 5, "B", 20, "square")])
        ev = one_beat(s, beam_up("R"))
        bonus = 2 * rules.GROUP_STEP
        self.assertEqual([e.hp for e in s.enemies], [20 - 3 - bonus] * 3)
        c = events(ev, "cast")[0]
        self.assertEqual((c["fits"], c["bonus"]), (3, bonus))

    def test_absorbed_shapes_do_not_count_toward_the_group(self):
        s = make_state([("pawn", 4, 7, "R", 20, "square"), ("pawn", 4, 6, "B", 20, "square")])
        one_beat(s, beam_up("R"))
        self.assertEqual([e.hp for e in s.enemies], [20, 17])

    def test_group_bonus_facet(self):
        s = make_state([("pawn", 4, 7, "B", 20), ("pawn", 4, 6, "B", 20)], mods={"group_bonus": 1})
        one_beat(s, beam_up("R"))
        self.assertEqual([e.hp for e in s.enemies], [20 - 3 - rules.GROUP_STEP - 1] * 2)

    def test_weakness_doubles_after_the_bonus(self):
        s = make_state([("pawn", 4, 7, "C", 20), ("pawn", 4, 6, "C", 20)])
        one_beat(s, beam_up("R"))
        self.assertEqual([e.hp for e in s.enemies], [20 - (3 + rules.GROUP_STEP) * 2] * 2)


class OncePerTurn(unittest.TestCase):
    def test_a_pattern_can_only_be_used_once_per_turn(self):
        s = make_state([("pawn", 4, 5, "B", 20)])
        a = beam_up("R")
        self.assertTrue(rules.validate_action(s, a)[0])
        one_beat(s, a)
        ok, msg = rules.validate_action(s, beam_up("G"))
        self.assertFalse(ok)
        self.assertIn("once per turn", msg)
        self.assertTrue(rules.validate_action(s, cast("halo", "square", "G"))[0])

    def test_patterns_come_back_next_turn(self):
        s = make_state([("pawn", 4, 1, "B", 20)])
        rules.resolve_turn(s, [beam_up("R")], advance=True)
        self.assertEqual(s.player.used, frozenset())
        self.assertTrue(rules.validate_action(s, beam_up("R"))[0])

    def test_unlearned_patterns_are_refused(self):
        s = make_state([("pawn", 4, 5, "B", 20)])
        ok, msg = rules.validate_action(s, cast("leap", "square", "R"))
        self.assertFalse(ok)
        self.assertIn("learned", msg)
        s.player.patterns = s.player.patterns + ["leap"]
        self.assertTrue(rules.validate_action(s, cast("leap", "square", "R"))[0])


class Validation(unittest.TestCase):
    def test_moves(self):
        s = make_state([("pawn", 4, 7, "R")], walls=[(3, 8)], player_at=(4, 8))
        self.assertFalse(rules.validate_action(s, move(0, 1))[0])     # edge
        self.assertFalse(rules.validate_action(s, move(-1, 0))[0])    # wall
        self.assertFalse(rules.validate_action(s, move(0, -1))[0])    # enemy
        ok, _ = rules.validate_action(s, move(1, 0))
        self.assertTrue(ok)
        self.assertFalse(rules.validate_action(s, move(1, 1))[0])     # diagonal

    def test_cast_needs_charges_and_a_legal_aim(self):
        s = make_state(palette={"R": 0})
        ok, msg = rules.validate_action(s, beam_up("R"))
        self.assertFalse(ok)
        self.assertIn("charges", msg)
        s = make_state()
        ok, msg = rules.validate_action(s, cast("beam", "square", "R", 1, 1))
        self.assertFalse(ok)
        self.assertIn("straight", msg)

    def test_every_failure_has_a_message(self):
        s = make_state([("pawn", 4, 7, "R")], walls=[(3, 8)])
        bad = [move(0, 1), move(-1, 0), move(0, -1), move(2, 0), cast("beam", "square", "R", 1, 1),
               cast("slant", "square", "R", 0, -1), cast("lob", "square", "R", 0, -1),
               cast("beam", "square", "X", 0, -1), cast("blob", "square", "R", 0, -1),
               cast("beam", "hexagon", "R", 0, -1), cast("beam", "square", "R", 0, 1)]
        for a in bad:
            ok, msg = rules.validate_action(s, a)
            self.assertFalse(ok, a)
            self.assertTrue(msg, a)

    def test_wait_is_always_ok_and_over_fight_is_rejected(self):
        s = make_state([("pawn", 4, 1, "R")])
        self.assertTrue(rules.validate_action(s, wait())[0])
        s.outcome = "victory"
        ok, msg = rules.validate_action(s, move(1, 0))
        self.assertFalse(ok)
        self.assertTrue(msg)


class Colours(unittest.TestCase):
    def target(self, color, hp=9, enemy_color="G", **kw):
        s = make_state([("pawn", 4, 6, enemy_color, hp)], **kw)
        ev = one_beat(s, beam_up(color))
        return s, ev, s.enemies[0] if s.enemies else None

    def test_red_does_three(self):
        s, ev, e = self.target("R", enemy_color="B")
        self.assertEqual(e.hp, 6)

    def test_primaries_cost_one_and_mixes_cost_two(self):
        for c in COLORS:
            s = make_state([("pawn", 4, 6, "G" if c != "G" else "B", 9)])
            before = dict(s.player.palette)
            one_beat(s, beam_up(c))
            for p in "RGB":
                expect = before[p] - (1 if p in COMPONENTS[c] else 0)
                self.assertEqual(s.player.palette[p], expect, (c, p))

    def test_weakness_doubles_and_same_colour_is_absorbed(self):
        s = make_state([("pawn", 4, 6, "C", 10)])
        one_beat(s, beam_up("R"))                                       # R is opposite of C
        self.assertEqual(s.enemies[0].hp, 4)
        s = make_state([("pawn", 4, 6, "R", 10)])
        ev = one_beat(s, beam_up("R"))
        self.assertEqual(s.enemies[0].hp, 10)
        self.assertEqual(len(events(ev, "absorb")), 1)

    def test_opposites_are_symmetric(self):
        for a, b in OPPOSITE.items():
            self.assertEqual(OPPOSITE[b], a)

    def test_green_pushes_away(self):
        s, ev, e = self.target("G", enemy_color="B")
        self.assertEqual((e.x, e.y), (4, 5))
        self.assertEqual(e.hp, 7)

    def test_green_collision_with_wall_and_enemy(self):
        s = make_state([("pawn", 4, 6, "B", 9)], walls=[(4, 5)])
        one_beat(s, beam_up("G"))
        e = s.enemies[0]
        self.assertEqual((e.x, e.y), (4, 6))
        self.assertEqual(e.hp, 9 - 2 - 2)
        s = make_state([("pawn", 4, 6, "B", 9), ("pawn", 4, 5, "B", 9, "circle")])
        one_beat(s, beam_up("G"))                  # fits only the square; it bumps the circle
        self.assertEqual(sorted(e.hp for e in s.enemies), [5, 7])

    def test_blue_stuns_and_shields_player(self):
        s, ev, e = self.target("B", enemy_color="R")
        self.assertGreaterEqual(e.stun, 1)
        self.assertEqual(s.player.shield, 1)
        s2 = make_state([("pawn", 4, 1, "R")])
        one_beat(s2, cast("halo", "triangle", "B"))                     # lands on nothing
        self.assertEqual(s2.player.shield, 1)                           # blue always shields

    def test_blue_shield_is_capped(self):
        s = make_state([("pawn", 4, 1, "R")])
        for beat in range(6):
            s.player.palette["B"] = 5
            s.player.used = frozenset()
            one_beat(s, cast("halo", "triangle", "B"), beat % BEATS)
        self.assertEqual(s.player.shield, 4)

    def test_yellow_burns_and_pushes_then_burn_ticks_at_turn_end(self):
        s = make_state([("pawn", 4, 6, "R", 8)])
        one_beat(s, beam_up("Y"))
        rules.end_turn(s)
        e = s.enemies[0]
        self.assertEqual(e.burn, 2)                                      # 3 minus one tick
        self.assertEqual(e.hp, 8 - 1 - 1)                                # 1 hit + 1 burn tick
        self.assertEqual((e.x, e.y), (4, 5))

    def test_cyan_swaps_with_first_hit_and_stuns(self):
        s = make_state([("pawn", 4, 6, "G", 8)])
        ev = one_beat(s, beam_up("C"))
        e = s.enemies[0]
        self.assertEqual((s.player.x, s.player.y), (4, 6))
        self.assertEqual((e.x, e.y), (4, 8))
        self.assertEqual(e.hp, 6)
        self.assertEqual(len(events(ev, "swap")), 1)

    def test_cyan_without_hit_does_nothing_but_says_so(self):
        s = make_state([("pawn", 3, 1, "R", 8)])
        ev = one_beat(s, beam_up("C"))
        self.assertEqual((s.player.x, s.player.y), (4, 8))
        self.assertEqual(len(events(ev, "miss")), 1)

    def test_magenta_splashes_neighbours_of_the_same_shape(self):
        s = make_state([("pawn", 4, 6, "R", 10), ("pawn", 5, 6, "R", 10),
                        ("pawn", 3, 6, "R", 10, "circle")])
        one_beat(s, beam_up("M"))
        by_pos = {(e.x, e.y): e.hp for e in s.enemies}
        self.assertEqual(by_pos[(4, 6)], 6)
        self.assertEqual(by_pos[(5, 6)], 9)                 # a square: splashed
        self.assertEqual(by_pos[(3, 6)], 10)                # a circle: the splash doesn't fit

    def test_dead_enemies_are_removed_and_victory_ends_the_fight(self):
        s = make_state([("pawn", 4, 6, "B", 2)])
        one_beat(s, beam_up("R"))
        self.assertEqual(s.enemies, [])
        self.assertEqual(s.outcome, "victory")

    def test_unaffordable_cast_fizzles_visibly(self):
        s = make_state([("pawn", 4, 6, "B", 6)], palette={"R": 0})
        ev = one_beat(s, beam_up("R"))
        self.assertEqual(len(events(ev, "fizzle")), 1)
        self.assertEqual(s.enemies[0].hp, 6)


class Relics(unittest.TestCase):
    def test_red_bonus_collision_bonus_regen_burn(self):
        s = make_state([("pawn", 4, 6, "B", 10)], mods={"red_bonus": 1})
        one_beat(s, beam_up("R"))
        self.assertEqual(s.enemies[0].hp, 6)
        s = make_state([("pawn", 4, 6, "B", 10)], walls=[(4, 5)], mods={"collision_bonus": 2})
        one_beat(s, beam_up("G"))
        self.assertEqual(s.enemies[0].hp, 10 - 2 - 4)
        s = make_state([("pawn", 4, 1, "B", 10)], palette={"R": 0}, mods={"regen": 2})
        rules.end_turn(s)
        self.assertEqual(s.player.palette["R"], 2)
        s = make_state([("pawn", 4, 6, "R", 20)], mods={"burn_bonus": 2})
        one_beat(s, beam_up("Y"))
        self.assertEqual(s.enemies[0].burn, 5)

    def test_blue_shield_relic(self):
        s = make_state([("pawn", 4, 1, "R")], mods={"blue_shield": 2})
        one_beat(s, cast("halo", "triangle", "B"))
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
        s = make_state([("pawn", 4, 6, "B", 1)])
        res = rules.resolve_turn(s, [beam_up("R"), move(1, 0), move(1, 0)])
        self.assertEqual(res.outcome, "victory")
        self.assertEqual(len(res.snapshots), 1)
        self.assertEqual(s.player.x, 4)

    def test_defeat(self):
        s = make_state([("pawn", 4, 7, "R")], hp=1)
        res = rules.resolve_turn(s, [wait(), wait(), wait(), wait()])
        self.assertEqual(res.outcome, "defeat")
        self.assertEqual(s.outcome, "defeat")

    def test_preview_does_not_mutate(self):
        s = make_state([("pawn", 4, 6, "B", 6)])
        before = rules.snapshot(s)
        rules.preview_full(s, [beam_up("R"), move(1, 0)])
        rules.simulate_prefix(s, [beam_up("R")])
        self.assertEqual(rules.snapshot(s), before)

    def test_preview_matches_real_resolution(self):
        plan = [beam_up("R"), move(1, 0), cast("halo", "square", "G"), wait()]
        a = make_state([("pawn", 4, 6, "B", 8), ("lancer", 1, 2, "G")])
        b = make_state([("pawn", 4, 6, "B", 8), ("lancer", 1, 2, "G")])
        pre, _ = rules.preview_full(a, plan)
        rules.resolve_turn(b, plan, advance=False)
        self.assertEqual(rules.snapshot(pre), rules.snapshot(b))

    def test_prefix_state_matches_full_run_up_to_that_beat(self):
        plan = [move(1, 0), beam_up("R")]
        a = make_state([("pawn", 4, 3, "B", 8)])
        pre, _ = rules.simulate_prefix(a, plan[:1])
        b = make_state([("pawn", 4, 3, "B", 8)])
        rules.resolve_beat(b, plan[0], 0, [])
        self.assertEqual(rules.snapshot(pre), rules.snapshot(b))

    def test_determinism(self):
        plan = [move(0, -1), cast("slant", "circle", "M", -1, -1), beam_up("R"), wait()]
        snaps = []
        for _ in range(3):
            s = make_state([("pawn", 4, 4, "G", 9), ("bloom", 2, 2, "R"), ("warden", 6, 3, "B"),
                            ("skew", 1, 5, "Y"), ("hopper", 7, 1, "C")])
            rules.resolve_turn(s, plan)
            snaps.append(rules.snapshot(s))
        self.assertEqual(snaps[0], snaps[1])
        self.assertEqual(snaps[1], snaps[2])

    def test_every_event_has_a_beat(self):
        s = make_state([("pawn", 4, 6, "R", 9), ("lancer", 1, 8, "B")])
        res = rules.resolve_turn(s, [beam_up("G"), move(1, 0), wait(), wait()])
        for e in res.events:
            self.assertIn("beat", e)


if __name__ == "__main__":
    unittest.main()


class Rolling(unittest.TestCase):
    """A circle's moves roll until something stops them."""

    def circle(self, enemies=(), walls=(), at=(4, 8)):
        s = make_state(enemies, walls=walls, player_at=at)
        s.player.rolls = True
        return s

    def test_rolls_to_the_wall(self):
        s = self.circle(walls=[(4, 3)])
        one_beat(s, move(0, -1))
        self.assertEqual((s.player.x, s.player.y), (4, 4))
        s = self.circle()
        one_beat(s, move(1, 0))
        self.assertEqual((s.player.x, s.player.y), (8, 8))

    def test_rolling_into_a_shape_bumps_and_pushes_it(self):
        s = self.circle([("pawn", 4, 3, "B", 9)])
        ev = one_beat(s, move(0, -1))
        e = s.enemies[0]
        self.assertEqual((s.player.x, s.player.y), (4, 4))        # stopped just short
        self.assertEqual((e.x, e.y, e.hp), (4, 2, 9 - rules.ROLL_BUMP))
        self.assertEqual(len(events(ev, "bump")), 1)

    def test_a_shape_right_next_to_you_can_be_bumped_without_moving(self):
        s = self.circle([("pawn", 4, 7, "B", 9)])
        self.assertTrue(rules.validate_action(s, move(0, -1))[0])
        one_beat(s, move(0, -1))
        self.assertEqual((s.player.x, s.player.y), (4, 8))
        self.assertEqual(s.enemies[0].hp, 9 - rules.ROLL_BUMP)

    def test_bumping_into_a_wall_behind_hurts_more(self):
        s = self.circle([("pawn", 4, 3, "B", 9)], walls=[(4, 2)])
        one_beat(s, move(0, -1))
        self.assertEqual(s.enemies[0].hp, 9 - rules.ROLL_BUMP - 2)

    def test_triangles_still_step_one_tile(self):
        s = make_state([("pawn", 4, 3, "B", 9)])
        one_beat(s, move(0, -1))
        self.assertEqual((s.player.x, s.player.y), (4, 7))
        self.assertFalse(rules.validate_action(make_state([("pawn", 4, 7, "B")]), move(0, -1))[0])


class Knotholes(unittest.TestCase):
    """Holes in the floor, in pairs (the Hollow Tree): a rolling circle drops
    into one and rolls out of its twin, still going the same way."""

    def circle(self, enemies=(), walls=(), at=(4, 8), holes=(((4, 5), (1, 2)),)):
        from prism.state import Board
        s = make_state(enemies, walls=walls, player_at=at)
        s.board = Board(walls=walls, portals=holes)
        s.player.rolls = True
        return s

    def test_rolling_into_a_hole_comes_out_of_its_twin_still_rolling(self):
        s = self.circle()
        ev = one_beat(s, move(0, -1))
        self.assertEqual((s.player.x, s.player.y), (1, 0))             # out at (1, 2), on up to the edge
        mv = [e for e in events(ev, "move") if e["who"] == "player"][0]
        self.assertEqual(mv["via"], [((4, 5), (1, 2))])
        self.assertEqual(len(events(ev, "portal")), 1)

    def test_it_works_both_ways(self):
        s = self.circle(at=(1, 0))
        one_beat(s, move(0, 1))
        self.assertEqual((s.player.x, s.player.y), (4, 8))             # in at (1, 2), out at (4, 5)

    def test_you_can_bump_a_shape_on_the_far_side(self):
        s = self.circle([("pawn", 1, 0, "B", 9)])
        one_beat(s, move(0, -1))
        self.assertEqual((s.player.x, s.player.y), (1, 1))
        self.assertEqual(s.enemies[0].hp, 9 - rules.ROLL_BUMP - 2)        # bumped into the wall behind

    def test_a_plugged_twin_means_you_roll_straight_over(self):
        s = self.circle([("pawn", 1, 2, "B", 9)])
        one_beat(s, move(0, -1))
        self.assertEqual(s.player.x, 4)                               # never went through

    def test_the_set_walk_over_holes_and_light_passes_over_them(self):
        s = self.circle([("pawn", 4, 3, "R", 9)])
        self.assertTrue(rules.tile_free(s, 4, 5))                      # a hole is still an open tile
        tiles = rules.pattern_tiles(s, "beam", 0, -1)
        self.assertIn((4, 5), tiles)

    def test_holes_never_loop_forever(self):
        # both holes in one row: rolling right drops in at (2, 4), out at (6, 4)... and on
        s = self.circle(at=(0, 4), holes=(((6, 4), (2, 4)),))
        tiles, bumped, jumps = rules.roll_route(s, 1, 0)
        self.assertIsNone(bumped)
        self.assertEqual(tiles[-1], (8, 4))
        s = self.circle(at=(8, 4), holes=(((2, 4), (6, 4)),))
        tiles, _b, jumps = rules.roll_route(s, -1, 0)                 # out at (2, 4)... in again? no
        self.assertEqual(tiles[-1][1], 4)
        self.assertLessEqual(len(jumps), 2)

    def test_tower_rooms_with_holes_are_still_winnable(self):
        from prism.dungeon import build_combat
        from prism.run import Run
        import random
        run = Run(5, tower="hollow")
        self.assertEqual(run.portal_pairs(), 2)
        st = build_combat(random.Random(3), 3, "fight", run.player, tier=run.tier(), portals=2)
        self.assertEqual(len(st.board.pairs), 2)
        holes = {t for pair in st.board.pairs for t in pair}
        self.assertFalse(holes & set(st.board.walls))
        self.assertFalse(holes & {(e.x, e.y) for e in st.enemies})
        self.assertIsNotNone(st.par)


class Twists(unittest.TestCase):
    """The other special floor tiles (consts.TWISTS). Rolls notice caps,
    snow, pools and facets; facets bend Beams too; currents and gusts carry
    anyone who ends a beat on them."""

    def circle(self, tiles, enemies=(), at=(0, 4), walls=()):
        from prism.state import Board
        s = make_state(enemies, walls=walls, player_at=at)
        s.board = Board(walls=walls, tiles=tiles)
        s.player.rolls = True
        return s

    def test_a_cap_flings_you_over_the_next_tile(self):
        s = self.circle({(3, 4): "spring"}, enemies=[("pawn", 4, 4, "B", 9)], at=(0, 4))
        ev = one_beat(s, move(1, 0))
        self.assertEqual((s.player.x, s.player.y), (8, 4))       # over the shape, and on
        mv = [e for e in events(ev, "move") if e["who"] == "player"][0]
        self.assertEqual(mv["hops"], [((3, 4), (5, 4))])
        self.assertEqual(s.enemies[0].hp, 9)                      # never touched it

    def test_a_cap_over_a_wall_too_but_not_onto_one(self):
        s = self.circle({(3, 4): "spring"}, walls=[(4, 4)])
        one_beat(s, move(1, 0))
        self.assertEqual(s.player.x, 8)                           # over the wall
        s = self.circle({(3, 4): "spring"}, walls=[(5, 4)])
        one_beat(s, move(1, 0))
        self.assertEqual(s.player.x, 3)                           # nowhere to land: stop on the cap

    def test_snow_packs_onto_your_bump(self):
        tiles = {(2, 4): "snow", (3, 4): "snow", (4, 4): "snow"}
        s = self.circle(tiles, enemies=[("pawn", 7, 4, "B", 20)])
        ev = one_beat(s, move(1, 0))
        self.assertEqual(s.enemies[0].hp, 20 - (rules.ROLL_BUMP + 3 * rules.SNOW_BUMP))
        self.assertEqual(len(events(ev, "snow")), 3)

    def test_a_pool_dyes_your_bump(self):
        s = self.circle({(2, 4): "pool:B"}, enemies=[("pawn", 6, 4, "Y", 20)], at=(0, 4))
        one_beat(s, move(1, 0))
        e = s.enemies[0]
        self.assertEqual(e.hp, 20 - (rules.ROLL_BUMP + rules.BASE_DAMAGE["B"]) * 2)   # blue vs yellow: doubled
        self.assertGreater(e.stun, 0)                             # and a blue bump stuns
        s = self.circle({(2, 4): "pool:R"}, enemies=[("pawn", 6, 4, "R", 20)])
        one_beat(s, move(1, 0))
        self.assertEqual(s.enemies[0].hp, 20)                     # the same colour is absorbed

    def test_a_green_bump_shoves_twice(self):
        s = self.circle({(2, 4): "pool:G"}, enemies=[("pawn", 4, 4, "R", 20)])
        one_beat(s, move(1, 0))
        self.assertEqual(s.enemies[0].x, 6)

    def test_bends_turn_you_a_quarter_turn(self):
        s = self.circle({(4, 4): "bend/"})                       # rolling right, "/" sends you up
        one_beat(s, move(1, 0))
        self.assertEqual((s.player.x, s.player.y), (4, 0))
        s = self.circle({(4, 4): "bend\\"})                      # "\\" sends you down
        one_beat(s, move(1, 0))
        self.assertEqual((s.player.x, s.player.y), (4, 8))

    def test_bends_turn_beams_too(self):
        from prism.state import Board
        s = self.circle({(4, 6): "bend/"}, at=(4, 8))
        s.board = Board(tiles={(4, 6): "bend/"})
        tiles = rules.pattern_tiles(s, "beam", 0, -1)             # up, then the facet turns it right
        self.assertEqual(tiles[:3], [(4, 7), (4, 6), (5, 6)])

    def test_currents_carry_you_and_them(self):
        tiles = {(4, 8): "current:1,0", (2, 2): "current:0,1"}
        s = self.circle(tiles, enemies=[("pawn", 2, 2, "B", 9)], at=(4, 8))
        s.enemies[0].orders = [("wait",)] * 4
        ev = []
        rules.resolve_beat(s, wait(), 0, ev)
        self.assertEqual((s.player.x, s.player.y), (5, 8))
        self.assertEqual((s.enemies[0].x, s.enemies[0].y), (2, 3))
        self.assertEqual(len(events(ev, "carried")), 2)

    def test_gusts_blow_two_tiles_as_far_as_clear(self):
        s = self.circle({(3, 8): "gust:1,0"}, enemies=[("pawn", 0, 0, "B", 9)], walls=[(5, 8)], at=(3, 8))
        s.enemies[0].orders = [("wait",)] * 4
        rules.resolve_beat(s, wait(), 0, [])
        self.assertEqual(s.player.x, 4)                           # one, then the wall

    def test_springs_and_loops_never_go_forever(self):
        s = self.circle({(1, 4): "bend/", (1, 0): "bend\\", (5, 0): "bend/", (5, 4): "bend\\"}, at=(3, 4))
        tiles, bumped, jumps = rules.roll_route(s, 1, 0)
        self.assertLess(len(tiles), 60)

    def test_the_set_and_light_ignore_the_rest(self):
        s = self.circle({(4, 4): "snow", (4, 3): "spring", (4, 5): "pool:R"}, enemies=[("pawn", 4, 2, "R", 9)],
                        at=(4, 8))
        self.assertTrue(rules.tile_free(s, 4, 4))
        self.assertIn((4, 4), rules.pattern_tiles(s, "beam", 0, -1))

    def test_every_tower_room_is_winnable(self):
        import random
        from prism.consts import TOWER_ORDER
        from prism.dungeon import build_combat
        from prism.run import Run
        for tid in TOWER_ORDER[1:]:
            run = Run(3, tower=tid)
            st = build_combat(random.Random(5), 3, "fight", run.player, tier=run.tier(),
                              portals=run.portal_pairs(), twists=run.twists())
            self.assertIsNotNone(st.par, tid)
            special = set(st.board.tiles) | {t for pair in st.board.pairs for t in pair}
            self.assertFalse(special & set(st.board.walls), tid)
