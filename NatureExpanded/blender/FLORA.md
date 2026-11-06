# Flora models

One Blender script per plant, built on `naturekit.py` (read it, and `poppy.py`, the worked example, first). Each is a
block model: Blender meters, Z up, the ground at z = -0.5 (`nk.GROUND`), the plant standing on it around the origin.

    blender -b --factory-startup --python <script>.py -- <unity models folder> <preview folder>

with `NatureExpanded/unity/Assets/NatureExpanded/Models` and `NatureExpanded/unity/Build/previews`.

## Rules for every plant

- **A clump, not a stem.** World generation puts one model on a block, and drifts of them make the meadows. From
  3 m off a flower block must read as a mass of its color: a dozen or more heads (more for small flowers), most of them
  facing up or out, the real flower's size or a touch bigger. Single stems read as nothing in game.
- **Real colors at full strength** for flowers, berries and caps (`nk.petal(..., sat=1.0)`); foliage stays muted
  (`nk.plant` defaults), since bright clean greens read as plastic.
- **Grass among meadow flowers:** a few `nk.tuft(...)` of `nk.grass()` among the stalks, so the ground under a drift
  isn't bare. Not for forest-floor, water, desert or snow plants unless the spec says so.
- **Footprint** inside x, y in [-0.45, 0.45] unless the spec gives another size (bushes and logs may spill over a
  neighbor block; the game doesn't mind).
- **Triangles:** flowers 1,500 to 3,500, bushes, cacti and logs up to 5,000. `nk.export` adds the far LOD.
- **Leaves and petals are single sheets** (the game draws them double-sided). No alpha textures: everything is
  geometry.
- **Variety inside the clump:** heights, leans, sizes and a few buds or spent heads vary; the game turns each block at
  random, so nothing should look mirrored or gridded.
- **Detail down to the texel on anything looked at up close** (mushrooms, the log, cacti). Smooth noise alone reads as
  blurry vector art at arm's length and Voronoi cells alone as crazy paving: give a surface cells, crests, grit, a
  ragged edge and real relief (bump distances are in meters, so the relief doesn't change with the atlas size).
  kit_forest has the pieces (`moss_layer`, `bolete_cap`, `agaric_cap`, `honeycomb`, `_cells`, `_ridged`, `_warped`,
  `_polar`). A patch of one material over another (moss on bark) draws its edge in the texture, fading to exactly the
  surface under it, never where its faces happen to cut through.
- **Texel density:** the export prints the pixels per cm each material gets. Weight the atlas toward the parts seen up
  close with `export(..., density={"Cap": 1.5, "Leaf": 0.5})` (litter and fern leaves only need their color); aim for
  8+ px/cm on a log's bark and moss, 15+ on mushroom caps. The solid plants (NatureBuilder.Solid) keep their atlas's
  own size in the bundle, up to 2048; everything else drops to 512.
- **Check close-ups in the game's shader:** `Unity -batchmode -quit -projectPath unity -executeMethod
  NatureCloseups.Run -plants Bolete,MossyLog` builds the bundle and renders `unity/Build/plants/<Name>_stand`,
  `_crouch`, `_macro`, `_back` and `_low` (raking sun, for the normal map) at about 1080p's pixels per degree.

## Pine forest meadows

| Name | Script | What |
|---|---|---|
| Poppy | poppy.py | Done (the example). |
| Lupine | lupine.py | 6 to 8 dense conical spikes of purple-blue pea flowers (`nk.spike(shape="pea")`), 50 to 80 cm, a few pink and white among them, buds at the tips; palmate leaves (7 to 9 narrow fingers on a stalk) low down. |
| Cornflower | cornflower.py | 15+ ragged bright blue flower heads (a ring of frilled, trumpet-ended florets round a darker purple-blue center) on wiry branching grey-green stems, 40 to 60 cm; narrow grey-green leaves. |
| OxeyeDaisy | oxeye_daisy.py | 18+ classic white daisies, 4 to 5 cm across: a ring of ~20 narrow white petals round a flat golden-yellow disc, on thin stems 30 to 60 cm; dark green toothed leaves low down. |
| Paintbrush | paintbrush.py | Indian paintbrush: 10 to 14 short upright stalks, 25 to 40 cm, each tipped with a 6 to 8 cm brush of scarlet-orange bracts (red at the tips, greener toward the base), narrow leaves up the stalks. |
| BlackEyedSusan | black_eyed_susan.py | 15+ heads 6 to 8 cm across: 12 to 14 golden-orange petals, drooping slightly, round a raised dark chocolate-brown dome; rough hairy stems 40 to 70 cm; lance leaves. |
| Coneflower | coneflower.py | Purple coneflower: 10 to 12 heads of drooping pink-purple petals (`droop` well down) round a big spiky orange-brown cone, 60 to 90 cm stout stems; dark lance leaves. |
| QueenAnnesLace | queen_annes_lace.py | 8 to 10 flat white lacy umbels 8 to 12 cm across (`nk.umbel`, with the spokes shown), a few curled up into "bird's nest" seed heads, on tall thin branching stems 60 to 100 cm; feathery carrot-like leaves low. |
| RedClover | red_clover.py | A low mat, 15 to 25 cm: 20+ round pink-red to magenta pompom heads 2 to 3 cm, trefoil leaves (three ovals with a pale chevron) filling the ground between. |
| Bergamot | bergamot.py | Wild bergamot: 10 to 12 shaggy lavender-pink pompom heads 4 to 6 cm (a ragged ball of tubular florets), on square stems 50 to 80 cm, pairs of opposite lance leaves. |
| Chicory | chicory.py | Roadside chicory: 4 to 5 stiff, nearly leafless, branching grey-green stems 60 to 100 cm, sky-blue flowers 3 to 4 cm (square-tipped petals) dotted along them (20+ flowers); a rosette of dandelion-like leaves at the base. |

## Forest floor and edges (no grass)

| Name | Script | What |
|---|---|---|
| Fern | fern.py | A lush clump of 10 to 14 arching bracken/sword fern fronds, 50 to 80 cm, each a midrib with 20+ pairs of leaflets that shrink toward the tip, a couple of fiddleheads uncurling in the middle. Footprint up to 0.6. |
| FlyAgaric | fly_agaric.py | A fairy ring arc of 5 to 7 fly agaric toadstools: bright red caps (domed young, flat old) with white warts, white gills underneath, white stems with a skirt and a bulbous base, 8 to 20 cm tall; a little moss and leaf litter at the base. |
| Bolete | bolete.py | A cluster of 4 to 6 fat brown-capped porcini: chestnut caps 6 to 14 cm, a spongy pale yellow underside, thick club-shaped pale stems with a net pattern; leaf litter. (Food.) |
| Trillium | trillium.py | 8 to 10 trilliums 20 to 35 cm: a whorl of three broad leaves, above it one white flower of three broad petals (a couple aging to pink). |
| WildStrawberry | wild_strawberry.py | A low ground mat, 10 to 15 cm: trefoil toothed leaves, a few small white five-petal flowers with yellow centers, and 10+ small bright red berries hanging on thin stalks. (Food.) |
| Foxglove | foxglove.py | 3 to 5 tall spikes 90 to 140 cm of drooping tubular bells (`nk.spike(shape="cup")`), pink-purple with spotted throats, a couple white; a big rosette of soft broad leaves. |
| Morels | morels.py | 6 to 9 morels 6 to 12 cm on burnt ground: tall honeycomb-pitted caps (tan to dark brown) on short pale hollow stems, with ash and a charred twig. (Food.) |
| Snowdrop | snowdrop.py | 15+ snowdrops 10 to 15 cm: a single nodding white bell on each arched stem (three outer petals, a green-tipped inner cup), pairs of strap leaves. |

## Shrubs, bushes and logs

| Name | Script | What |
|---|---|---|
| WildRose | wild_rose.py | A rounded thorny bush 0.8 to 1.1 m tall, footprint up to 0.8: arching canes with clusters of small oval leaves, 25+ single pink five-petal roses with yellow centers, and a few red-orange hips. |
| Elderberry | elderberry.py | A bush 1.2 to 1.6 m, footprint up to 0.9: arching lenticel canes with smooth pinnate leaves (`ks.pinnate_leaf`), about 5 lacy creamy-white flower heads 15 cm across built as rays and pedicels ending in puffs of florets (`ks.flower_cyme`, no solid plate), and a couple of heavy clusters of dark purple-black berries (`ks.berry_bunch`). Nothing floats in either LOD (`ks.report_floating`). |
| Sumac | sumac.py | Staghorn sumac 1 to 1.5 m, footprint up to 0.8: a few stout fuzzy branches, long compound leaves turned scarlet and orange (fall color, the point of it), upright dark red cone-shaped fruit clusters. |
| MossyLog | mossy_log.py | A fallen, half-rotten log 2 to 2.5 m long and 35 to 45 cm thick lying on the ground (footprint long along x), bark peeling in places, green moss over its top, a few shelf fungi on its side, a broken stub of branch, a fern or two at one end. Up to 5,000 triangles. |
| CharredShrub | charred_shrub.py | A burnt black bush 50 to 80 cm (charred bare twigs, grey ash at the base) with bright fresh green shoots coming up from its base. |
| Winterberry | winterberry.py | A leafless bush 0.8 to 1.2 m of bare grey-brown twigs thick with clusters of glossy bright red berries (200+ small berries; it's the color that counts), a little snow sitting on the twigs. |
| FrostedJuniper | frosted_juniper.py | A low spreading blue-green juniper 0.5 to 0.8 m tall, footprint up to 0.9: dense scaly sprays, frosted pale blue berries, snow resting on top. |
| DeadBrush | dead_brush.py | A tangle of dead, grey, broken twiggy brush 40 to 70 cm, with a few dry tan seed heads; reads as wasteland scrub. |

## Water's edge, snow and wasteland

| Name | Script | What |
|---|---|---|
| Cattail | cattail.py | 10 to 14 tall flat strap leaves 1.2 to 1.6 m and 5 to 7 stalks with brown velvet sausage heads 15 cm, a thin spike above each. |
| Reeds | reeds.py | A dense stand of 30+ thin reed stems 1.2 to 1.8 m with long narrow leaves, half of them topped by feathery purple-brown plumes. |
| BlueFlagIris | blue_flag_iris.py | 6 to 8 violet-blue iris flowers (three falls with yellow and white veined throats, three upright standards) on 50 to 80 cm stalks, a fan of tall sword leaves. |
| MarshMarigold | marsh_marigold.py | A low glossy mound 25 to 35 cm of round heart-shaped leaves with 15+ buttery yellow cup flowers of five petals. |
| AlpineAster | alpine_aster.py | A low cushion 15 to 25 cm with 15+ blue-violet asters (a ring of many thin petals round a yellow center). |
| Heather | heather.py | A dense low mound 25 to 40 cm of fine needle-leaved twigs, covered in tiny purple-pink bell flowers along the tips (color mass is what matters). |
| SilverSage | silver_sage.py | A soft round mound 40 to 60 cm of felted silver-grey leaves, a few spikes of pale yellow flowers. |
| Fireweed | fireweed.py | 6 to 8 tall spikes 90 to 130 cm of magenta-pink four-petal flowers (open lower, buds at the top, a few seed pods splitting with white fluff at the bottom); willow-like leaves up the stems. |
| Thistle | thistle.py | 3 to 5 spiny stems 60 to 100 cm, spiny grey-green lobed leaves, 8 to 12 fat purple shaving-brush flower heads on spiny green bulbs, one or two gone to white fluff. |
| WildMustard | wild_mustard.py | Branching stems 50 to 90 cm topped with 12+ loose clusters of small four-petal bright yellow flowers, thin seed pods below them. Some grass. |
| CurlyDock | curly_dock.py | 2 to 3 tall stalks 60 to 100 cm of dense rust-red to chocolate seed clusters (the color is the point), a rosette of long wavy-edged leaves going red at the base. |

## Desert (no grass)

| Name | Script | What |
|---|---|---|
| PricklyPear | prickly_pear.py | A sprawling clump 50 to 80 cm, footprint up to 0.8: 15 to 20 flat oval blue-green pads joined edge to edge, spine dots on them, 6+ yellow cup flowers (one or two pink-orange) and a few magenta fruits on the pad rims. |
| BarrelCactus | barrel_cactus.py | 2 to 3 ribbed barrel cacti 30 to 60 cm, green with long hooked red-yellow spines along the ribs, a crown of red-orange flowers and yellow fruit on top of each. |
| Ocotillo | ocotillo.py | 10 to 14 tall spiny whip canes 1.8 to 2.5 m fanning out from one base, small leaves along them, bright red-orange flower clusters at the tips. |
| AgaveBloom | agave_bloom.py | A big rosette of thick blue-grey spiked leaves 0.8 m across, from its center a tall stalk 2.5 to 3 m with branching arms near the top carrying clumps of yellow flowers. Up to 5,000 triangles. |
| DesertMarigold | desert_marigold.py | A woolly grey-green mound 25 to 35 cm with 20+ bright yellow daisies held just above on thin stems. |
| Globemallow | globemallow.py | 6 to 8 upright wands 40 to 70 cm crowded with small apricot-orange cup flowers (30+), grey-green crinkled leaves. |
| Sagebrush | sagebrush.py | A twisted silver-grey woody shrub 60 to 90 cm, footprint up to 0.7: shaggy bark at the base, fine silver three-lobed leaves in dense tufts. |
| EveningPrimrose | evening_primrose.py | A low sprawl 15 to 25 cm of 10+ large white four-petal flowers 6 to 8 cm across (a couple fading to pink), long narrow leaves. |

## Ground cover (2026-11-06)

The 25 ground-cover models (leaf litters, needle mat, moss, twigs, cones, acorns, stones, pebbles, mud, ash, ice, gravel, rust,
tumbleweed; specs in `blender/groundcover/SPEC_forest.md`, `SPEC_stones.md`, `SPEC_harsh.md`) are plants for the pipeline
but not for the rules above: patches 0.8 to 1 m across lying on the ground, no taller than a few centimetres (the tumbleweed
40), their textures keep the size they were baked at (the bundle's 512 cap is for flowers) and they go in
`natureexpanded-ground.unity3d`. NatureBuilder and NatureShaderDEM carry the name list (`GroundCover`, `Leafy`): they don't
sway, and only leaves, needles, moss and stems let light through.
