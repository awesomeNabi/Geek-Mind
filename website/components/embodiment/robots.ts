import { ORBIT_RIG } from "./orbit-rig";
import {
  add,
  black,
  box,
  cylinder,
  dark,
  edge,
  ellipsoid,
  smoothEllipsoid,
  radialPanel,
  face,
  lightSilver,
  link,
  sculptedLink,
  loft,
  merge,
  mix,
  red,
  rotateY,
  rotateZ,
  rubber,
  scene,
  silver,
  torus,
  transform,
  type Material,
  type Model,
  type V3,
} from "./geometry";

const seam: Material = { color: [78, 85, 92], metal: 0.15 };
const glass: Material = { color: [12, 23, 29], metal: 0.9 };
const white: Material = { color: [233, 238, 235], unlit: true };
function bolt(m: Model, p: V3, side = 1, opacity = 1, r = 0.025) {
  // Subpixel bevels needlessly multiply SVG nodes during the orbit.
  for (const [radius, depth, material] of [
    [r, 0.012, seam],
    [r * 0.47, 0.017, lightSilver],
  ] as const) {
    face(
      m,
      Array.from({ length: 8 }, (_, i) =>
        add(p, [
          Math.cos((i * Math.PI) / 4) * radius,
          Math.sin((i * Math.PI) / 4) * radius,
          side * depth,
        ]),
      ),
      material,
      opacity,
      [0, 0, side],
    );
  }
}
function motor(m: Model, p: V3, side: number, opacity = 1) {
  const at = (z: number) => add(p, [0, 0, z * side]);
  cylinder(m, at(-0.06), at(0.26), 0.285, silver, opacity, 32);
  cylinder(m, at(0.09), at(0.105), 0.288, seam, opacity, 32);
  cylinder(m, at(0.12), at(0.15), 0.29, lightSilver, opacity, 32);
  smoothEllipsoid(m, at(0.3), [0.27, 0.255, 0.13], silver, opacity);
  for (const a of [-0.7, 0.9, 2.6, 4.1])
    bolt(m, add(at(0.215), [Math.cos(a) * 0.266, Math.sin(a) * 0.266, 0]), side, opacity, 0.015);
}
function wheel(m: Model, p: V3, side: number, spin: number, opacity: number) {
  if (opacity < 0.004) return;
  const c = add(p, [0, 0, side * 0.14]);
  torus(m, c, 0.225, 0.092, 0.117, rubber, opacity, 36);
  // Distinct inside motor cover and outside dished rim, projected as native
  // SVG circles and gradients so the reflective surface stays continuous.
  radialPanel(m, add(c, [0, 0, side * 0.125]), 0.205, side, "dish", spin, opacity);
  radialPanel(m, add(p, [0, 0, -side * 0.025]), 0.175, -side, "cover", spin, opacity);
  // Tread grooves are vector ribbons wrapping the tire crown.
  for (let j = 0; j < 28; j++)
    for (const sideBand of [-1, 1]) {
      const a = (j * Math.PI) / 14 + spin;
      const points = [0, 0.4, 0.8, 1].map((t) => {
        const b = a + t * 0.065 * sideBand;
        return [
          c[0] + Math.cos(b) * (0.225 + 0.092 * Math.sqrt(1 - ((t * 0.095) / 0.117) ** 2) + 0.0005),
          c[1] + Math.sin(b) * (0.225 + 0.092 * Math.sqrt(1 - ((t * 0.095) / 0.117) ** 2) + 0.0005),
          c[2] + t * 0.095 * sideBand,
        ] as V3;
      });
      for (let k = 0; k < 3; k++) {
        face(
          m,
          [
            points[k],
            points[k + 1],
            add(points[k + 1], [-0.006 * Math.sin(a), 0.006 * Math.cos(a), 0]),
            add(points[k], [-0.006 * Math.sin(a), 0.006 * Math.cos(a), 0]),
          ],
          { color: [20, 24, 26], unlit: true },
          opacity,
          [Math.cos(a), Math.sin(a), 0],
          true,
        );
        m.faces[m.faces.length - 1].strokeWidth = 0.35;
      }
    }
  cylinder(
    m,
    add(p, [0, 0, -0.01 * side]),
    add(p, [0, 0, 0.07 * side]),
    0.165,
    silver,
    opacity,
    24,
  );
}

export type DogPose = {
  morph: number;
  step: number;
  footOpacity: number;
  wheelOpacity: number;
  spin: number;
  bodyLift: number;
};
export function buildDog(pose: DogPose): Model {
  const m = scene();
  // Torso is lofted from measured silhouette sections, with a raised back and
  // sloping sensor face. The values are editable independently of the timeline.
  const sections = [
    [-1.57, 2.13, 0.28, 0.23],
    [-1.48, 2.19, 0.3, 0.31],
    [-1.29, 2.25, 0.36, 0.38],
    [-1.04, 2.28, 0.39, 0.36],
    [-0.76, 2.3, 0.39, 0.39],
    [-0.4, 2.28, 0.4, 0.45],
    [0.1, 2.29, 0.41, 0.46],
    [0.58, 2.31, 0.4, 0.46],
    [0.95, 2.3, 0.36, 0.42],
    [1.22, 2.28, 0.34, 0.36],
    [1.38, 2.27, 0.31, 0.32],
    [1.43, 2.27, 0.3, 0.29],
  ];
  const rings = sections.map(([x, y, h, w]) =>
    Array.from({ length: 32 }, (_, i) => {
      const a = (i * Math.PI) / 16;
      const squircle = (v: number) => Math.sign(v) * Math.pow(Math.abs(v), x < -1.18 ? 0.28 : 0.42);
      return [x, y + squircle(Math.cos(a)) * h, squircle(Math.sin(a)) * w] as V3;
    }),
  );
  loft(
    m,
    rings.map((r) => r.reverse()),
    silver,
    1,
    true,
  );
  // Recessed belly, longitudinal deck strip, hatch, lift handle and fasteners.
  box(m, [0, 1.94, 0], [1.85, 0.09, 0.44], dark);
  face(
    m,
    [
      [-0.35, 2.697, -0.17],
      [0.84, 2.681, -0.17],
      [0.93, 2.683, 0.17],
      [-0.36, 2.697, 0.17],
    ],
    edge,
  );
  for (const x of [-0.72, 0.97]) {
    link(
      m,
      [
        [x - 0.15, 2.63, -0.24],
        [x - 0.15, 2.72, -0.16],
        [x + 0.12, 2.74, -0.16],
        [x + 0.16, 2.66, -0.24],
      ],
      [0.025, 0.025, 0.025, 0.025],
      0.026,
      edge,
    );
  }
  for (const s of [-1, 1]) {
    const z = s * 0.464;
    if (s > 0) {
      face(
        m,
        [
          [-0.28, 2.12, z],
          [0.91, 2.12, z],
          [0.91, 2.48, z],
          [-0.28, 2.48, z],
        ],
        edge,
      );
      face(
        m,
        [
          [-0.26, 2.13, z + s * 0.003],
          [0.895, 2.13, z + s * 0.003],
          [0.895, 2.465, z + s * 0.003],
          [-0.26, 2.465, z + s * 0.003],
        ],
        silver,
      );
      for (const x of [0.23, 0.66]) {
        box(m, [x, 2.26, z], [0.13, 0.23, 0.028], dark);
        box(m, [x - 0.006, 2.26, z + s * 0.019], [0.08, 0.17, 0.007], seam);
        box(m, [x + 0.028, 2.26, z + s * 0.024], [0.012, 0.16, 0.008], lightSilver);
      }
      box(m, [0.445, 2.393, z + s * 0.017], [0.078, 0.13, 0.035], edge);
      const plate = (x: number, y: number, w: number, h: number, material: Material) => {
        face(
          m,
          [
            [x - w / 2, y - h / 2, z + s * 0.027],
            [x + w / 2, y - h / 2, z + s * 0.027],
            [x + w / 2, y + h / 2, z + s * 0.027],
            [x - w / 2, y + h / 2, z + s * 0.027],
          ],
          material,
          1,
          [0, 0, s],
          true,
        );
        m.faces[m.faces.length - 1].overlay = true;
      };
      for (const x of [0.23, 0.66]) {
        plate(x, 2.26, 0.14, 0.25, edge);
        plate(x, 2.26, 0.1, 0.21, dark);
        plate(x - 0.025, 2.265, 0.013, 0.18, lightSilver);
      }
      plate(0.445, 2.39, 0.07, 0.12, edge);
      for (let j = 0; j < 4; j++)
        plate(0.445, 2.15 + j * 0.033, 0.012, 0.017, { color: [151, 181, 137], unlit: true });

      for (let j = 0; j < 4; j++)
        box(m, [0.445, 2.15 + j * 0.033, z + s * 0.022], [0.012, 0.017, 0.008], {
          color: [116, 152, 105],
          unlit: true,
        });
    }
    m.labels.push({
      origin: [0.34, s > 0 ? 2.46 : 2.32, z + s * 0.015],
      right: [s * 0.01, 0, 0],
      up: [0, 0.01, 0],
      size: s > 0 ? 15 : 26,
      italic: s < 0,
      text: s > 0 ? "UNITREE" : "Go2",
      color: "#f4f6f5",
    });
    for (const x of [-0.28, 0.9])
      for (const y of [2.13, 2.455]) bolt(m, [x, y, z + s * 0.018], s, 1, 0.012);
  }
  // Front vision stack: camera, depth aperture and the protected lower LiDAR.
  const frontX = -1.585;
  face(
    m,
    [
      [frontX, 1.9, -0.135],
      [frontX, 1.9, 0.135],
      [frontX, 2.45, 0.135],
      [frontX, 2.45, -0.135],
    ],
    dark,
  );
  for (const [y, r] of [
    [2.34, 0.086],
    [2.08, 0.052],
  ]) {
    cylinder(m, [frontX - 0.007, y, 0], [frontX - 0.032, y, 0], r, edge, 1, 28);
    cylinder(m, [frontX - 0.034, y, 0], [frontX - 0.037, y, 0], r * 0.78, glass, 1, 28);
    ellipsoid(m, [frontX - 0.041, y + 0.023, -0.021], [0.006, 0.014, 0.014], white, 1, 10, 6);
  }
  box(m, [-1.612, 2.205, 0], [0.005, 0.014, 0.1], white);
  ellipsoid(m, [-1.365, 1.8, 0], [0.253, 0.235, 0.31], black, 1, 24, 12);
  cylinder(m, [-1.36, 1.74, 0], [-1.36, 1.86, 0], 0.245, glass, 1, 24);
  for (const z of [-0.265, -0.13, 0, 0.13, 0.265])
    link(
      m,
      [
        [-1.52, 1.91, z],
        [-1.57, 1.75, z],
        [-1.5, 1.62, z],
        [-1.29, 1.62, z],
      ],
      [0.021, 0.023, 0.025, 0.02],
      0.019,
      dark,
    );
  for (const s of [-1, 1])
    for (let j = 0; j < 5; j++) {
      face(
        m,
        [
          [-1.45 + j * 0.006, 2.32 + j * 0.033, s * 0.328],
          [-1.31 + j * 0.006, 2.35 + j * 0.033, s * 0.328],
          [-1.31 + j * 0.006, 2.365 + j * 0.033, s * 0.328],
          [-1.45 + j * 0.006, 2.335 + j * 0.033, s * 0.328],
        ],
        white,
        1,
        [0, 0, s],
        true,
      );
      m.faces[m.faces.length - 1].depthBias = 0.025;
    }
  // Open honeycomb rear panel, visible when the camera passes the tail.
  for (let row = 0; row < 7; row++)
    for (let col = 0; col < 5; col++) {
      const y = 2.02 + row * 0.082,
        z = (col - 2) * 0.093 + (row % 2) * 0.0465;
      if (Math.abs(z) > 0.23 || ((row === 0 || row === 6) && Math.abs(z) > 0.16)) continue;
      for (const [radius, x, material] of [
        [0.05, 1.446, edge],
        [0.036, 1.45, black],
      ] as const) {
        face(
          m,
          Array.from(
            { length: 6 },
            (_, i) =>
              [
                x,
                y + Math.sin((i * Math.PI) / 3) * radius,
                z + Math.cos((i * Math.PI) / 3) * radius,
              ] as V3,
          ),
          material,
          1,
          [1, 0, 0],
          true,
        );
        m.faces[m.faces.length - 1].overlay = true;
      }
    }
  const body = transform(m, (p) => add(p, [0, ORBIT_RIG.bodyRise, 0]));
  m.faces = body.faces;
  m.labels = body.labels;
  m.solids = body.solids;
  m.panels = body.panels;
  for (const side of [-1, 1])
    for (const front of [true, false]) {
      const hip: V3 = [front ? -1.01 : 1.11, ORBIT_RIG.hipY, side * 0.43];
      const gait = pose.step * (front ? 1 : -1) * side;
      const knee: V3 = [
        (front ? ORBIT_RIG.kneeFrontX : ORBIT_RIG.kneeRearX) + gait * 0.11,
        ORBIT_RIG.kneeY + Math.max(0, gait) * 0.06,
        side * ORBIT_RIG.kneeZ,
      ];
      smoothEllipsoid(m, add(hip, [0, 0.02, side * 0.045]), [0.325, 0.325, 0.09], black);
      motor(m, hip, side);
      const leg = scene();
      sculptedLink(
        leg,
        [
          add(hip, [0.12, -0.06, side * 0.29]),
          add(hip, [0.4, -0.32, side * 0.32]),
          add(knee, [0.05, 0.32, -side * 0.015]),
          knee,
        ],
        [0.18, 0.155, 0.095, 0.062],
        0.058,
        silver,
        { color: [99, 111, 119], metal: 0.15 },
        [0.64, 0.95],
      );
      cylinder(leg, add(knee, [0, 0, -0.072]), add(knee, [0, 0, 0.072]), 0.061, edge, 1, 20);
      bolt(leg, add(knee, [0, 0, side * 0.075]), side, 1, 0.028);
      merge(m, leg);
      const foot: V3 = [hip[0] - 0.13 - gait * 0.2, 0.13 + Math.max(0, gait) * 0.19, side * 0.77];
      if (pose.footOpacity > 0.004) {
        const o = pose.footOpacity;
        const mid = mix(knee, foot, 0.56);
        link(
          m,
          [
            knee,
            add(mix(knee, foot, 0.22), [0.015, 0, 0]),
            add(mid, [-0.048, 0, 0]),
            add(foot, [0.01, 0.16, 0]),
            foot,
          ],
          [0.05, 0.063, 0.045, 0.052, 0.084],
          0.047,
          lightSilver,
          o,
        );
        link(
          m,
          [
            add(knee, [0, -0.018, -side * 0.046]),
            add(mix(knee, foot, 0.28), [-0.027, 0.017, -side * 0.046]),
            add(mid, [-0.056, 0.02, -side * 0.046]),
          ],
          [0.03, 0.03, 0.012],
          0.011,
          edge,
          o,
        );
        ellipsoid(m, add(foot, [0, -0.017, 0]), [0.088, 0.08, 0.072], rubber, o, 20, 10);
        for (const dx of [-0.04, 0.04])
          bolt(m, add(foot, [dx, 0.104, side * 0.05]), side, o, 0.013);
      }
      if (pose.wheelOpacity > 0.004) {
        const o = pose.wheelOpacity;
        const w: V3 = [
          front ? ORBIT_RIG.wheelFrontX : ORBIT_RIG.wheelRearX,
          0.42,
          side * ORBIT_RIG.wheelZ,
        ];
        sculptedLink(
          m,
          [knee, add(knee, [-0.19, -0.27, side * 0.035]), add(w, [0.08, 0.36, -side * 0.01]), w],
          [0.062, 0.045, 0.05, 0.125],
          0.044,
          lightSilver,
          { color: [112, 124, 132], metal: 0.2 },
          [0.13, 0.86],
          o,
        );
        const wheelPart = scene();
        wheel(wheelPart, w, side, pose.spin, o);
        merge(
          m,
          transform(wheelPart, (p) => [
            w[0] + (p[0] - w[0]) * 1.35,
            w[1] + (p[1] - w[1]) * 1.35,
            w[2] + (p[2] - w[2]) * 1.2,
          ]),
        );
      }
    }
  return transform(m, (p) => add(p, [0, pose.bodyLift, 0]));
}

function armJoint(m: Model, p: V3, r: number, depth: number, accent = true) {
  cylinder(m, add(p, [0, 0, -depth / 2]), add(p, [0, 0, depth / 2]), r, dark, 1, 36);
  for (const s of [-1, 1]) {
    const z = p[2] + s * (depth / 2 + 0.015);
    cylinder(m, [p[0], p[1], z - s * 0.02], [p[0], p[1], z], r * 1.015, edge, 1, 36);
    cylinder(m, [p[0], p[1], z + s * 0.004], [p[0], p[1], z + s * 0.017], r * 0.88, dark, 1, 36);
    cylinder(
      m,
      [p[0], p[1], z + s * 0.019],
      [p[0], p[1], z + s * 0.023],
      r * 0.67,
      { color: [47, 49, 50], metal: 0.3 },
      1,
      32,
    );
    if (accent) {
      cylinder(m, [p[0], p[1], z + s * 0.024], [p[0], p[1], z + s * 0.025], r * 0.4, red, 1, 32);
      cylinder(m, [p[0], p[1], z + s * 0.026], [p[0], p[1], z + s * 0.027], r * 0.355, dark, 1, 32);
      m.labels.push({
        origin: [p[0], p[1] + r * 0.48, z + s * 0.03],
        right: [s * 0.004, 0, 0],
        up: [0, 0.004, 0],
        size: 7,
        text: "AGILE·X",
        color: "#b7b7b7",
      });
    }
    for (const a of [0.6, 2.7, 4.6])
      bolt(
        m,
        [p[0] + Math.cos(a) * r * 0.91, p[1] + Math.sin(a) * r * 0.91, z + s * 0.006],
        s,
        1,
        0.013,
      );
  }
}
function armLink(m: Model, a: V3, b: V3, w: number, label: string) {
  const v: V3 = [b[0] - a[0], b[1] - a[1], 0],
    len = Math.hypot(...v),
    angle = Math.atan2(v[1], v[0]);
  const part = scene();
  // Extruded, chamfered aluminum channel with a recessed central web.
  link(
    part,
    [
      [0, 0, 0],
      [0.21, 0, 0],
      [len - 0.24, 0, 0],
      [len, 0, 0],
    ],
    [w * 1.05, w * 0.71, w * 0.7, w * 0.97],
    0.105,
    edge,
  );
  for (const s of [-1, 1]) {
    face(
      part,
      [
        [0.18, -w * 0.72, s * 0.106],
        [len - 0.21, -w * 0.72, s * 0.106],
        [len - 0.25, w * 0.71, s * 0.106],
        [0.24, w * 0.71, s * 0.106],
      ],
      silver,
    );
    face(
      part,
      [
        [0.31, -w * 0.36, s * 0.108],
        [len - 0.36, -w * 0.36, s * 0.108],
        [len - 0.36, w * 0.29, s * 0.108],
        [0.31, w * 0.29, s * 0.108],
      ],
      dark,
    );
    part.labels.push({
      origin: [len / 2, -0.02, s * 0.111],
      right: [s * 0.006, 0, 0],
      up: [0, 0.006, 0],
      size: 13,
      text: label,
      color: "#dedede",
    });
  }
  merge(
    m,
    transform(part, (p) => add(a, rotateZ(p, angle))),
  );
}
export type ArmPose = { shoulder: number; elbow: number; wrist: number; grip: number; yaw: number };
export function buildArm(pose: ArmPose): Model {
  const m = scene();
  box(m, [0, 0.025, 0], [0.77, 0.05, 0.66], dark);
  for (const x of [-0.31, 0.31])
    for (const z of [-0.25, 0.25]) cylinder(m, [x, 0.053, z], [x, 0.058, z], 0.032, black, 1, 12);
  cylinder(m, [0, 0.075, 0], [0, 0.61, 0], 0.275, dark, 1, 40, 0.25);
  cylinder(m, [0, 0.6, 0], [0, 0.66, 0], 0.27, black, 1, 40);
  const root: V3 = [0, 0.75, 0];
  const elbow = add(root, rotateZ([1.42, 0, 0], pose.shoulder));
  const wrist = add(elbow, rotateZ([1.27, 0, 0], pose.shoulder + pose.elbow));
  armLink(m, root, elbow, 0.18, "AGILE X");
  armLink(m, elbow, wrist, 0.15, "PiPER");
  armJoint(m, root, 0.235, 0.38);
  armJoint(m, elbow, 0.215, 0.34);
  armJoint(m, wrist, 0.185, 0.31, false);
  const hand = scene();
  cylinder(hand, [0, 0, 0], [0.28, 0, 0], 0.165, dark, 1, 32);
  cylinder(hand, [0.26, 0, 0], [0.3, 0, 0], 0.17, seam, 1, 32);
  cylinder(hand, [0.29, 0, 0], [0.48, 0, 0], 0.148, dark, 1, 32);
  // Vertical wrist motor and sensor cap.
  cylinder(hand, [0.13, 0.035, 0], [0.13, 0.35, 0], 0.172, dark, 1, 32);
  cylinder(hand, [0.13, 0.34, 0], [0.13, 0.37, 0], 0.174, edge, 1, 32);
  for (const y of [0.08, -0.08]) bolt(hand, [0.34, y, 0.132], 1, 1, 0.015);
  box(hand, [0.5, 0, 0], [0.1, 0.22, 0.3], dark);
  const opening = 0.045 + pose.grip * 0.09;
  for (const side of [-1, 1]) {
    const z = side * (0.13 + opening);
    link(
      hand,
      [
        [0.49, side * 0.015, side * 0.105],
        [0.64, -0.025, z],
        [0.83, -0.075, z],
        [0.92, -0.055, side * opening],
      ],
      [0.065, 0.055, 0.045, 0.034],
      0.039,
      edge,
    );
    link(
      hand,
      [
        [0.57, 0.008, side * 0.11],
        [0.68, -0.033, side * (0.12 + opening)],
        [0.85, -0.063, side * opening],
      ],
      [0.025, 0.02, 0.022],
      0.021,
      dark,
    );
    box(hand, [0.865, -0.07, side * (opening + 0.015)], [0.115, 0.06, 0.018], rubber);
    bolt(hand, [0.57, 0.01, z + side * 0.038], side, 1, 0.015);
  }
  const handAngle = pose.shoulder + pose.elbow + pose.wrist;
  merge(
    m,
    transform(hand, (p) => add(wrist, rotateZ(p, handAngle))),
  );
  return transform(m, (p) => rotateY(p, pose.yaw));
}
