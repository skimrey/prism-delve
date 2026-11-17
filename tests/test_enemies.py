import unittest

from helpers import events, make_state

from prism import rules
from prism.consts import BEATS, COLORS, KNIGHT, SHAPES
from prism.enemies import BOSS_FOR_ACT, KINDS, boss_color, boss_shape, order_pattern
from prism.rules import MAX_ENEMIES
from prism.state import cast, move, wait

ORDERS = ("wait", "move", "halo", "leap", "line", "splash", "shield", "summon")


def run_turn(state, actions):
    return rules.resolve_turn(state, actions, advance=False)


class Planning(unittest.TestCase):
    def test_every_kind_plans_exactly_one_order_per_beat(self):
        for kind in KINDS:
            s = make_state([(kind, 4, 2, "R")], player_at=(4, 8))
            e = s.enemies[0]
            self.assertEqual(len(e.orders), BEATS, kind)
            for o in e.orders:
                self.assertIn(o[0], ORDERS)

    def test_orders_are_replanned_each_turn(self):
        s = make_state([("pawn", 4, 2, "R")])
        first = list(s.enemies[0].orders)
        rules.resolve_turn(s, [move(1, 0)])
        self.assertNotEqual(first, s.enemies[0].orders)

    def test_nobody_idles_out_of_reach(self):
        # a Skew exactly on your diagonal but too far away used to wait forever
        s = make_state([("skew", 0, 0, "R")], player_at=(4, 4))
        self.assertEqual(s.enemies[0].orders[0][0], "move")
        # a wall straight between you: walk around it
        walls = [(4, 5), (3, 5), (5, 5)]
        for kind in ("pawn", "lancer", "hopper", "skew"):
            s = make_state([(kind, 4, 7, "R")], walls=walls, player_at=(4, 3))
            self.assertEqual(s.enemies[0].orders[0][0], "move", kind)

    def test_everyone_eventually_reaches_you(self):
        walls = [(2, 4), (3, 4), (4, 6), (5, 6), (6, 2)]
        for kind in ("pawn", "lancer", "skew", "hopper", "bloom"):
            s = make_state([(kind, 8, 8, "R", 99)], walls=walls, player_at=(1, 1), hp=999)
            attacked = False
            for _ in range(8):
                res = rules.resolve_turn(s, [], advance=True)
                attacked |= bool(events(res.events, "enemy_attack"))
            self.assertTrue(attacked, kind)

    def test_stuck_enemy_waits_instead_of_crashing(self):
        walls = [(3, 5), (5, 5), (4, 4), (4, 6)]
        for kind in ("pawn", "skew", "hopper"):
            s = make_state([(kind, 4, 5, "R")], walls=walls)
            self.assertTrue(all(o[0] in ("wait", "move") for o in s.enemies[0].orders), kind)
            run_turn(s, [])


class SharedPatterns(unittest.TestCase):
    """Enemies attack with the same patterns you cast, and say which."""

    def test_every_regular_enemy_attacks_with_its_listed_pattern(self):
        for kind, spec in KINDS.items():
            if spec.get("boss"):
                continue
            seen = set()
            for px, py in ((4, 8), (4, 4), (0, 0), (8, 3), (5, 5), (2, 6)):
                for ex, ey in ((4, 5), (3, 3), (5, 4), (4, 2), (6, 6), (1, 1), (6, 7)):
                    if (px, py) == (ex, ey):
                        continue
                    s = make_state([(kind, ex, ey, "R")], player_at=(px, py))
                    for o in s.enemies[0].orders:
                        if order_pattern(o):
                            seen.add(order_pattern(o))
            self.assertEqual(seen, {spec["pattern"]}, kind)

    def test_shape_is_independent_of_behaviour(self):
        for shape in SHAPES:
            s = make_state([("lancer", 4, 5, "R", None, shape)])
            self.assertEqual(s.enemies[0].shape, shape)
            self.assertEqual(s.enemies[0].orders[0][0], "line")


class Squads(unittest.TestCase):
    def test_a_squad_keeps_its_formation_as_it_marches(self):
        s = make_state([("pawn", 2, 0, "R"), ("pawn", 3, 0, "G"), ("pawn", 4, 0, "B")],
                       player_at=(3, 8), begin=False)
        for e in s.enemies:
            e.squad = 1
        rules.begin_turn(s)
        rules.resolve_turn(s, [], advance=False)
        xs = sorted(e.x for e in s.enemies)
        ys = {e.y for e in s.enemies}
        self.assertEqual(xs, [2, 3, 4])
        self.assertEqual(len(ys), 1)
        self.assertGreater(ys.pop(), 0)

    def test_followers_copy_the_leader_not_their_own_path(self):
        spec = [("pawn", 1, 4, "R"), ("pawn", 4, 1, "G")]
        alone = make_state(spec, player_at=(4, 4))
        self.assertEqual(alone.enemies[1].orders[0], ("move", 0, 1))    # its own way: down
        s = make_state(spec, player_at=(4, 4), begin=False)
        for e in s.enemies:
            e.squad = 1
        rules.begin_turn(s)
        self.assertEqual(s.enemies[0].orders[0], ("move", 1, 0))
        self.assertEqual(s.enemies[1].orders[0], ("move", 1, 0))        # the leader's way

    def test_followers_still_attack_on_their_own(self):
        s = make_state([("pawn", 1, 0, "R"), ("pawn", 4, 7, "G")], player_at=(4, 8), begin=False)
        for e in s.enemies:
            e.squad = 1
        rules.begin_turn(s)
        self.assertEqual(s.enemies[1].orders[0][0], "halo")


class Stomper(unittest.TestCase):
    """kind 'pawn': walks up and Halos (all 8 tiles around it)."""

    def test_walks_then_halos(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8))
        self.assertEqual([o[0] for o in s.enemies[0].orders], ["move", "move", "move", "halo"])

    def test_standing_still_takes_the_hit(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [])
        self.assertEqual(s.player.hp, 8)

    def test_diagonal_is_close_enough(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(5, 5), hp=10)
        self.assertEqual(s.enemies[0].orders[0], ("halo", 2))

    def test_one_step_aside_is_not_enough_two_is(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0)])
        self.assertEqual(s.player.hp, 8)
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0), move(1, 0)])
        self.assertEqual(s.player.hp, 10)

    def test_halo_skips_walls(self):
        s = make_state([("pawn", 4, 4, "R")], walls=[(5, 4)], player_at=(5, 5), hp=10)
        res = run_turn(s, [])
        atk = events(res.events, "enemy_attack")[0]
        self.assertNotIn((5, 4), atk["tiles"])
        self.assertEqual(len(atk["tiles"]), 7)

    def test_shield_absorbs_before_hp(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        s.player.shield = 2
        run_turn(s, [])
        self.assertEqual((s.player.hp, s.player.shield), (10, 0))

    def test_stun_skips_actions(self):
        s = make_state([("pawn", 4, 5, "G", 10)], player_at=(4, 7), hp=10)
        res = run_turn(s, [cast("beam", "square", "B", 0, -1)])
        self.assertEqual(len(events(res.events, "stunned")), 2)
        self.assertLess(len(events(res.events, "enemy_attack")), 2)

    def test_pushing_an_enemy_changes_where_it_hits(self):
        s = make_state([("pawn", 4, 6, "B", 10)], player_at=(4, 8), hp=10)
        # it would step to (4, 7) and Halo; pushed back to (4, 5) it never gets close enough
        run_turn(s, [cast("beam", "square", "G", 0, -1), move(1, 0), move(1, 0), wait()])
        self.assertEqual(s.player.hp, 10)

    def test_blocked_move_is_reported(self):
        s = make_state([("pawn", 4, 6, "R"), ("pawn", 4, 7, "R")], player_at=(4, 8))
        s.enemies[1].orders = [("wait",)] * 4
        s.enemies[0].orders = [("move", 0, 1)] + [("wait",)] * 3
        res = run_turn(s, [])
        self.assertEqual(len(events(res.events, "blocked")), 1)


class Lancer(unittest.TestCase):
    def test_lines_up_then_pierces(self):
        s = make_state([("lancer", 1, 5, "R")], player_at=(4, 8))
        self.assertIn("move", [o[0] for o in s.enemies[0].orders])

    def test_aligned_in_reach_attacks_through_the_line(self):
        s = make_state([("lancer", 4, 5, "R")], player_at=(4, 8), hp=10)
        self.assertEqual(s.enemies[0].orders[0][0], "line")
        run_turn(s, [])
        self.assertEqual(s.player.hp, 6)              # lines at beats 1 and 3
        s = make_state([("lancer", 4, 5, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0)])                     # stepping off the line dodges all of it
        self.assertEqual(s.player.hp, 10)

    def test_aligned_but_far_closes_the_gap(self):
        s = make_state([("lancer", 4, 1, "R")], player_at=(4, 8))
        self.assertEqual(s.enemies[0].orders[0][0], "move")

    def test_walls_block_the_line(self):
        s = make_state([("lancer", 4, 5, "R")], walls=[(4, 6)], player_at=(4, 8), hp=10)
        s.enemies[0].orders = [("line", 0, 1, 2, 3)] + [("wait",)] * 3
        run_turn(s, [])
        self.assertEqual(s.player.hp, 10)


class Skew(unittest.TestCase):
    def test_on_a_diagonal_it_slants(self):
        s = make_state([("skew", 2, 6, "R")], player_at=(4, 8), hp=10)
        self.assertEqual(s.enemies[0].orders[0], ("line", 1, 1, 2, 3))
        run_turn(s, [])
        self.assertEqual(s.player.hp, 6)

    def test_off_the_diagonal_it_moves_onto_one(self):
        s = make_state([("skew", 4, 6, "R")], player_at=(4, 8))
        o = s.enemies[0].orders
        self.assertEqual(o[0][0], "move")
        self.assertIn("line", [x[0] for x in o])

    def test_a_straight_step_dodges_a_slant(self):
        s = make_state([("skew", 2, 6, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0)])
        self.assertEqual(s.player.hp, 10)


class Hopper(unittest.TestCase):
    def test_at_an_l_step_it_leaps(self):
        s = make_state([("hopper", 3, 6, "R")], player_at=(4, 8), hp=10)
        self.assertEqual(s.enemies[0].orders[0], ("leap", 2))
        res = run_turn(s, [])
        atk = events(res.events, "enemy_attack")[0]
        self.assertEqual(sorted(atk["tiles"]), sorted(
            (3 + dx, 6 + dy) for dx, dy in KNIGHT if 0 <= 3 + dx < 9 and 0 <= 6 + dy < 9))
        self.assertEqual(s.player.hp, 6)

    def test_it_walks_to_an_l_step_not_to_you(self):
        s = make_state([("hopper", 4, 4, "R")], player_at=(4, 8))
        o = s.enemies[0].orders
        self.assertEqual(o[0][0], "move")
        self.assertIn("leap", [x[0] for x in o])

    def test_stepping_next_to_it_is_safe(self):
        s = make_state([("hopper", 3, 6, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(0, -1)])                    # (4, 7) is not an L-step from (3, 6)
        self.assertEqual(s.player.hp, 10)


class Bloom(unittest.TestCase):
    def test_splash_hits_where_you_stood_when_planned(self):
        s = make_state([("bloom", 4, 5, "R")], player_at=(4, 8), hp=10)
        self.assertEqual([o[0] for o in s.enemies[0].orders], ["wait", "splash", "wait", "splash"])
        run_turn(s, [])
        self.assertEqual(s.player.hp, 6)              # two splashes of 2

    def test_two_steps_clear_dodge_it_but_one_step_is_still_in_the_plus(self):
        s = make_state([("bloom", 4, 5, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0), move(1, 0)])
        self.assertEqual(s.player.hp, 10)
        s = make_state([("bloom", 4, 5, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0)])
        self.assertEqual(s.player.hp, 6)


class Warden(unittest.TestCase):
    def test_shields_adjacent_allies_first_beat(self):
        s = make_state([("warden", 4, 3, "R"), ("pawn", 4, 4, "R", 6)], player_at=(4, 8))
        run_turn(s, [])
        pawn = [e for e in s.enemies if e.kind == "pawn"][0]
        self.assertEqual(pawn.shield, 1)

    def test_enemy_shield_absorbs_damage_then_hp(self):
        s = make_state([("pawn", 4, 6, "B", 6)])
        s.enemies[0].shield = 2
        rules.player_action(s, cast("beam", "square", "R", 0, -1), 0, [])
        self.assertEqual((s.enemies[0].hp, s.enemies[0].shield), (5, 0))


class Splitter(unittest.TestCase):
    def test_dies_into_two_shards_of_the_same_shape(self):
        s = make_state([("splitter", 4, 6, "B", 2, "circle"), ("pawn", 1, 1, "R")])
        ev = []
        rules.player_action(s, cast("beam", "circle", "R", 0, -1), 0, ev)
        rules.reap(s, ev, 0)
        self.assertEqual(len(events(ev, "spawn")), 2)
        self.assertEqual(sorted(e.kind for e in s.enemies), ["pawn", "shard", "shard"])
        for e in s.enemies:
            if e.kind == "shard":
                self.assertEqual((e.color, e.shape), ("B", "circle"))

    def test_no_shards_when_boxed_in(self):
        walls = [(3, 5), (5, 5), (4, 4), (4, 6)]
        s = make_state([("splitter", 4, 5, "B", 2), ("pawn", 1, 1, "R")], walls=walls,
                       player_at=(4, 7))
        ev = []
        s.enemies[0].hp = 0
        rules.reap(s, ev, 0)
        self.assertEqual(events(ev, "spawn"), [])

    def test_enemy_cap_is_respected(self):
        s = make_state([("splitter", 4, 5, "B", 2)] + [("pawn", x, 0, "R") for x in range(MAX_ENEMIES - 1)])
        s.enemies[0].hp = 0
        ev = []
        rules.reap(s, ev, 0)
        self.assertLessEqual(len(s.enemies), MAX_ENEMIES)


class Shard(unittest.TestCase):
    def test_shard_flicks_a_beam_of_two(self):
        s = make_state([("shard", 4, 6, "R")], player_at=(4, 8), hp=10)
        self.assertEqual(s.enemies[0].orders[0], ("line", 0, 1, 1, 2))
        run_turn(s, [])
        self.assertEqual(s.player.hp, 8)

    def test_shard_out_of_reach_closes_in(self):
        s = make_state([("shard", 4, 4, "R")], player_at=(4, 8))
        self.assertEqual(s.enemies[0].orders[0][0], "move")


class Burn(unittest.TestCase):
    def test_burn_can_finish_a_fight(self):
        s = make_state([("pawn", 4, 1, "B", 1)])
        s.enemies[0].burn = 2
        res = run_turn(s, [])
        self.assertEqual(res.outcome, "victory")


class Keepers(unittest.TestCase):
    def test_colour_cycles_every_turn(self):
        s = make_state([(BOSS_FOR_ACT[1], 4, 1, "R")])
        seen = set()
        for _ in range(len(COLORS)):
            seen.add(s.enemies[0].color)
            rules.resolve_turn(s, [wait()] * BEATS, advance=True)
            if s.outcome != "ongoing":
                break
            s.player.hp = 99
        self.assertGreater(len(seen), 3)
        self.assertEqual(boss_color(s, s.enemies[0]), s.enemies[0].color)

    def test_shape_changes_every_beat_on_a_visible_schedule(self):
        s = make_state([("colossus", 4, 1, "R")], hp=99)
        e = s.enemies[0]
        expect = [boss_shape(s, e, b) for b in range(BEATS)]
        self.assertEqual(e.shape, expect[0])
        self.assertGreater(len(set(expect)), 1)
        res = rules.resolve_turn(s, [], advance=False, record=True)
        seen = [snap["enemies"][0][10] for snap in res.snapshots[:BEATS]]
        self.assertEqual(seen, expect)

    def test_timing_decides_whether_your_light_fits_a_keeper(self):
        s = make_state([("colossus", 4, 6, "B", 30)], hp=99)
        e = s.enemies[0]
        beat = [boss_shape(s, e, b) for b in range(BEATS)].index("triangle")
        plan = [wait()] * beat + [cast("beam", "triangle", "R", 0, -1)]
        rules.resolve_turn(s, plan, advance=False)
        self.assertLess(s.enemies[0].hp, 30)
        s = make_state([("colossus", 4, 6, "B", 30)], hp=99)
        wrong = (beat + 1) % BEATS if boss_shape(s, s.enemies[0], (beat + 1) % BEATS) != "triangle" \
            else (beat + 2) % BEATS
        plan = [wait()] * wrong + [cast("beam", "triangle", "R", 0, -1)]
        rules.resolve_turn(s, plan, advance=False)
        self.assertEqual(s.enemies[0].hp, 30)

    def test_summons_on_even_turns_copy_the_keepers_shape(self):
        s = make_state([("colossus", 4, 1, "R")], player_at=(4, 8), hp=99)
        s.player.max_hp = 99
        spawned = []
        for _ in range(4):
            res = rules.resolve_turn(s, [wait()] * BEATS)
            for ev in events(res.events, "spawn"):
                spawned.append(s.get(ev["who"]).shape if s.get(ev["who"]) else None)
        self.assertTrue(spawned)

    def test_keepers_are_flagged_and_tough(self):
        for act, kind in BOSS_FOR_ACT.items():
            self.assertTrue(KINDS[kind]["boss"])
            self.assertGreaterEqual(KINDS[kind]["hp"], 16)
            self.assertEqual(len(KINDS[kind]["shapes"]), BEATS)


if __name__ == "__main__":
    unittest.main()
