# Geek Mind SVG embodiment scene

The homepage hero mounts `EmbodimentScene`, a square, responsive, silent 15-second loop. The component contains only SVG shapes, paths, text, gradients and filters. No video, screenshot, raster texture, downloaded model or pre-rendered image sequence is used by this animation.

## Editing

- `portraits.ts`: manually drawn curved shells, metallic gradients, sensors, motor details, tires and PiPER arm. Coordinates follow the reference camera. `dogPortrait()` and `armPortrait()` return SVG groups; every path is editable.
- `rig.ts`: articulated reference-view hip, knee and contact anchors. Body rise, upper-shell transforms, lower links and camera framing share the same pose.
- `orbit-rig.ts`: camera and 3D joint calibration against those editable anchors.
- `robots.ts`: procedural dog geometry for the full camera orbit, plus an alternate parametric arm model. Dimensions are scene-relative units. `motor()`, `wheel()`, `armJoint()` and `armLink()` are separate components.
- `REFERENCE-NOTES.md`: reference provenance and the limits of structural calibration.
- `geometry.ts`: lofts, ellipsoids, cylinders, tapered Bézier leg shells, tires, perspective projection, lighting and depth ordering. Analytic SVG ellipses and radial gradients smooth motor housings without dense facets. The output is SVG paths, not WebGL or canvas. Back faces of closed shells are culled. Shared vertices are projected once per frame; adjacent opaque patches with identical paint share SVG paths. Smooth patches use vertex-normal gradients. The machined wheel faces use projected circles and gradients, with distinct inner covers and outer rims.
- `timeline.ts`: `ANIMATION` holds timing and camera settings. `sampleTimeline(seconds)` is deterministic and loops at 15 seconds. Radians control joints, and normalized values control fades and gripper opening.
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
| 5.43–6.43   | Full camera orbit: front → opposite flank → rear → original angle |
| 6.65–7.60   | Wheel pose and tire rotation                                      |
| 7.60–8.65   | Dog crossfades into PiPER                                         |
| 9.00–14.10  | Arm reaches, opens and closes its gripper, returns                |
| 14.10–15.00 | Crossfade to the first pose                                       |

## Visual review

Run `pnpm dev`, then open `/?scene-review&t=0`. The local-only controls allow seeking to the supplied review times. The production build removes this query-driven UI. The component also accepts `fixedTime={9}` for deterministic captures and `debug` for a standalone review tool.

Review composition, contours, color, surface detail, gait, fade order, orbit and loop rhythm against the references. **No SSIM-based acceptance is used.** The current orbit geometry remains less detailed than the curved reference view; an automatic percentage match is neither measured nor claimed.

Build: `pnpm build` (includes TypeScript). Code checks: `pnpm exec oxlint components/embodiment app/page.tsx`.

The animation is a conceptual hardware illustration and does not add or assert robot-runtime support for a particular platform.
