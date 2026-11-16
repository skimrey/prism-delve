"""Dungeon generation, the run (routes, rewards, shop, rest, events), meta
saving, and the 'more than one path to victory' guarantee."""

import json
import os
import random
import tempfile
import unittest

from helpers import make_state

from prism import rules
from prism.consts import GRID_H, GRID_W, PLAYER_START, RELICS
from prism.dungeon import (NODE_KINDS, REQUIRED_PATHS, build_combat, distinct_paths,
                           generate_route, make_walls)
from prism.enemies import BOSS_FOR_ACT, KINDS
from prism.run import ACTS, EVENTS, Meta, Run
from prism.solver import CONSTRAINTS, solve
from prism.state import Player


class Rooms(unittest.TestCase):
    def test_walls_never_block_the_start_or_disconnect_the_room(self):
        from prism.dungeon import _reachable
        for seed in range(60):
            rng = random.Random(seed)
            walls = make_walls(rng, rng.randrange(3, 8))
            self.assertNotIn(PLAYER_START, walls)
            open_tiles = [(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in walls]
            self.assertTrue(_reachable(walls, PLAYER_START, open_tiles), seed)

    def test_enemies_are_placed_legally(self):
        for act in (1, 2, 3):
            for kind in ("fight", "elite", "boss"):
                for seed in range(8):
                    st = build_combat(random.Random(seed), act, kind, Player(), verify=False)
                    spots = [(e.x, e.y) for e in st.enemies]
                    self.assertEqual(len(spots), len(set(spots)))
                    for e in st.enemies:
                        self.assertNotIn((e.x, e.y), st.board.walls)
                        self.assertNotEqual((e.x, e.y), PLAYER_START)
                        self.assertIn(e.kind, KINDS)
                        self.assertEqual(len(e.orders), 4)
                    if kind == "boss":
                        self.assertEqual(sum(1 for e in st.enemies if e.kind == BOSS_FOR_ACT[act]), 1)

    def test_elites_are_tougher(self):
        norm = build_combat(random.Random(5), 1, "fight", Player(), verify=False)
        elite = build_combat(random.Random(5), 1, "elite", Player(), verify=False)
        self.assertGreater(sum(e.hp for e in elite.enemies), sum(e.hp for e in norm.enemies))

    def test_fight_starts_with_fresh_palette_and_position(self):
        p = Player()
        p.palette = {"R": 0, "G": 0, "B": 0}
        p.x, p.y, p.shield = 0, 0, 3
        st = build_combat(random.Random(1), 1, "fight", p, verify=False)
        self.assertEqual((p.x, p.y), PLAYER_START)
        self.assertEqual(p.shield, 0)
        self.assertEqual(sum(p.palette.values()), 9)
        self.assertEqual(st.turn, 1)


class Routes(unittest.TestCase):
    def test_route_invariants_over_many_seeds(self):
        for seed in range(120):
            route = generate_route(random.Random(seed), 1 + seed % 3)
            layers = route.layers
            self.assertEqual(len(layers[-1]), 1)
            self.assertEqual(layers[-1][0].kind, "boss")
            reach = {0: set(range(len(layers[0])))}
            for li in range(len(layers) - 1):
                reach[li + 1] = set()
                for i in reach[li]:
                    node = layers[li][i]
                    self.assertTrue(node.nexts, (seed, li, i))
                    for j in node.nexts:
                        self.assertLess(j, len(layers[li + 1]))
                        reach[li + 1].add(j)
                self.assertEqual(reach[li + 1], set(range(len(layers[li + 1]))), (seed, li))
            for layer in layers:
                for n in layer:
                    self.assertIn(n.kind, NODE_KINDS)
            self.assertEqual(layers[-1][0].kind, "boss")
            self.assertTrue(all(n.kind != "boss" for layer in layers[:-1] for n in layer))


class RunFlow(unittest.TestCase):
    def setUp(self):
        self.run = Run(seed=3)

    def test_start_choices_are_layer_zero(self):
        self.assertEqual([i for i, _ in self.run.choices()], list(range(len(self.run.route.layers[0]))))

    def test_cannot_enter_unreachable_nodes(self):
        with self.assertRaises(ValueError):
            self.run.enter(99)
        self.run.enter(self.run.choices()[0][0])
        bad = [i for i in range(5) if i not in [c for c, _ in self.run.choices()]]
        if bad:
            with self.assertRaises(ValueError):
                self.run.enter(bad[0])

    def force(self, kind):
        self.run.route.layers[0][0].kind = kind
        self.run.layer, self.run.node = -1, None
        self.run.enter(0)

    def test_combat_node_builds_a_state_and_defeat_ends_the_run(self):
        self.force("fight")
        self.assertIsNotNone(self.run.state)
        self.assertEqual(self.run.finish_combat(False), 0)
        self.assertEqual(self.run.finished, "defeat")

    def test_victory_pays_gold_by_kind(self):
        got = {}
        for kind in ("fight", "elite", "boss"):
            r = Run(seed=3)
            r.route.layers[0][0].kind = kind
            r.enter(0)
            got[kind] = r.finish_combat(True)
        self.assertLess(got["fight"], got["elite"])
        self.assertLess(got["elite"], got["boss"])

    def test_reward_options_are_three_distinct_and_all_apply(self):
        for seed in range(20):
            r = Run(seed=seed)
            opts = r.reward_options()
            self.assertEqual(len(opts), 3)
            self.assertEqual(len({o["id"] for o in opts}), 3)
            for o in opts:
                r.player.hp = 5
                before = (r.player.max_hp, r.player.hp, dict(r.player.cap), list(r.relics),
                          dict(r.player.mods))
                r.apply_reward(o)
                after = (r.player.max_hp, r.player.hp, dict(r.player.cap), list(r.relics),
                         dict(r.player.mods))
                self.assertNotEqual(before, after, o)
        with self.assertRaises(ValueError):
            Run(seed=1).apply_reward({"id": "nonsense"})

    def test_relics_apply_their_mods_once(self):
        r = Run(seed=1)
        r.apply_reward({"id": "relic:crimson_lens"})
        r.apply_reward({"id": "relic:crimson_lens"})
        self.assertEqual(r.player.mods["red_bonus"], 1)
        self.assertEqual(r.relics, ["crimson_lens"])
        for rid in RELICS:
            r.apply_reward({"id": "relic:" + rid})
        self.assertEqual(sorted(r.relics), sorted(RELICS))

    def test_caps_and_max_hp(self):
        r = Run(seed=1)
        r.apply_reward({"id": "cap:R"})
        self.assertEqual(r.player.cap["R"], 6)
        r.player.hp = 2
        r.apply_reward({"id": "maxhp"})
        self.assertEqual((r.player.max_hp, r.player.hp), (17, 5))
        r.apply_reward({"id": "heal"})
        self.assertEqual(r.player.hp, 11)
        r.apply_reward({"id": "heal"})
        r.apply_reward({"id": "heal"})
        self.assertEqual(r.player.hp, r.player.max_hp)

    def test_shop_buy_paths(self):
        self.force("shop")
        run = self.run
        self.assertGreaterEqual(len(run.shop), 3)
        ok, msg = run.buy(0)
        self.assertFalse(ok)
        self.assertIn("gold", msg)
        self.assertFalse(run.buy(99)[0])
        self.assertFalse(run.buy(-1)[0])
        run.gold = 1000
        run.player.hp = 3
        ok, _ = run.buy(0)
        self.assertTrue(ok)
        self.assertGreater(run.player.hp, 3)
        ok, msg = run.buy(0)
        self.assertFalse(ok)
        self.assertIn("sold", msg.lower())
        gold = run.gold
        self.assertEqual(gold, 1000 - run.shop[0]["cost"])
        for i in range(1, len(run.shop)):
            self.assertTrue(run.buy(i)[0])

    def test_rest_heal_and_focus(self):
        self.force("rest")
        self.run.player.hp = 4
        msg = self.run.rest("heal")
        self.assertEqual(self.run.player.hp, 4 + (14 * 4) // 10)
        self.assertTrue(msg)
        self.run.rest("focus")
        self.assertEqual(sorted(self.run.player.cap.values()), [5, 5, 6])
        with self.assertRaises(ValueError):
            self.run.rest("dance")

    def test_every_event_choice_works_or_explains_itself(self):
        for ev in EVENTS:
            for cid, _label in ev["choices"]:
                for gold, hp in ((0, 14), (50, 14), (50, 2), (0, 1)):
                    r = Run(seed=4)
                    r.event = ev
                    r.gold, r.player.hp = gold, hp
                    try:
                        msg = r.resolve_event(cid)
                        self.assertTrue(msg)
                        self.assertGreaterEqual(r.player.hp, 1)
                    except ValueError as e:
                        self.assertTrue(str(e))

    def test_altar_gives_relic_for_hp_and_refuses_when_too_weak(self):
        r = Run(seed=2)
        r.event = [e for e in EVENTS if e["id"] == "altar"][0]
        r.resolve_event("blood")
        self.assertEqual(r.player.hp, 11)
        self.assertEqual(len(r.relics), 1)
        r.player.hp = 3
        with self.assertRaises(ValueError):
            r.resolve_event("blood")

    def test_act_progression_and_victory(self):
        r = Run(seed=9)
        for act in range(1, ACTS + 1):
            self.assertEqual(r.act, act)
            r.layer, r.node = len(r.route.layers) - 1, 0
            self.assertEqual(r.current_kind(), "boss")
            r.leave_node()
            if act < ACTS:
                self.assertEqual(r.layer, -1)
                self.assertEqual(r.visited, set())
        self.assertEqual(r.finished, "victory")


class Persistence(unittest.TestCase):
    def test_meta_round_trip_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "meta.json")
            m = Meta(path)
            m.record(2, False)
            m.record(3, True)
            m2 = Meta(path)
            self.assertEqual(m2.data, {"runs": 2, "wins": 1, "best_act": 3})
            with open(path, "w") as f:
                f.write("{not json")
            self.assertEqual(Meta(path).data["runs"], 0)

    def test_meta_without_a_path_is_in_memory(self):
        m = Meta(None)
        m.record(1, False)
        self.assertEqual(m.data["runs"], 1)


class PathsToVictory(unittest.TestCase):
    """The headline guarantee: every generated fight can be won in at least
    two genuinely different ways, and each way is replayable."""

    def replay(self, state, plan):
        s = state.clone()
        for turn_actions in plan:
            rules.resolve_turn(s, turn_actions, advance=True)
            if s.outcome != "ongoing":
                break
        return s.outcome

    def test_distinct_paths_are_found_replayed_and_respect_their_bans(self):
        cases = [(1, "fight"), (2, "fight"), (3, "fight"), (1, "elite"), (2, "elite"),
                 (3, "elite"), (1, "boss"), (2, "boss"), (3, "boss")]
        for act, kind in cases:
            for seed in range(3):
                st = build_combat(random.Random(100 * act + seed), act, kind, Player())
                self.assertGreaterEqual(len(st.paths), REQUIRED_PATHS, (act, kind, seed))
                self.assertEqual(len(set(st.paths)), len(st.paths))
                for name in st.paths:
                    res = solve(st, CONSTRAINTS[name], max_turns=5, beat_beam=14, turn_beam=6)
                    self.assertTrue(res.won, (act, kind, seed, name))
                    self.assertEqual(self.replay(st, res.plan), "victory", (act, kind, seed, name))
                    banned = CONSTRAINTS[name]
                    for turn in res.plan:
                        for a in turn:
                            if a.kind == "cast":
                                self.assertTrue(banned(a.shape, a.color), (name, a))

    def test_the_two_paths_use_different_tools(self):
        diffs = 0
        total = 0
        for seed in range(6):
            st = build_combat(random.Random(500 + seed), 1, "fight", Player())
            plans = [solve(st, CONSTRAINTS[n], max_turns=5, beat_beam=14, turn_beam=6)
                     for n in st.paths[:2]]
            used = [p.used() for p in plans]
            total += 1
            if used[0] != used[1] or [a for t in plans[0].plan for a in t] != [a for t in plans[1].plan for a in t]:
                diffs += 1
        self.assertEqual(diffs, total)

    def test_distinct_paths_reports_none_for_an_unwinnable_room(self):
        p = Player()
        p.hp = 1
        st = make_state([("pawn", 4, 7, "R", 99), ("pawn", 3, 8, "R", 99), ("pawn", 5, 8, "R", 99)],
                        hp=1)
        self.assertEqual(distinct_paths(st), [])

    def test_solver_does_not_mutate_its_input(self):
        st = build_combat(random.Random(7), 1, "fight", Player(), verify=False)
        before = rules.snapshot(st)
        solve(st, None)
        self.assertEqual(rules.snapshot(st), before)


class BotRun(unittest.TestCase):
    """A solver-driven bot plays whole runs through the engine, proving the
    flow (routes, nodes, rewards, acts) holds together end to end."""

    def play(self, seed):
        run = Run(seed=seed)
        guard = 0
        while run.finished is None and guard < 200:
            guard += 1
            idx = run.choices()[0][0]
            node = run.enter(idx)
            if node.kind in ("fight", "elite", "boss"):
                st = run.state
                turns = 0
                while st.outcome == "ongoing" and turns < 12:
                    turns += 1
                    res = solve(st, None, max_turns=4, beat_beam=10, turn_beam=5)
                    plan = res.plan[0] if res.won else []
                    rules.resolve_turn(st, plan, advance=True)
                won = st.outcome == "victory"
                run.finish_combat(won)
                if not won:
                    break
                run.apply_reward(run.reward_options()[0])
            elif node.kind == "rest":
                run.rest("heal")
            elif node.kind == "shop":
                for i in range(len(run.shop)):
                    run.buy(i)
            run.leave_node()
        return run

    def test_bot_completes_runs_without_breaking_the_flow(self):
        results = [self.play(seed) for seed in (1, 2, 3)]
        for r in results:
            self.assertIn(r.finished, ("victory", "defeat"))


if __name__ == "__main__":
    unittest.main()
