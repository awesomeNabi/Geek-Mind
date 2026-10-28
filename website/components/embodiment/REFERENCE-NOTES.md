# Reference and reconstruction notes

The displayed scene is authored as SVG paths, geometric primitives, gradients and filters. The supplied video and images are used for observation and visual review; they are not embedded in the scene. No OBJ/STL meshes are imported into the website.

## Visual references

- User-provided 7.6-second recording, with the original video identified as [YouTube reference](https://www.youtube.com/watch?v=w9JAPJ8CXz4).
- User-provided PiPER arm image, used to draw the arm casing, joints, labels and gripper.
- User-provided Geek Mind homepage image, used to place the square scene in the hero's right column.
- [AgileX Ranger official product page](https://global.agilex.ai/products/ranger), requested by the project owner and inspected on 2026-10-28. Its three-quarter and side product photos guide the silver body, dark mounting deck and rails, underbody battery, coil suspension, tires, rims and side markings. The product's four-wheel steering and lateral movement inform the added motion. The photos remain references and are not bundled with the animation; no manufacturer CAD or mesh is imported. The fixed-view SVG is an illustration, not a dimensionally calibrated simulation, and it does not assert Ranger integration in the project's robot runtime.

## Structural cross-check

[Unitree's official Go2-W description](https://github.com/unitreerobotics/unitree_mujoco/blob/1eb6642e3f3fdfb7fb13a9794fd6a2dd93ea0e7d/unitree_robots/go2w/go2w.xml), pinned to commit `1eb6642e3f3fdfb7fb13a9794fd6a2dd93ea0e7d`, was inspected as a dimensional reference:

- Front/rear hip origins are at ±0.1934 m along the body axis, giving a 0.3868 m span.
- Thigh-to-calf joint offset: 0.213 m.
- Calf-to-wheel joint offset: 0.2264 m.
- Hip-to-thigh lateral offset: 0.0955 m.

These values help check the reconstruction's proportions. The current SVG still uses adjustable illustration coordinates and camera calibration; the simulation description is not treated as proof that the reference video's camera, pose or cosmetic surfaces are identical. A constrained calibration was investigated locally, but not adopted because it worsened the observed joint alignment.

## Visual acceptance

No SSIM score or pixel-similarity percentage is used. Review covers contours, material appearance, occlusion, body pose, motion order, timing, transitions and the square crop. Passing TypeScript/build checks or matching joint locations does not establish 98% visual fidelity.
