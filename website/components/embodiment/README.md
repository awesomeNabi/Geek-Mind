# Geek Mind SVG embodiment scene

The homepage hero mounts `EmbodimentScene`, a square, responsive, silent 24-second loop: legged Go2 → wheeled Go2 → Ranger mobile base → PiPER arm. The component contains only SVG shapes, paths, text, gradients and filters. No video, screenshot, raster texture, downloaded model or pre-rendered image sequence is used by this animation.

## Editing

- `portraits.ts`: the original detailed silver dog and PiPER artwork, used throughout the active loop. The dog retains its curved shells, sensors, panel lines, joint caps and UNITREE marking.
- `ranger.ts`: the fixed-view Ranger illustration, with silver body panels, a dark rail deck, underbody battery, suspension struts and four independently drawn steering wheels. `rangerBody()` is identical in every frame; only wheel projection, wheel rotation and whole-model translation change.
- `rig.ts`: articulated reference-view anchors and the whole-illustration presentation transform. The latter uses only rotation and translation, preserving all distances and proportions.
- `orbit-rig.ts`, `robots.ts` and `geometry.ts`: retained procedural 3D references, not rendered by the active showcase. Pose types are imported as types only.
- `REFERENCE-NOTES.md`: reference provenance and the limits of structural calibration.
- `timeline.ts`: `ANIMATION` holds timing settings. `sampleTimeline(seconds)` is deterministic and loops at 24 seconds. The four-second presentation freezes the dog pose and applies at most ±2.2° of rotation and ±5 SVG units of translation in the screen plane. Ranger steers its wheels, travels 34 SVG units sideways, then returns and straightens. Neither model simulates a 360° camera orbit.
- `EmbodimentScene.tsx`: playback, SVG masks, crossfades, pause control, viewport visibility, reduced-motion support and frame scheduling.
- `embodiment.css`: 1:1 layout and typography. The hero uses two columns on desktop and stacks below the copy on screens 800 px or narrower.

The source clip is observed locally, never read by the website. The referenced arm image is likewise not bundled.

## Timeline

| Seconds     | Action                                                            |
| ----------- | ----------------------------------------------------------------- |
| 0–1.65      | Four-legged reference pose                                        |
| 1.65–3.10   | Alternating leg movement                                          |
| 3.15–4.10   | Lower legs fade out                                               |
| 4.10–5.10   | Wheel legs fade in                                                |
| 5.40–9.40   | Gentle whole-illustration turn with smooth entry and exit         |
| 9.40–10.60  | Hold wheeled pose                                                |
| 10.60–11.65 | Wheeled dog crossfades into Ranger                                |
| 12.10–12.80 | Four Ranger wheels steer together                                |
| 12.85–14.15 | Rigid Ranger chassis travels sideways                             |
| 14.45–16.20 | Chassis returns and wheels straighten                             |
| 16.60–17.65 | Ranger crossfades into PiPER                                      |
| 18.00–23.00 | Arm reaches, opens and closes its gripper, returns                 |
| 23.10–24.00 | Crossfade to the first pose                                       |

## Visual review

Run `pnpm dev`, then open `/?scene-review&t=0`. The local-only controls allow seeking to the supplied review times. The production build removes this query-driven UI. The component also accepts `fixedTime={9}` for deterministic captures and `debug` for a standalone review tool.

Review composition, contours, color, surface detail, gait, fade order, presentation motion and loop rhythm against the references. **No SSIM-based acceptance is used.** The original curved reference portrait stays on screen throughout the dog stages. Because this is fixed-view artwork, the approved presentation uses a small rigid turn rather than fabricating other viewpoints. The leg rig still articulates during stepping and the wheel transition. This is an illustration, not a CAD model or a physical simulator.

Build: `pnpm build` (includes TypeScript). Code checks: `pnpm exec oxlint components/embodiment app/page.tsx`.

Regression checks: `node scripts/check-scene.mjs` samples 97 dog presentation positions and all 577 frames of the 24-second loop. It verifies unchanged dog artwork and joint distances, a rigid Ranger chassis with four wheel assemblies, bounded travel and return, finite SVG, continuous crossfades and stage order. Check full framing in the browser at the review keyframes. No generated screenshots or temporary compilation output are checked in.

The animation is a conceptual hardware illustration and does not add or assert robot-runtime support for a particular platform.
