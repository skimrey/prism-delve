# Prism Delve

*A triangle who wants to roll.*

A turn-based roguelite played with shape and colour. Pure Python + pygame-ce, CPU-only (no GPU, no image assets: every pixel is drawn from shapes).

## The world

Everything with corners lives in **the Sorter**, a tower of floors where every door is cut for exactly one shape. You are **Tri**, a triangle, and also a prism: light goes into you white and comes out as colour. That colour is what you fight with.

Corners catch on the floor, so everything in the Sorter moves in clicks: four clicks a turn, everyone together. That is the grid, and those are the beats. Only circles move smoothly, and circles don't stay. They roll out through the **Round Door**, down the **Long Ramp**, into the **Meadow**. Tri wants to roll.

**The Set** are the shapes that stay exactly as they were cut. A shape that grows a side leaves a hole in the Sorter, and the Set are afraid of holes, so they come to knock you back into your slot. They aren't cruel, just tidy. Each is dyed one colour: its own colour passes straight through it, and its opposite unmakes it. Knocked loose, a shape falls apart into edges and leaves **glint** (scraps of light) behind.

**The Stillwheel** is the last Keeper, on the Floor of Five: the one circle that never rolled. It thinks someone has to stay, so it keeps the Round Door shut. The intro introduces it; you fight it to reach the Door; and in the Meadow, it turns out, it rolled after you.

Each floor's **Keeper** holds a spare side. Take it and you grow: Triangle (Floor of Three) → Square (+3 max HP) → Pentagon (+1 cap on every colour) → the Round Door, which doesn't need you to be a circle, only round enough to fit. If the Set win, they sort you back to the bottom as a triangle again. That's why every climb starts over.

| In the world | In the game |
|---|---|
| The Sorter's floors | Acts 1-3, each with its own palette |
| A room on the floor map | Route node: The Set (fight), Hard Set (elite), Tinter (shop), Still Tile (rest), Oddity (event), Keeper (boss) |
| Clicks of the floor | The 4-beat turn |
| Light you're holding | Colour charges (regenerate each turn) |
| Facets | Relics |
| Glint | Currency |
| Sorted | Defeat |

## Run

```
python3 -m venv .venv
./.venv/bin/pip install pygame-ce
./.venv/bin/python -m prism            # optional: --seed=123
```

Headless (VM / CI): `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`

### Testing mode

```
./.venv/bin/python -m prism --dev                          # Dev button on the title (or F1)
./.venv/bin/python -m prism --dev --floor=2 --room=boss     # straight into a Keeper
./.venv/bin/python -m prism --dev --scene=tower --tower=hollow          # climb the Hollow Tree
./.venv/bin/python -m prism --dev --scene=hub --at=7000 --rescued=leaning # the Wilds, mid-jungle
./.venv/bin/python -m prism --dev --scene=towerboss --tower=windmill    # straight to a tower's Keeper
# scenes: story|ascend|roll|meadow|sorted|rolled|hub|wilds|tower|towerintro|towerboss|rescue|finale|
#         rolloff|pinball|sporedrop|curl|duneputt|glimmerpop|beachbowl|skyball
```

`RUN.txt` at the repo root has the same thing as a short cheat sheet (setup, play, test mode, tests, the tour, controls).

On a Mac, double-click `play_dev.command` for the same thing. `./.venv/bin/python tools/dev_tour.py` launches dev mode headlessly, visits every screen (each floor's fights and Keeper, every encounter, the shop, the story scenes, both endings, every tower's intro, Keeper and rescue, the Grand Roll, every zone of the hub, every game theme, the gallery) and saves a screenshot of each to `shots/`.

Rooms: `fight elite boss shop rest event`. A particular Oddity: `--event=polisher|well|trader --variant=gift|deal`. Hotkeys in dev mode: F1 menu, F2 win the fight, F3 lose it, F4 skip to the floor's Keeper, F6 climb to the next floor, F7 learn every pattern, F8 +100 glint, F9 heal (+20 max HP). The Dev menu also toggles 99 HP, all patterns and all facets, and has a second tab, **Meadow & towers**: pretend nobody, the first, or everyone is already out (dev only, never saved), jump to the start of any zone (it opens everything before it), pick any of the eight towers and climb it, see its intro, fight its Keeper or watch its rescue, play any of the eight zone games, open the tower Gallery, set how many sides you have (−/+, *auto* from who's out, or *round*), and open every zone at once.

## Test

```
./.venv/bin/python -m unittest discover -s tests
```

## Rules in brief

A cast is three picks, then you aim it on the board:

- **Pattern** (where the light goes): fixed geometry around you, like the way a game piece moves. Each pattern can be used **once per turn**.
  - *Beam*: a straight line, up/down/left/right, until a wall.
  - *Slant*: a diagonal line, until a wall.
  - *Halo*: the 8 tiles around you.
  - *Leap*: the 8 tiles an L-step away, over anything.
  - *Lob*: a plus that lands 3 tiles away in a straight line.
  Patterns come with your form: a triangle is all points, so you start with Beam and Slant; becoming a Square brings Halo, a Pentagon brings Lob. The Set attacks with these same patterns, and beating a shape that uses one you lack offers to teach it (if you already learned your next form's pattern that way, the form brings the next one you don't know).
- **Shape** (what it fits): light only touches enemies of the chosen shape and passes through everything else.
- **Colour** (what it does): Red 3, Green 2 + push, Blue 1 + stun + shield, Yellow 1 + burn + push, Cyan 2 + stun + swap, Magenta 4 + splash. Mixes (Y = R+G, C = G+B, M = R+B) cost both parts, as with light. Opposites (R/C, G/M, B/Y) deal double; an enemy's own colour is absorbed.

**Sort them together.** Every extra shape one cast fits adds +2 damage to all of them. The Set arrives in squads (one kind, one shape) that march in formation, tough alone and fragile together.

**Be quick.** Each fight has a par: the fewest turns the solver found. Up to one turn over par is a *Clean* sort (extra glint and a fourth reward to choose from); two over is *Tidy*.

**Keepers** change shape every beat on a schedule shown above them, so hitting one is a matter of timing.

**Reading the board.** Striped tiles are *danger*: a shape will strike there. They are striped in the attacker's colour and tagged with a tiny copy of *who* strikes and *when* (the beat). Hover one and a popup lists every strike on it and whether you will be standing there; your first fight points one out for you. Pink marks the one tile where a strike lands on you. Numbered dots trace where each shape steps. Hover a beat slot under the board (or Q/E) to play the turn one beat at a time, with a sentence saying what happens in order; hover a shape to see only its plan. The Board Key (K) explains all of this and opens on your first fight. Nothing is hidden or random.

**Shapes arrive one at a time.** The first rooms are triangles only (learn patterns and colour), squares join mid-floor 1 (now the shape you cut your light to matters), circles on floor 2. Each first appearance is announced.

**The Meadow** is the epilogue, and the only place in the game without a grid, beats or points. You steer freely (arrows to roll, up to hop), pick up speed down hills, and roll up to the other circles (Space) to hear what shape each of them used to be: a triangle the Set sorted back nine times, a square who stopped counting corners, one who used to be *in* the Set, a Bloom whose roots came loose. The Stillwheel is at the far end. There is nothing to win; press Esc whenever you like and Tri rests. Glimpses of it show through the round window in every room on the way up.

**Nobody is sanded down.** Sides are grown: every Keeper, every bump, every time through gives you another, and a shape that has been through enough is *round enough* to roll. So nobody in the Meadow is a perfect circle. The old hands have so many sides you can't count them; newcomers (like the square who used to be in the Set) still go ka-thunk. Roundness here means how much you've been through, not being the same as everyone else, and each of them still carries a faint outline of the shape they started as.

**Other towers (the Meadow hub).** Once you've rolled out of the Sorter, *The Meadow* opens from the title as a hub. The land runs on past the Stillwheel to the **Leaning Tower**, where a hexagon at a high window is waving: it wants to roll too. To get in, build speed downhill and hop at the lip of the kicker ramp (a hop just after the lip still counts); too slow, or no hop, and you bounce off the wall. Inside, you climb as a sphere (or nearly: see *Roundness* below): **moves roll you until something stops you**, and rolling into a shape bumps it (2 damage and a push, more if it hits a wall). The tower is one floor of fights, and **the Latch**, who keeps the window shut (it thinks the hexagon might fall). Reach the window and the two of you go out of it and roll all the way down the outside of the tower: you smoothly, it ka-thunk, ka-thunk, growing a side every few bumps (a hexagon lands with ten: round enough). From then on it's rolling about in your Meadow. Nobody else in the tower has to leave. Lose, and the Set just bundle you back out of the window. The first time you go in, three short animated cards set it up: the hexagon who asked (in its own words), what's different as a sphere (a little board showing a roll and a bump), and the Latch, pacing under the window, worried rather than mean. Each tower's cards are data (`consts.TOWERS[id]["intro"]`).

**Zones and towers.** The hub goes on zone after zone (`world.py`). Each zone ends at a tower with someone at its window; get them out and that tower's ground door opens onto the next zone, and the friend you just rescued runs the game at its start. Every tower is reached the same way (speed down a long slope, hop at the lip of a kicker) and each adds a **twist** to its floors. There are eight, all painted as pixel art:

| Tower | Zone | Who asked | Keeper | Twist |
|---|---|---|---|---|
| The Leaning Tower | The Meadow | a hexagon, waving | the Latch (worried it'll fall) | just rolling |
| The Hollow Tree | The Wilds: roots, rocks, pools, a jungle | a square stuck in a knothole | the Knot (everything stays where it grew) | knotholes |
| The Toadstool | The Glow Grove: big bouncy caps | a diamond that keeps bouncing back up | the Cap (down is dangerous) | springy caps |
| The Icicle Spire | The Frost: ice sheets, snowdrifts | a pentagon frozen mid-roll | the Rime (change is just melting) | snow |
| The Sundial | The Dunes: big dunes, soft sand, an oasis | a triangle that's been the pointer for ages | the Hourglass (time stops if it leaves) | colour pools |
| The Lens | The Glimmer Caves: ringing crystals | a diamond focusing all the light | the Focus (light goes in one line) | crystal facets |
| The Lighthouse | The Coast: tide pools, sand | a pentagon who's never been down | the Beacon (the lamp needs its keeper) | blowholes + currents |
| The Windmill | The Windy Heights: gusts, springs | a diamond kept as a weather kite | the Vane (turn with the wind) | gusts + springy caps |

**Twists** are special floor tiles. Every one of them is a way to *aim a roll*, so each tower asks a different question about the same move:

- **Knotholes** (the Lighthouse calls them blowholes): roll into one and you come out of its twin, still rolling. A twin with a shape on it is plugged.
- **Springy caps**: fling you over the next tile (a shape, a wall, anything) and you land two on, still rolling. Get behind things.
- **Snow**: packs onto you as you roll through: +1 to your bump for every tile of it. Take the long way round and hit hard.
- **Colour pools**: dye you. Your bump lands as that colour: red hits hard, green shoves twice, blue stuns, the opposite colour doubles it, and a shape of the same colour just absorbs it.
- **Crystal facets**: turn a roll a quarter turn, the way they slant, and bend light too: every straight Beam, yours *and theirs*, turns at a facet. The danger stripes follow the bend.
- **Currents** (one tile) and **gusts** (two tiles): anyone who ends a beat on one, you or the Set, is carried along it as far as it's clear. Drift them into walls, into each other, into your line.

The Set walk straight over holes, caps, snow, pools and facets (corners catch, so only rolling things notice those); currents and gusts carry everyone. Every tower's fights are still checked by the solver (each has a par, so each is winnable). The first time you meet a twist it gets a banner, every special tile explains itself on hover, and each tower's intro card shows its twist on a strip of its floor, rolled by the real rules (a tower with two twists shows both, in turn).

**Difficulty climbs with your route, not the tower.** However you order your towers (see *Pick your towers*), the first one you reach is gentle (four rooms, the Set at their easiest), the middle ones tougher, and the last ones toughest (six rooms, bigger squads). So a shuffled world still ramps up properly.

**Keepers have faces.** Each tower's Keeper has its own expression to match what it believes: the Latch worried, the Knot stubborn, the Cap giddy, the Rime stern, the Hourglass fussy, the Focus intense, the Beacon proud, the Vane dizzy (and the Sorter's Keepers strict, haughty and, for the Stillwheel, melancholy). The same face shows on its intro card, in the fight, and, softened into a smile, when you meet it again in the hub after its friend is out.

**Roundness.** Nobody has to become a perfect circle to roll. The Round Door makes Tri *round enough*: ten sides. Every friend you get out of a tower rounds you out more (about 10 → 12 → 15 → 18 → 22 → 26 → 31 → 35 sides across eight towers), and you only become truly round, all the way round, once everyone who asked is out. A friend lands from its rescue with ten sides (one per bump on the way down) and grows two more with every friend you rescue after it (up to 26), so the Meadow always has a spread: old hands who are nearly smooth, and recent friends who visibly aren't. Every zone also has a **newcomer** or two: shapes with only four to seven sides who have just started rolling and tumble up and down all day, ka-THUNK, puffing dust at every corner ("Is this rolling? It feels like falling over. Lots."). The rescue card says it: "you: 15 sides, now 18". You can *see* it: at low counts you're a visible polygon that goes ka-thunk; near the end you're nearly smooth.

**The Grand Roll.** Get the last friend in your world out and, instead of going straight back to the hub, everyone lines up on the crest above the Meadow: you (round, all the way round now), every friend you rescued, and the Stillwheel. ("Last one down's a square!") You all roll down the Long Ramp together, painted as a rainbow road, the newer friends still going ka-thunk. In the field they hop up into a ring around you, a circle made of everyone, and the whole wheel rolls off across the field while a rainbow comes out and each tower's Keeper, waiting along the way with its new job, cheers it past ("Things change! It's fine!"). Then a last card, and the hub. It plays once (`meta["finale_seen"]`); the Dev menu's *Finale* button or `--scene=finale` replays it (`finale.py`).

**Go back to anything, any time.** Nothing you've reached is ever closed off:

- **Climb any tower again.** Once a tower's friend is out, its window still takes you in (hop in at the lip, as before), and its Keeper, standing by the open door, ends its chat with an invitation ("The floors have all shuffled since you came. Climb again?"). A climb for fun is **generated fresh every time**: a new seed, and never the same route as your last climb of that tower, but the same twists, the same difficulty for its place in your world, and the same checks as always (every floor path is fair, every fight re-rolled until the solver finds two different ways to win, and given a par). The Keeper greets you with a rematch line; at the top nobody's waiting, so you roll down the outside on your own and land by its door ("Up and down again! Times up the Hollow Tree: 3").
- **The Map** (M or Tab in the hub) shows every tower in your world in order: the ones you've reached (friend out, how many times you've climbed it, or someone still at the window) and the ones still veiled. *Go* takes you to any reached zone, *Climb* / *Again* straight up any reached tower, and there's a button back to the Meadow's start.
- **Slot in at any floor of the Sorter.** Once you've reached a higher floor, *New Run* asks where you slot in: the Floor of Three, Four or Five, any you've reached (all three once you've rolled out). Starting higher, you're grown as if you'd beaten the Keepers below (their sides, their patterns) and get 45 glint per floor skipped.

**Zones open as you go (or all at once).** By default each zone's door opens when you get the previous tower's friend out, so the hub is a chain you walk, with a reason to go on. *Settings → Every Meadow zone open* opens them all from the start (for players who'd rather wander); the difficulty still climbs with each tower's place in your route either way.

**The zones feel different to roll through.** Roots bonk you unless you hop them or hit them fast (then they fling you over). Pools float you. Ice slides (don't push, lean). Snowdrifts and sand slow you. Big caps throw you into the air. Gusts push you along. Crystals bounce you back unless you hop. Each zone has its own sky, far layer (tree trunks, giant mushrooms, mountain peaks, mesas, stalagmites, the sea, floating islands), ground, plants and little lives (moths, fireflies, spores, snow, dust, sparkles, gulls, petals), and the colours blend from one into the next as you roll.

**Pick your towers.** *Settings → Towers in your world* (or the Dev menu's Gallery) shows every tower, its zone, who's in it, its Keeper and its twist. Click a tower to put it in your world or take it out; the numbers are the order you'll find them in. *Curated order* puts them back; *Shuffle* randomizes the order. The plan is saved (`meta["plan"]`).

**One game per zone.** Each zone has its own game, right at its start, run by whoever opened it (the friend from the tower before), with a sign and a bouncing **!**. Every game casts you as a ball, because rolling is the whole point:

| Zone | Game | In the vein of | What you do |
|---|---|---|---|
| The Meadow | **Roll-Off** | marble sumo | last one on the painted bowl wins (Bump or Tilt) |
| The Wilds | **Side Show** | pinball | flippers paint you their colour; free shapes of your colour |
| The Glow Grove | **Spore Drop** | Peggle | drop through a field of sleepy shapes; wake the level's colour; land in the sliding cap for a free drop |
| The Frost | **Curl** | curling | slide down the ice to the rings, hold Space to sweep; three ends against a friend |
| The Dunes | **Dune Putt** | mini golf | six holes: dunes carry you sideways, sand slows you, the oasis sends you back, rocks bounce you |
| The Glimmer Caves | **Glimmer Pop** | bubble shooter | fly up into the crystal roof; three of a colour round off and float away |
| The Coast | **Beach Bowl** | bowling | ten sandcastles at the end of the boardwalk; lean while you wind up for a curve |
| The Windy Heights | **Sky Ball** | skee-ball | roll up and off the ramp into the rings; mind the wind streamer |

They all share one frame (`arcade.py`): a side panel with the score, your best, the rules and the keys; the field; and the host, cheering. Nothing is at stake; best scores are kept.

**The Side Show (pinball).** You're the ball. Each stage has exactly two colours: the **left flipper is one, the right flipper is the other, and whichever flipper you touch paints you its colour**. Shapes pop up in those two colours only; hit one while you're its own colour and it grows a side, and round, it rolls off the table, free. Free them all and the stage clears (a light show and multiball), and the next stage brings two new colours, more shapes, and shapes that drift about. Shapes of your current colour glow so you can see what to aim for. Also on the table: four R-O-L-L rollover lanes (light them all for a bigger multiplier; the flippers shuffle which are lit), three mushroom bumpers, two slingshots, a spinner, three drop targets (knock all three down: every shape grows a side), a knothole that swallows you and bursts your colour over every matching shape, a ball save at the start of each ball, and a lit marquee. Three balls; your best score is kept.

**The Roll-Off.** Near the start of the hub a beach-ball of a circle bounces by a sign, with a bouncing **!** over it. Roll up and say hello (Space) and it invites you to the spheres' favourite game: everyone rolls onto a big painted bowl floating over a pool of colour, and the last one still on it wins the round. Falling off is the best part (splash, bob about in the pool, cheer, bounce back on for the next round), so nothing is ever at stake. It's drawn in 3D (a small perspective projection: a tilting disc, shaded marbles with shadows) and comes in two flavours to compare: **Bump** (steer your marble with the arrows, Space to dash into others; the bowl shrinks after a while so every round ends) and **Tilt** (the arrows tip the whole bowl; everyone rolls downhill, they scramble back uphill, you grip better; tip them all off and stay on). Whoever you've rescued from the towers joins in. Esc takes you back to the host, who asks for another go.

**Pixel world, smooth characters.** The *world* is pixel art (`pixel.py`): scenery on a low-resolution canvas with hue-shifted shading ramps (shadows lean cool, lights warm) and a dark outline, scaled up with nearest-neighbour so every pixel stays crisp. The towers are painted brick by brick and leaf by leaf (`towers_art.py`), the hub landscape and the title scene column by column (`hubart.py`), the combat board's tiles, walls and twist tiles per tower material (`board_art.py`: stone, wood, ice, sand, crystal, planks...), and the game arenas too. The *characters* are smooth vector shapes, deliberately: the story is about getting rounder, and a smooth outline is the only way to show a 31-sided shape as different from a 35-sided one (or a circle). `art.PIXEL_CHARACTERS = True` switches them to pixel sprites for comparison. Text and panels stay crisp.

**Settings** (title screen, O): *Colour-blind mode* (every colour also wears its letter, R G B Y C M, on a little disc: on shapes, buttons, pips and danger tiles), sound on/off and volume, fullscreen, *Every Meadow zone open*, and *Towers in your world...* (the Gallery).

**Sound** is synthesized on the spot: every beat of a fight clicks, colours each have a note, shapes knocked loose pop. Rolling (the ramp, the Meadow) is the only smooth sound.

**Saving.** The run is saved whenever you're on the floor map; quit any time and choose *Continue* on the title.

**The map is fair.** Every floor opens with a fight, and every path to the Keeper has at least three fights, never two calm rooms in a row, and at most two Hard Sets. Paths still differ (some have more Hard Sets), so you can choose an easier way up, but never one without fighting. Fights are where you grow: glint and a reward pick (a Hard Set always offers a facet). Calm rooms only spend or trade what fights give you: the Tinter sells for glint, the Still Tile heals or deepens one colour, Oddities trade.

**Oddities are gifts or deals.** A *gift* is two bonuses: pick one, no walking away. A *deal* puts a cost on each bonus, so walking away is a real choice. Low floors mostly give gifts, high floors mostly make deals. Every choice shows its label, its outcome as icons, and the same thing in plain words ("+1 max Red charge", "New facet, Hard Corner: push collisions deal +2 damage; -1 max Green charge"). The Oddities: a Pool of Colour, the Polisher (a cheerful octagon in goggles who buffs facets onto shapes), and a Drifting Tinter. Costs are glint or a little colour, never pain.

**Facets look like gems.** Every facet is the same cut gem, tinted only when it is about a colour (Sharp Red: red) and prismatic otherwise. Shapes and colours on their own always mean enemies, so no bonus is drawn as "a purple square".

**Rooms are shown, not described.** Oddities and the Still Tile are small animated scenes: each choice is a picture button (a label and its outcome as icons: ♥ +5, a colour pip +1, glint −10...), hovering previews it on the stage, and picking it plays out what happens.

**Banter.** Shapes trade insults about corners, sides, angles and stability: occasionally when they land a hit or get knocked loose, always when a Keeper arrives or falls.

Enemies are kind (behaviour + pattern) × shape × colour, all independent. Every fight is checked at generation to have at least two distinct winning styles.

## Code map

| Module | What |
|---|---|
| `rules.py`, `state.py`, `solver.py` | Deterministic engine, state, beam-search solver (no pygame) |
| `enemies.py` | The Set: kinds, patterns, squads, AI |
| `dungeon.py`, `run.py` | Room/route generation; the climb (forms, rewards, shops, events) |
| `consts.py` | Numbers, colours, relics (facets), `FORMS`, `FLOORS`, `TOWERS` (all eight), `TWISTS` |
| `widgets.py`, `art.py`, `scene.py` | Palette and buttons; procedural characters, particles, gradients; composed scenery (tower, map icons, morphs) |
| `screens.py` | Title, help, floor map |
| `combat_ui.py` | The combat screen: picking, aiming, previews, beat-by-beat reading, animation; the Board Key |
| `banter.py` | What shapes say to each other (rationed) |
| `dev.py` | Testing mode: jumps, cheats, hotkeys (`tools/dev_tour.py` tours it headlessly) |
| `vignettes.py` | The animated scenes for Oddities and the Still Tile |
| `world.py` | The hub as a chain of zones: zone data (look, features, locals, game), the plan, layout and terrain |
| `meadow.py` | The playable epilogue and the hub: rolling, hopping, talking, hosts, guardians, characters |
| `hubart.py` | Painting the hub (and the title screen) as pixel art, zone by zone |
| `pixel.py` | The pixel-art kit: shading ramps, brushes (bricks, shingles, leaves...), pixel characters |
| `towers_art.py` | The eight towers, painted |
| `board_art.py` | The combat board's pixel tiles, walls and twist tiles |
| `worldmap.py` | The Map: every tower in your world, go anywhere, climb anything again |
| `finale.py` | The Grand Roll: everyone down the Long Ramp together, then a wheel of everyone |
| `gallery.py` | The tower gallery: pick which towers are in your world, and their order |
| `arcade.py` | The shared frame for the zone games (panel, field, host, best scores, end card) |
| `rolloff.py` | The Roll-Off: the spheres' 3D marble game (bump and tilt modes) |
| `pinball.py` | The Side Show: pinball where each flipper paints you its colour, in stages |
| `sporedrop.py`, `curl.py`, `duneputt.py`, `glimmerpop.py`, `beachbowl.py`, `skyball.py` | The other six zone games |
| `sound.py` | Synthesized sound effects |
| `settings.py` | Player settings and the colour-blind letters |
| `node_screens.py` | Reward, Tinter, Still Tile, Oddity, end |
| `story.py` | Intro, growing a side between floors, the roll, the tower intros, the rescue (out of the window and down the outside) |

Licensed under the MIT License.
