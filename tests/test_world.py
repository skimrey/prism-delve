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
from prism.dungeon import (NODE_KINDS, REQUIRED_PATHS, _solve_kw, build_combat, distinct_paths,
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
    def test_every_path_has_fights_and_no_long_calm_stretch(self):
        from prism.dungeon import COMBAT, MIN_FIGHTS, route_paths
        for seed in range(150):
            route = generate_route(random.Random(seed), 1 + seed % 3)
            self.assertTrue(all(n.kind == "fight" for n in route.layers[0]))
            paths = route_paths(route)
            for kinds in paths:
                self.assertGreaterEqual(sum(k in COMBAT for k in kinds), MIN_FIGHTS, (seed, kinds))
                for a, b in zip(kinds, kinds[1:]):
                    self.assertFalse(a not in COMBAT and b not in COMBAT, (seed, kinds))

    def test_paths_differ_in_difficulty_so_there_is_an_easier_way(self):
        from prism.dungeon import route_paths
        spread = 0
        for seed in range(60):
            paths = route_paths(generate_route(random.Random(seed), 2))
            d = [sum({"fight": 1, "elite": 2}.get(k, 0) for k in p) for p in paths]
            spread += max(d) > min(d)
        self.assertGreater(spread, 40)

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
                          dict(r.player.mods), list(r.player.patterns))
                r.apply_reward(o)
                after = (r.player.max_hp, r.player.hp, dict(r.player.cap), list(r.relics),
                         dict(r.player.mods), list(r.player.patterns))
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
        self.assertIn("glint", msg)
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
            for variant in ("gift", "deal"):
                for cid, _label, _effects in ev[variant]:
                    for gold, hp in ((0, 14), (50, 14), (50, 2), (0, 1)):
                        r = Run(seed=4)
                        r.event = r.make_event(ev, variant)
                        r.gold, r.player.hp = gold, hp
                        before = (r.gold, r.player.hp, dict(r.player.cap), list(r.relics))
                        try:
                            msg = r.resolve_event(cid)
                            self.assertTrue(msg)
                            self.assertGreaterEqual(r.player.hp, 1)
                        except ValueError as e:
                            self.assertTrue(str(e))
                            after = (r.gold, r.player.hp, dict(r.player.cap), list(r.relics))
                            self.assertEqual(before, after)        # a refusal changes nothing

    def test_the_polisher_deal_costs_colour_or_glint_never_hp(self):
        polisher = [e for e in EVENTS if e["id"] == "polisher"][0]
        r = Run(seed=2)
        r.player.cap["G"] = 6
        r.event = r.make_event(polisher, "deal")
        r.resolve_event("polish")
        self.assertEqual((r.player.cap["G"], r.player.hp, len(r.relics)), (5, 14, 1))
        r.event = r.make_event(polisher, "deal")
        r.gold = 10
        with self.assertRaises(ValueError):
            r.resolve_event("polish2")              # a fancy polish costs 30 glint

    def test_a_colour_trade_is_always_between_two_colours(self):
        well = [e for e in EVENTS if e["id"] == "well"][0]
        ev = Run(seed=1).make_event(well, "deal")        # all caps equal at the start
        drink = [c for c in ev["choices"] if c[0] == "drink"][0][2]
        self.assertNotEqual(drink[0][1], drink[1][1])

    def test_nothing_in_an_oddity_hurts(self):
        # the tone is a toy box: costs are glint or a little colour, never HP
        for ev in EVENTS:
            for variant in ("gift", "deal"):
                for cid, _label, effects in ev[variant]:
                    flat = []
                    for eff in effects:
                        flat += [eff] + (list(eff[2]) + list(eff[3]) if eff[0] == "gamble" else [])
                    self.assertEqual([e for e in flat if e[0] == "hp"], [], (ev["id"], cid))

    def test_gifts_have_no_way_out_and_deals_do(self):
        for ev in EVENTS:
            gift_ids = [c[0] for c in ev["gift"]]
            self.assertNotIn("leave", gift_ids, ev["id"])
            for cid, _label, effects in ev["gift"]:
                for eff in effects:       # a gift only gives
                    self.assertFalse(eff[0] == "hp" or (eff[0] in ("glint", "maxhp") and eff[-1] < 0)
                                     or (eff[0] == "cap" and eff[2] < 0), (ev["id"], cid))
            self.assertIn("leave", [c[0] for c in ev["deal"]], ev["id"])
            for cid, _label, effects in ev["deal"]:
                if cid == "leave":
                    continue
                costs = [e for e in effects if e[0] == "gamble" or e[0] == "hp" or
                         (e[0] in ("glint",) and e[1] < 0) or (e[0] == "cap" and e[2] < 0)]
                self.assertTrue(costs, (ev["id"], cid))          # every deal has a drawback

    def test_low_floors_give_more_gifts_high_floors_more_deals(self):
        counts = {}
        for act in (1, 3):
            gifts = 0
            for seed in range(200):
                r = Run(seed=seed)
                r.act = act
                gifts += r.make_event()["variant"] == "gift"
            counts[act] = gifts
        self.assertGreater(counts[1], 120)
        self.assertLess(counts[3], 60)

    def test_every_effect_reads_as_words(self):
        from prism.run import effect_text
        r = Run(seed=1)
        for ev in EVENTS:
            for variant in ("gift", "deal"):
                for _cid, _label, effects in r.make_event(ev, variant)["choices"]:
                    for eff in effects:
                        text = effect_text(eff)
                        self.assertTrue(text and "None" not in text, eff)

    def test_each_keeper_grows_a_side_with_its_perk(self):
        from prism.consts import FORMS
        r = Run(seed=9)
        self.assertEqual(r.form()["shape"], "triangle")
        hp, caps = r.player.max_hp, dict(r.player.cap)
        r.layer, r.node = len(r.route.layers) - 1, 0
        r.leave_node()
        self.assertEqual(r.form()["shape"], "square")
        self.assertEqual(r.player.max_hp, hp + FORMS[2]["max_hp"])
        r.layer, r.node = len(r.route.layers) - 1, 0
        r.leave_node()
        self.assertEqual(r.form()["shape"], "pentagon")
        self.assertEqual(r.player.cap, {c: v + FORMS[3]["cap"] for c, v in caps.items()})
        r.layer, r.node = len(r.route.layers) - 1, 0
        r.leave_node()
        self.assertEqual(r.finished, "victory")
        self.assertEqual(r.form()["shape"], 10)            # round enough (not round: that comes later)

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


class SpeedAndPatterns(unittest.TestCase):
    """Fewer turns pay more; the patterns the Set used are yours to learn."""

    def test_grades_against_par(self):
        from prism.run import grade
        self.assertEqual(grade(2, 3)["name"], "Clean")
        self.assertEqual(grade(4, 3)["name"], "Clean")          # par + 1 is still clean
        self.assertEqual(grade(5, 3)["name"], "Tidy")
        self.assertEqual(grade(7, 3)["name"], "Messy")
        self.assertIsNone(grade(3, None))

    def test_a_clean_win_pays_more_and_offers_four_rewards(self):
        got = {}
        for turns in (3, 4, 9):
            r = Run(seed=3)
            r.route.layers[0][0].kind = "fight"
            r.enter(0)
            got[turns] = (r.finish_combat(True, turns=turns, par=2), len(r.reward_options()))
        self.assertGreater(got[3][0], got[4][0])
        self.assertGreater(got[4][0], got[9][0])
        self.assertEqual(got[3][1], 4)
        self.assertEqual(got[9][1], 3)

    def test_built_fights_have_a_par(self):
        st = build_combat(random.Random(4), 1, "fight", Player())
        self.assertIsNotNone(st.par)
        self.assertGreaterEqual(st.par, 1)

    def test_a_hard_set_always_leaves_a_facet(self):
        for seed in range(10):
            r = Run(seed=seed)
            r.route.layers[0][0].kind = "elite"
            r.enter(0)
            r.finish_combat(True)
            self.assertTrue(any(o["id"].startswith("relic:") for o in r.reward_options()))

    def test_beating_a_pattern_you_lack_offers_to_learn_it(self):
        r = Run(seed=5)
        r.route.layers[0][0].kind = "fight"
        r.enter(0)
        r.state.seen_patterns = {"leap"}
        r.finish_combat(True)
        opts = r.reward_options()
        self.assertIn("pattern:leap", [o["id"] for o in opts])
        r.apply_reward({"id": "pattern:leap"})
        self.assertIn("leap", r.player.patterns)
        r.apply_reward({"id": "pattern:leap"})
        self.assertEqual(r.player.patterns.count("leap"), 1)
        with self.assertRaises(ValueError):
            r.apply_reward({"id": "pattern:nonsense"})

    def test_fights_record_the_patterns_their_set_uses(self):
        st = build_combat(random.Random(2), 2, "boss", Player(), verify=False)
        self.assertIn(KINDS[BOSS_FOR_ACT[2]]["pattern"], st.seen_patterns)
        self.assertIn(KINDS[KINDS[BOSS_FOR_ACT[2]]["summon"]]["pattern"], st.seen_patterns)

    def test_fights_arrive_as_a_set_in_formation(self):
        for act in (1, 2, 3):
            for seed in range(10):
                st = build_combat(random.Random(seed), act, "fight", Player(), verify=False)
                squad = [e for e in st.enemies if e.squad is not None]
                self.assertGreaterEqual(len(squad), 2, (act, seed))
                self.assertEqual(len({(e.kind, e.shape) for e in squad}), 1)
                xs = sorted(e.x for e in squad)
                ys = sorted(e.y for e in squad)
                self.assertLessEqual(max(xs[-1] - xs[0], ys[-1] - ys[0]), 6)

    def test_the_set_starts_away_from_you(self):
        for seed in range(20):
            st = build_combat(random.Random(seed), 1 + seed % 3, "fight", Player(), verify=False)
            for e in st.enemies:
                self.assertGreater(max(abs(e.x - PLAYER_START[0]), abs(e.y - PLAYER_START[1])), 2)

    def test_each_form_brings_its_own_pattern(self):
        r = Run(seed=1)
        self.assertEqual(r.player.patterns, ["beam", "slant"])
        r.grow_to(2)
        self.assertEqual((r.gift, r.player.patterns[-1]), ("halo", "halo"))
        r.grow_to(3)
        self.assertEqual((r.gift, r.player.patterns[-1]), ("lob", "lob"))
        # already learned the form's pattern from the Set? you get the next one instead
        r = Run(seed=1)
        r.player.patterns.append("halo")
        r.grow_to(2)
        self.assertEqual(r.gift, "leap")

    def test_shapes_are_introduced_one_at_a_time(self):
        from prism.run import shapes_for
        names = lambda act, layer: {s for s, _ in shapes_for(act, layer)}
        self.assertEqual(names(1, 0), {"triangle"})
        self.assertEqual(names(1, 1), {"triangle"})
        self.assertEqual(names(1, 3), {"triangle", "square"})
        self.assertEqual(names(2, 0), {"triangle", "square", "circle"})
        r = Run(seed=4)
        r.route.layers[0][0].kind = "fight"
        r.enter(0)
        self.assertEqual({e.shape for e in r.state.enemies}, {"triangle"})
        keeper = KINDS[BOSS_FOR_ACT[1]]
        self.assertNotIn("circle", keeper["shapes"])    # the first Keeper only uses what you've met

    def test_shop_wares_have_names_and_descriptions(self):
        r = Run(seed=2)
        r.route.layers[0][0].kind = "shop"
        r.enter(0)
        for item in r.shop:
            self.assertTrue(item["name"] and item["desc"] and item["label"])

    def test_enemy_shapes_lean_rounder_as_you_climb(self):
        counts = {}
        for act in (1, 3):
            n = {"triangle": 0, "circle": 0}
            for seed in range(30):
                st = build_combat(random.Random(seed), act, "fight", Player(), verify=False)
                for e in st.enemies:
                    if e.shape in n:
                        n[e.shape] += 1
            counts[act] = n
        self.assertGreater(counts[1]["triangle"], counts[1]["circle"])
        self.assertGreater(counts[3]["circle"], counts[3]["triangle"])


class Persistence(unittest.TestCase):
    def test_meta_round_trip_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "meta.json")
            m = Meta(path)
            m.record(2, False)
            m.record(3, True)
            m2 = Meta(path)
            self.assertEqual(m2.data, {"runs": 2, "wins": 1, "best_act": 3, "seen_intro": False,
                                       "seen_board_key": False, "seen_danger_tip": False})
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
                kit = Run(seed=seed).grow_to(act).player        # as a real climb would arrive
                st = build_combat(random.Random(100 * act + seed), act, kind, kit)
                self.assertGreaterEqual(len(st.paths), REQUIRED_PATHS, (act, kind, seed))
                self.assertEqual(len(set(st.paths)), len(st.paths))
                self.assertIsNotNone(st.par, (act, kind, seed))
                for name in st.paths:
                    res = solve(st, CONSTRAINTS[name], **_solve_kw(st))
                    self.assertTrue(res.won, (act, kind, seed, name))
                    self.assertGreaterEqual(res.turns, st.par)
                    self.assertEqual(self.replay(st, res.plan), "victory", (act, kind, seed, name))
                    allow = CONSTRAINTS[name]
                    for turn in res.plan:
                        for a in turn:
                            if a.kind == "cast":
                                self.assertTrue(allow(a.pattern, a.color), (name, a))

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


class Roundness(unittest.TestCase):
    """Sides are grown: the Round Door makes you round enough; every friend
    you get out rounds you out more; everyone out, and you're round."""

    def test_you_grow_rounder_with_every_rescue(self):
        from prism.consts import TOWER_ORDER
        from prism.world import ROUND_ENOUGH, your_sides
        sides = [your_sides({"friends": list(TOWER_ORDER[:k])}) for k in range(len(TOWER_ORDER))]
        self.assertEqual(sides[0], ROUND_ENOUGH)
        self.assertEqual(sides, sorted(sides))
        self.assertEqual(len(set(sides)), len(sides))           # every rescue adds sides
        self.assertEqual(your_sides({"friends": list(TOWER_ORDER)}), 0)   # all out: round

    def test_only_your_worlds_towers_count(self):
        from prism.world import your_sides
        data = {"plan": ["leaning", "lens"], "friends": ["leaning", "hollow"]}
        self.assertGreater(your_sides(data), 10)
        data["friends"].append("lens")
        self.assertEqual(your_sides(data), 0)

    def test_friends_keep_growing_after_theyre_out(self):
        from prism.world import FRIEND_START, friend_sides
        data = {"friends": ["leaning"], "sides": {"leaning": FRIEND_START}}
        self.assertEqual(friend_sides("leaning", data), FRIEND_START)
        data["friends"] += ["hollow", "toadstool"]
        self.assertGreater(friend_sides("leaning", data), friend_sides("hollow", data))

    def test_a_tower_climb_uses_your_sides(self):
        from prism.run import Run
        r = Run(3, tower="hollow")
        r.sides = 18
        self.assertEqual(r.form()["shape"], 18)
        r.sides = 0
        self.assertEqual(r.form()["shape"], "circle")

