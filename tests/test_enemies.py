import unittest

from helpers import events, make_state

from prism import rules
from prism.consts import BEATS, COLORS
from prism.enemies import BOSS_FOR_ACT, KINDS, boss_color, plan_orders
from prism.rules import MAX_ENEMIES
from prism.state import cast, move, wait


def run_turn(state, actions):
    return rules.resolve_turn(state, actions, advance=False)


class Planning(unittest.TestCase):
    def test_every_kind_plans_exactly_one_order_per_beat(self):
        for kind in KINDS:
            s = make_state([(kind, 4, 2, "R")], player_at=(4, 8))
            e = s.enemies[0]
            self.assertEqual(len(e.orders), BEATS, kind)
            for o in e.orders:
                self.assertIn(o[0], ("wait", "move", "hit", "line", "splash", "shield", "summon"))

    def test_orders_are_replanned_each_turn(self):
        s = make_state([("pawn", 4, 2, "R")])
        first = list(s.enemies[0].orders)
        rules.resolve_turn(s, [move(1, 0)])
        self.assertNotEqual(first, s.enemies[0].orders)

    def test_stuck_enemy_waits_instead_of_crashing(self):
        walls = [(3, 5), (5, 5), (4, 4), (4, 6)]
        s = make_state([("pawn", 4, 5, "R")], walls=walls)
        self.assertTrue(all(o[0] in ("wait", "move") for o in s.enemies[0].orders))
        run_turn(s, [])


class Pawn(unittest.TestCase):
    def test_walks_then_hits(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8))
        self.assertEqual([o[0] for o in s.enemies[0].orders], ["move", "move", "move", "hit"])

    def test_standing_still_takes_the_hit(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [])
        self.assertEqual(s.player.hp, 8)

    def test_moving_away_dodges_the_telegraphed_hit(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0)])
        self.assertEqual(s.player.hp, 10)

    def test_shield_absorbs_before_hp(self):
        s = make_state([("pawn", 4, 4, "R")], player_at=(4, 8), hp=10)
        s.player.shield = 2
        run_turn(s, [])
        self.assertEqual((s.player.hp, s.player.shield), (10, 0))

    def test_stun_skips_actions(self):
        s = make_state([("pawn", 4, 4, "G", 10)], player_at=(4, 7), hp=10)
        res = run_turn(s, [cast("circle", "B", 4, 5)])
        self.assertEqual(s.player.hp, 10)
        self.assertEqual(len(events(res.events, "stunned")), 2)

    def test_pushing_an_enemy_changes_where_it_hits(self):
        s = make_state([("pawn", 4, 6, "B", 10)], player_at=(4, 8), hp=10)
        # pawn would step to (4,7) then hit (4,8); pushing it back first spoils that
        run_turn(s, [cast("circle", "G", 4, 6), wait(), wait(), wait()])
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
        kinds = [o[0] for o in s.enemies[0].orders]
        self.assertIn("move", kinds)

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


class Bloom(unittest.TestCase):
    def test_splash_hits_where_you_stood_when_planned(self):
        s = make_state([("bloom", 4, 5, "R")], player_at=(4, 8), hp=10)
        self.assertEqual([o[0] for o in s.enemies[0].orders], ["wait", "splash", "wait", "splash"])
        run_turn(s, [])
        self.assertEqual(s.player.hp, 6)              # two splashes of 2

    def test_two_steps_clear_dodge_it_but_one_step_is_still_in_the_plus(self):
        s = make_state([("bloom", 4, 5, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0), move(1, 0)])        # two tiles from the centre by the splash
        self.assertEqual(s.player.hp, 10)
        s = make_state([("bloom", 4, 5, "R")], player_at=(4, 8), hp=10)
        run_turn(s, [move(1, 0)])                     # still adjacent to the centre
        self.assertEqual(s.player.hp, 6)


class Warden(unittest.TestCase):
    def test_shields_adjacent_allies_first_beat(self):
        s = make_state([("warden", 4, 3, "R"), ("pawn", 4, 4, "R", 6)], player_at=(4, 8))
        run_turn(s, [])
        pawn = [e for e in s.enemies if e.kind == "pawn"][0]
        self.assertEqual(pawn.shield, 2)

    def test_enemy_shield_absorbs_damage_then_hp(self):
        s = make_state([("pawn", 4, 5, "B", 6)])
        s.enemies[0].shield = 2
        rules.player_action(s, cast("circle", "R", 4, 5), 0, [])
        self.assertEqual((s.enemies[0].hp, s.enemies[0].shield), (6, 0))
        rules.player_action(s, cast("square", "R", 4, 5), 1, [])
        self.assertEqual(s.enemies[0].hp, 4 if s.player.chain == 1 else 3)


class Splitter(unittest.TestCase):
    def test_dies_into_two_shards(self):
        s = make_state([("splitter", 4, 5, "R", 2), ("pawn", 1, 1, "R")])
        res = run_turn(s, [cast("circle", "B", 4, 5)] if False else [cast("circle", "G", 4, 5)])
        # green does 1; use red on a differently coloured splitter for a clean kill
        s = make_state([("splitter", 4, 5, "B", 2), ("pawn", 1, 1, "R")])
        ev = []
        rules.player_action(s, cast("circle", "R", 4, 5), 0, ev)
        rules.reap(s, ev, 0)
        self.assertEqual(len(events(ev, "spawn")), 2)
        self.assertEqual(sorted(e.kind for e in s.enemies), ["pawn", "shard", "shard"])
        for e in s.enemies:
            if e.kind == "shard":
                self.assertEqual(e.color, "B")

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


class Burn(unittest.TestCase):
    def test_burn_can_finish_a_fight(self):
        s = make_state([("pawn", 4, 1, "B", 1)])
        s.enemies[0].burn = 2
        res = run_turn(s, [])
        self.assertEqual(res.outcome, "victory")


class Bosses(unittest.TestCase):
    def test_boss_colour_cycles_every_turn(self):
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

    def test_boss_summons_on_even_turns(self):
        s = make_state([("colossus", 4, 1, "R")], player_at=(4, 8), hp=99)
        s.player.max_hp = 99
        counts = []
        for _ in range(4):
            rules.resolve_turn(s, [wait()] * BEATS)
            counts.append(len(s.enemies))
        self.assertGreater(max(counts), 1)

    def test_bosses_have_big_health_and_are_flagged(self):
        for act, kind in BOSS_FOR_ACT.items():
            self.assertTrue(KINDS[kind]["boss"])
            self.assertGreaterEqual(KINDS[kind]["hp"], 18)


if __name__ == "__main__":
    unittest.main()
