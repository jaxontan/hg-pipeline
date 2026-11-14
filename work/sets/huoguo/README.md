# 火锅店 white model — 《老汤》 pilot set

Built by `win/blender_set_huoguo.py`. Blender 5.2.3 LTS, EEVEE, 9:16.

A **white model**: one grey clay family, real geometry, no textures, no materials to
speak of. Its job is not to look good. Its job is to hand the video models a
structurally correct frame, so that lighting, skin, steam, rain and reflections are
invented by the generator instead of being modelled by us and then thrown away.

## What is in the scene

| Piece | Detail |
|---|---|
| Interior | 9.0 × 7.0 m, ceiling 3.2 m, 0.6 m tiled floor with grout gaps |
| Front wall | door opening 1.30 × 2.10 m with a 13-strand beaded curtain |
| Left wall | window 2.6 × 1.4 m, 5 mullions, cool night glow behind the glass |
| Back wall | kitchen pass-through (1.70 × 0.95 m) with shelf and pot stacks |
| Right wall | bar counter, register, drinks fridge, two bar shelves, menu panels, AC unit |
| Tables | 4 round tables (hero r = 0.50 m at `(0.30, 0.50)`), 16 stools |
| Hero props | 鸳鸯锅 with divider, rim, handles, lid; 4 plates, 4 bowls, 3 dips, chopsticks, 2 glasses, napkin box |
| Street strip | 2.7 m deep, opposite wall with shutters, lamp post, folding stall table + pot + 2 stools + cardboard sign |
| Proxies | 6 mannequins — 5 seated, 1 standing (二叔 over the pot). **Placeholders for L1–L4**, not characters |
| Lights | hero key, ceiling fill, cool window bounce, street fill, warm pendant practicals ×4, rear rim, street lamp |

Deliberately absent: steam, rain particles, crowds, signage text, any texture. All five
are cheaper for the video model to invent than for us to model, and none of them
survive into a depth pass anyway.

## Files

| File | What it is |
|---|---|
| `huoguo_set.blend` | the set, all cameras, all lights. sha256 printed on every build |
| `set_huoguo_cameras.json` | camera rig table — position, target, lens, intent. The shot list reads this |
| `sNNN_beauty.png` | clay render, composition reference |
| `sNNN_depth.png` | normalised Z pass, **near = white**, range derived per rig (see below), background black |
| `sNNN_depth_ctrl.png` | the depth pass blurred 4 px — **this is the file ControlNet gets**, not the sharp one |
| `sNNN_normal.png` | world-space normals remapped to RGB |

Depth and normal are produced with **material overrides**, not the compositor Z pass.
The compositor path in Blender 5.2 returns a flat gradient with no structure — a guide
pass that looks plausible but is empty is worse than no pass at all. Do not "simplify"
this back into a compositor node tree.

Two things make the depth map usable, and both were bugs first:

1. **The ramp is per rig, not global.** A single 0.6–9.0 m range works for a wide shot and
   destroys a close-up: at a 1.3 m subject distance the whole frame lands in the top tenth
   of the ramp and renders as one flat grey. `depth_range()` derives the ramp from the rig —
   `near = 0.5 × distance-to-target` (clamped 0.35–4.0 m), `far = near + max(1.6 × d, 3.2 m)`.
   Every shot's actual range is written into `set_huoguo_cameras.json` as `depth_near_m` /
   `depth_far_m`, so a pass can always be reproduced or compared.
2. **Guide passes render through Standard, not AgX.** AgX maps emission 1.0 to about 0.85
   and compresses exactly the highlight end where near geometry lives. The beauty pass keeps
   AgX; the depth and normal passes switch to Standard and switch back.

## Camera rigs

Positions in metres, room origin at floor centre, +Y toward the kitchen.

| Rig | Position | Target | Lens | Intent |
|---|---|---|---|---|
| s001 | 3.55, −3.10, 1.58 | 0.00, 0.70, 1.05 | 24 | establishing, in through the door |
| s002 | −0.55, −0.65, 1.02 | 0.32, 0.52, 0.88 | 35 | low hero framing on the pot |
| s003 | 2.75, 0.55, 1.22 | 0.20, 0.45, 1.10 | 24 | profile two-shot, 二叔 standing over 苏念 |
| s004 | 0.72, −0.60, 1.20 | 0.30, 1.18, 1.16 | 50 | close on 苏念, kitchen pass behind her |
| s005 | −1.05, −2.15, 1.20 | −2.28, −0.40, 1.14 | 40 | 顾衍 alone at the window table |
| s006 | 3.10, −5.45, 1.52 | 1.20, −4.30, 0.95 | 35 | street stall two-shot, through the door |
| s007 | 3.90, 1.90, 1.58 | −0.20, −0.90, 0.92 | 30 | reverse wide, tilted down off the ceiling |
| s008 | 2.55, −3.85, 1.32 | 1.02, −4.86, 1.00 | 24 | the first customer behind the folding stall, shutters behind |

Each rig maps onto a beat of `work/story/premise_laotang.md`: s001–s004 are episode 1
beats 1–4, s005 is beat 3, s006–s008 are beats 5–7.

Every build ray-casts each camera at its target and prints `SIGHTLINE <shot> CLEAR|BLOCKED`.
A `BLOCKED` line means something is in front of the lens — read the `first_hit` name before
reacting:

- **A named prop or character that is the subject of the shot** is expected. s002 hits
  `Pot_Rim` at 0.86 because the rig looks into the pot from just above its near rim; s004
  hits `P_Sunian_Head` at 0.97 and s008 hits `P_Buyer_Shoulders` at 0.95 because each rig
  is a close-up and the subject *is* the thing the ray reaches. These are correct frames,
  not defects.
- **Anything else** — a wall, a table edge, a stool, another diner's back — is a broken rig.
  Move the camera, do not render it and hope.

## Re-render

```
python win/blender_set_huoguo.py --shot-id all              # 8 shots, 3 passes each
python win/blender_set_huoguo.py --shot-id s002             # one shot
python win/blender_set_huoguo.py --shot-id all --samples 16 # fast look-dev
python win/blender_set_huoguo.py --shot-id all --ctrl-only  # re-blur existing depth passes
```

Blender is auto-detected under `C:\Program Files\Blender Foundation`; override with
`BLENDER_EXE`. The build runs headless in its own process, so it never touches an open
Blender session.

## Guide-pass verification

Every build prints, per shot:

- `SIGHTLINE <shot> CLEAR|BLOCKED frac=… first_hit=…` — is anything in front of the lens
- `DEPTH <shot> near=… far=…` — the ramp actually used for that frame
- `DEPTHSTAT <shot> std=… OK|FLAT` — the pass is measured after render, not trusted

`FLAT` means the depth image has almost no gradient and is not a usable control signal, no
matter how plausible it looks. Fix the rig or the ramp; never ship it. The threshold is
`std > 0.06` on 0–1 values, measured off the saved PNG rather than the render buffer, so it
tests the file that the video model will actually see.

## Does the model actually use the guide? Measured, not assumed

Test rig: `s001_depth` → Z-Image Turbo INT8 + Fun ControlNet 2.1 Lite, seed `420261113`,
8 steps, 768 × 1344, ~8 s per keyframe. Three runs, one variable each:

| Control input | Strength | Result |
|---|---|---|
| sharp depth | 0.85 | layout honoured, **but a white arc above every head** — the model reads the hard near-white silhouette edge as a separate object |
| blurred 4 px | 0.72 | halos gone, **layout drifts** — beaded curtain and window swap sides |
| blurred 4 px | 0.85 | **both**: no halos, layout held |

So the guide is genuinely used, not decorative. Against `s001_beauty.png`, the keyframe at
blurred/0.85 places the two cone pendants, the beaded curtain, the pass-through with its
shelf, the hero table and its pedestal, the red stool clusters and the standing waiter in
the same places — and it invents steam, skin, rain, tiles and menus on top, which is exactly
the division of labour the white model is for.

The control pass therefore ships **pre-blurred** (`write_depth_ctrl`, radius = width / 192,
4 px at 768), and the recipe is blurred depth at **0.85**, not sharp at any strength.
Rebuild the control passes without re-rendering with `--ctrl-only`.

### Failure modes seen so far, and what caused them

| Symptom in the keyframe | Cause | Fix |
|---|---|---|
| white arc above every head | razor-sharp near-white silhouette edge read as a separate object | blur the control pass 4 px |
| black wedge at the armpit | proxy arm cylinder **tangent** to the torso — a hairline sliver of far background | arm radius 0.055 at x ±0.178 so it bites into the torso |
| ceiling rendered as a black void | ceiling is nearest geometry, clips to pure white, model reads it as unlit sky | tilt the rig so the ceiling is not a large area of frame |

All three are guide defects that look like generation defects. Before blaming the model,
look at the depth pass.

**The normal pass is not a substitute for depth.** It was tried on s007 where depth
saturates on the ceiling: the composition came back as a doorway view with a different
layout — the model used the normals loosely, not as geometry. Feed depth; use the normal
pass only for inspection or for a dedicated normal-control model.

### Rig results

Eight rigs through the same recipe (blurred control, 0.85, seed `420261113`):

| Rig | Layout held? | Notes |
|---|---|---|
| s001 establishing | yes | curtain, pendants, pass, hero table, waiter all placed |
| s002 pot close-up | yes | steam, signage, stools; divider read as a chimney pot |
| s003 confrontation | yes | standing figure and seated figure in the right seats |
| s004 苏念 close-up | yes | armpit holes fixed by the arm-geometry change |
| s005 window table | yes | cool window light lands where the guide has it |
| s006 street stall | yes | lamp, shutter, folding table, single customer |
| s007 reverse wide | yes | layout holds; ceiling band is dark, reduced by the downward tilt |
| s008 first customer | yes | shutters, stall table, lamp and rain all placed |

## Known gaps, ranked by what they cost

1. **Mannequins are proxy silhouettes.** They carry position and height, not identity.
   Swapping in L1–L4 is the whole point of the `PROXY` collection — replace the objects,
   keep the names or re-place the rigs to match real seated heights.
2. **No steam.** Removed on purpose: opaque wisps read as pipes in a clay render and
   corrupt the eye in every frame they appear. The generator supplies steam.
3. **Back wall is bare** above the wainscot ledge. Harmless in a depth pass — the keyframe
   test filled it with its own sign and poster, which looks right but is not controllable.
   Add one or two framed panels when a shot needs a specific wall.
4. **Signage has no text.** Latin/CJK text needs a font file inside the boundary;
   not worth it until a shot actually calls for a readable sign.

## Next step

The decisive test has been run and passed: the keyframe model follows this set's structure.
The remaining work is per-shot, not architectural.

1. Run the other seven rigs through the same recipe (blurred `_depth_ctrl.png`, strength
   0.85, one seed per shot) and check each one the same way — does the layout hold, or does
   the model re-invent it? A rig where it doesn't hold needs a stronger foreground anchor
   (a table edge, a door frame), not a different prompt.
2. Take two adjacent keyframes of the same rig into Wan 2.2 I2V and confirm the set stays
   consistent across motion. Depth consistency between frames is what decides whether a
   shot can cut against the next one.
3. Only then does the character matter. The proxies already block the frame; finishing L1–L4
   changes what the keyframe model yields, not whether the pipeline works.
