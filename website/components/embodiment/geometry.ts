/** Small, dependency-free vector renderer. Every visible surface is native SVG geometry.
 * Geometry is authored here; no downloaded meshes, raster textures or frames.
 * Coordinates: X forward/back, Y up, Z left/right; units are scene-relative.
 */
export type V3 = [number, number, number];
export type Material = { color: V3; metal?: number; unlit?: boolean };
export type Face = {
  points: V3[];
  material: Material;
  opacity: number;
  normal?: V3;
  cull?: boolean;
  overlay?: boolean;
  depthBias?: number;
  vertexNormals?: V3[];
  strokeWidth?: number;
};
export type Label = {
  origin: V3;
  right: V3;
  up: V3;
  text: string;
  size: number;
  color: string;
  italic?: boolean;
};
export type SmoothSolid = { center: V3; axes: V3[]; material: Material; opacity: number };
export type RadialPanel = {
  center: V3;
  axes: V3[];
  normal: V3;
  kind: "dish" | "cover";
  spin: number;
  opacity: number;
};
export type Model = {
  faces: Face[];
  labels: Label[];
  solids: SmoothSolid[];
  panels: RadialPanel[];
};
export const silver: Material = { color: [187, 194, 200], metal: 0.45 };
export const edge: Material = { color: [147, 155, 163], metal: 0.5 };
export const lightSilver: Material = { color: [204, 210, 214], metal: 0.4 };
export const dark: Material = { color: [30, 33, 35], metal: 0.28 };
export const rubber: Material = { color: [34, 37, 39], metal: 0.02, unlit: true };
export const black: Material = { color: [9, 13, 16], metal: 0.4 };
export const red: Material = { color: [167, 44, 40], metal: 0.1 };
export const add = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const mul = (a: V3, b: number): V3 => [a[0] * b, a[1] * b, a[2] * b];
export const dot = (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a: V3, b: V3): V3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
export const norm = (v: V3): V3 => mul(v, 1 / (Math.hypot(...v) || 1));
export const mix = (a: V3, b: V3, t: number): V3 => add(a, mul(sub(b, a), t));
export const scene = (): Model => ({ faces: [], labels: [], solids: [], panels: [] });
export function face(
  m: Model,
  points: V3[],
  material: Material,
  opacity = 1,
  normal?: V3,
  cull = false,
) {
  m.faces.push({ points, material, opacity, normal, cull });
}
// Cross sections join into closed, smooth-looking shells with controllable taper.
export function loft(
  m: Model,
  rings: V3[][],
  mat: Material,
  opacity = 1,
  smooth = false,
  caps = true,
) {
  const n = rings[0].length;
  const normals = smooth
    ? rings.map((ring, j) =>
        ring.map((_, i) =>
          norm(
            cross(
              sub(rings[Math.min(j + 1, rings.length - 1)][i], rings[Math.max(0, j - 1)][i]),
              sub(ring[(i + 1) % n], ring[(i + n - 1) % n]),
            ),
          ),
        ),
      )
    : undefined;
  for (let j = 0; j < rings.length - 1; j++)
    for (let i = 0; i < n; i++) {
      const k = (i + 1) % n;
      face(
        m,
        [rings[j][i], rings[j + 1][i], rings[j + 1][k], rings[j][k]],
        mat,
        opacity,
        undefined,
        true,
      );
      if (normals)
        m.faces[m.faces.length - 1].vertexNormals = [
          normals[j][i],
          normals[j + 1][i],
          normals[j + 1][k],
          normals[j][k],
        ];
    }
  if (caps) {
    face(m, rings[0], mat, opacity, undefined, true);
    face(m, [...rings[rings.length - 1]].reverse(), mat, opacity, undefined, true);
  }
}
export function ellipsoid(
  m: Model,
  c: V3,
  r: V3,
  mat: Material,
  opacity = 1,
  segments = 24,
  rows = 12,
) {
  const rings: V3[][] = [];
  for (let j = 0; j <= rows; j++) {
    const v = -Math.PI / 2 + (j * Math.PI) / rows;
    rings.push(
      Array.from({ length: segments }, (_, i) => {
        const a = (i * 2 * Math.PI) / segments;
        return [
          c[0] + r[0] * Math.cos(v) * Math.cos(a),
          c[1] + r[1] * Math.sin(v),
          c[2] + r[2] * Math.cos(v) * Math.sin(a),
        ] as V3;
      }),
    );
  }
  loft(m, rings, mat, opacity);
}
/** Analytic silhouette and SVG radial shading avoid faceted motor housings. */
export function smoothEllipsoid(m: Model, c: V3, r: V3, material: Material, opacity = 1) {
  m.solids.push({
    center: c,
    axes: [
      [r[0], 0, 0],
      [0, r[1], 0],
      [0, 0, r[2]],
    ],
    material,
    opacity,
  });
}
/** Circular machined face projected into SVG; no tessellation of flat disks. */
export function radialPanel(
  m: Model,
  center: V3,
  radius: number,
  side: number,
  kind: "dish" | "cover",
  spin = 0,
  opacity = 1,
) {
  m.panels.push({
    center,
    axes: [
      [radius, 0, 0],
      [0, -radius, 0],
    ],
    normal: [0, 0, side],
    kind,
    spin,
    opacity,
  });
}
export function cylinder(
  m: Model,
  a: V3,
  b: V3,
  r: number,
  mat: Material,
  opacity = 1,
  segments = 28,
  endRadius = r,
) {
  const axis = norm(sub(b, a));
  const u = norm(cross(axis, Math.abs(axis[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0]));
  const v = cross(axis, u);
  const profiles =
    Math.hypot(...sub(b, a)) < r * 0.2
      ? [
          [0, 1],
          [1, endRadius / r],
        ]
      : [
          [0, 0.88],
          [0.04, 1],
          [0.96, endRadius / r],
          [1, (endRadius / r) * 0.88],
        ];
  const rings = profiles.map(([t, s]) =>
    Array.from({ length: segments }, (_, i) => {
      const theta = (i * 2 * Math.PI) / segments;
      return add(mix(a, b, t), mul(add(mul(u, Math.cos(theta)), mul(v, Math.sin(theta))), r * s));
    }),
  );
  loft(
    m,
    rings.map((r) => r.reverse()),
    mat,
    opacity,
    profiles.length > 2 && (mat.metal ?? 0) > 0.1,
  );
}
export function box(m: Model, c: V3, size: V3, mat: Material, opacity = 1) {
  const [x, y, z] = size.map((v) => v / 2);
  const v = ([-1, 1] as const).flatMap((a) =>
    [-1, 1].flatMap((b) => [-1, 1].map((d) => add(c, [a * x, b * y, d * z]))),
  );
  for (const ids of [
    [0, 1, 3, 2],
    [4, 6, 7, 5],
    [0, 4, 5, 1],
    [2, 3, 7, 6],
    [0, 2, 6, 4],
    [1, 5, 7, 3],
  ])
    face(
      m,
      ids.map((i) => v[i]),
      mat,
      opacity,
    );
}
/** Curved structural link. Width is in the bending plane; thickness is lateral. */
export function sculptedLink(
  m: Model,
  controls: [V3, V3, V3, V3],
  widths: [number, number, number, number],
  depth: number,
  material: Material,
  inset: Material,
  range: [number, number],
  opacity = 1,
) {
  const samples = 12,
    count = 12;
  const cubic = (v: number[], t: number) =>
    v[0] * (1 - t) ** 3 + 3 * v[1] * (1 - t) ** 2 * t + 3 * v[2] * (1 - t) * t * t + v[3] * t ** 3;
  const rings: V3[][] = [];
  for (let j = 0; j <= samples; j++) {
    const t = j / samples;
    const center: V3 = [0, 1, 2].map((k) =>
      cubic(
        controls.map((p) => p[k]),
        t,
      ),
    ) as V3;
    const tangent = norm(
      add(
        add(
          mul(sub(controls[1], controls[0]), 3 * (1 - t) ** 2),
          mul(sub(controls[2], controls[1]), 6 * (1 - t) * t),
        ),
        mul(sub(controls[3], controls[2]), 3 * t * t),
      ),
    );
    const u = norm([-tangent[1], tangent[0], 0]),
      v = norm(cross(tangent, u));
    const width = cubic(widths, t);
    const span = Math.max(0, Math.min(1, (t - range[0]) / (range[1] - range[0])));
    const band = 0.53 * Math.sin(Math.PI * span);
    // Rounded chamfers and a tapered flat web form the manufactured shell.
    const section = [
      [-1, -0.65],
      [-0.86, -1],
      [-band, -1],
      [band, -1],
      [0.86, -1],
      [1, -0.65],
      [1, 0.65],
      [0.86, 1],
      [band, 1],
      [-band, 1],
      [-0.86, 1],
      [-1, 0.65],
    ];
    rings.push(
      section.map(([a, b]) => add(center, add(mul(u, a * width), mul(v, b * depth)))).reverse(),
    );
  }
  const start = m.faces.length;
  loft(m, rings, material, opacity, true);
  for (let j = 0; j < samples; j++) {
    const t = (j + 0.5) / samples;
    if (t > range[0] + 0.015 && t < range[1] - 0.015) {
      // Reversed ring indices 2 and 8 are the two central web faces.
      m.faces[start + j * count + 2].material = inset;
      m.faces[start + j * count + 8].material = inset;
    }
  }
}

export function link(
  m: Model,
  points: V3[],
  widths: number[],
  thickness: number,
  mat: Material,
  opacity = 1,
) {
  const rings = points.map((p, i) => {
    const direction = norm(
      sub(points[Math.min(i + 1, points.length - 1)], points[Math.max(0, i - 1)]),
    );
    const u = norm([-direction[1], direction[0], 0]);
    return Array.from({ length: 12 }, (_, j) => {
      const a = (j * Math.PI) / 6;
      const round = (n: number) => Math.sign(n) * Math.pow(Math.abs(n), 0.55);
      return add(
        p,
        add(mul(u, round(Math.cos(a)) * widths[i]), [0, 0, round(Math.sin(a)) * thickness]),
      );
    });
  });
  loft(
    m,
    rings.map((r) => r.reverse()),
    mat,
    opacity,
  );
}
export function torus(
  m: Model,
  c: V3,
  radius: number,
  tube: number,
  depth: number,
  mat: Material,
  opacity = 1,
  segments = 40,
) {
  // Wheel axis is Z. An elliptical cross section makes a tire, not a doughnut.
  const rings = Array.from({ length: segments + 1 }, (_, i) => {
    const a = (i * 2 * Math.PI) / segments;
    return Array.from({ length: 12 }, (_, j) => {
      const b = (j * 2 * Math.PI) / 12,
        r = radius + tube * Math.cos(b);
      return add(c, [Math.cos(a) * r, Math.sin(a) * r, Math.sin(b) * depth]);
    });
  });
  loft(m, rings, mat, opacity);
}
export function transform(m: Model, fn: (v: V3) => V3): Model {
  // All model transforms are affine. Normals use the inverse transpose so a
  // stretched wheel keeps correct lighting instead of following point scaling.
  const origin = fn([0, 0, 0]);
  const x = sub(fn([1, 0, 0]), origin),
    y = sub(fn([0, 1, 0]), origin),
    z = sub(fn([0, 0, 1]), origin);
  const nx = cross(y, z),
    ny = cross(z, x),
    nz = cross(x, y),
    sign = Math.sign(dot(x, nx)) || 1;
  const rawNormal = (n: V3) =>
    norm(mul(add(add(mul(nx, n[0]), mul(ny, n[1])), mul(nz, n[2])), sign));
  const normals = new Map<V3, V3>(),
    points = new Map<V3, V3>();
  const normal = (n: V3) => {
    let v = normals.get(n);
    if (!v) {
      v = rawNormal(n);
      normals.set(n, v);
    }
    return v;
  };
  const point = (p: V3) => {
    let v = points.get(p);
    if (!v) {
      v = fn(p);
      points.set(p, v);
    }
    return v;
  };
  return {
    panels: m.panels.map((p) => ({
      ...p,
      center: fn(p.center),
      axes: p.axes.map((a) => sub(fn(add(p.center, a)), fn(p.center))),
      normal: normal(p.normal),
    })),
    solids: m.solids.map((s) => ({
      ...s,
      center: fn(s.center),
      axes: s.axes.map((a) => sub(fn(add(s.center, a)), fn(s.center))),
    })),
    faces: m.faces.map((f) => ({
      ...f,
      points: f.points.map(point),
      normal: f.normal ? normal(f.normal) : undefined,
      vertexNormals: f.vertexNormals?.map(normal),
    })),
    labels: m.labels.map((l) => ({
      ...l,
      origin: fn(l.origin),
      right: sub(fn(add(l.origin, l.right)), fn(l.origin)),
      up: sub(fn(add(l.origin, l.up)), fn(l.origin)),
    })),
  };
}
export function merge(m: Model, n: Model) {
  m.faces.push(...n.faces);
  m.labels.push(...n.labels);
  m.solids.push(...n.solids);
  m.panels.push(...n.panels);
}
export function rotateZ(p: V3, angle: number): V3 {
  const c = Math.cos(angle),
    s = Math.sin(angle);
  return [p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2]];
}
export function rotateY(p: V3, angle: number): V3 {
  const c = Math.cos(angle),
    s = Math.sin(angle);
  return [p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c];
}

export type Camera = {
  yaw: number;
  pitch: number;
  scale: number;
  distance?: number;
  center: [number, number];
  target: V3;
};
export function renderSVG(model: Model, camera: Camera, prefix = "orbit"): string {
  const { yaw, pitch, scale, center, target } = camera;
  const eye: V3 = [
    Math.sin(yaw) * Math.cos(pitch),
    Math.sin(pitch),
    Math.cos(yaw) * Math.cos(pitch),
  ];
  const right = norm(cross([0, 1, 0], eye));
  const up = cross(eye, right);
  const projection = new Map<V3, [number, number, number]>();
  const project = (v: V3): [number, number, number] => {
    const cached = projection.get(v);
    if (cached) return cached;
    const q = sub(v, target);
    const depth = dot(q, eye);
    const perspective = camera.distance ? camera.distance / (camera.distance - depth) : 1;
    const result: [number, number, number] = [
      center[0] + dot(q, right) * scale * perspective,
      center[1] - dot(q, up) * scale * perspective,
      depth,
    ];
    projection.set(v, result);
    return result;
  };
  const key = norm([-3, 7, 5]);
  const fill = norm([4, 2, -3]);
  const half = norm(add(key, eye));
  const shade = (n: V3, material: Material) => {
    const light = 0.64 + 0.34 * Math.max(0, dot(n, key)) + 0.12 * Math.max(0, dot(n, fill));
    const spec = Math.pow(Math.max(0, dot(n, half)), 28) * (material.metal ?? 0) * 65;
    return material.color.map((v) =>
      Math.max(0, Math.min(255, Math.round(material.unlit ? v : v * light + spec))),
    );
  };
  let shadeId = 0;
  const projected: { depth: number; markup: string; path?: string; style?: string }[] = [];
  for (const f of model.faces) {
    if (f.opacity < 0.004) continue;
    let n = (f.normal ??= norm(
      cross(sub(f.points[1], f.points[0]), sub(f.points[2], f.points[0])),
    ));
    // Back-face culling keeps the orbit lightweight. Hand-authored plates are two-sided.
    if (dot(n, eye) < 0) {
      if (f.cull) continue;
      n = mul(n, -1);
    }
    let fillColor = `rgb(${shade(n, f.material).join(",")})`;
    let gradient = "";
    const pts = f.points.map(project);
    const area = pts.reduce((sum, p, i) => {
      const q = pts[(i + 1) % pts.length];
      return sum + p[0] * q[1] - q[0] * p[1];
    }, 0);
    if (f.cull && Math.abs(area) < 0.05) continue;
    if (f.vertexNormals && !f.material.unlit) {
      const colors = f.vertexNormals.map((n) => shade(n, f.material));
      const intensities = colors.map((c) => (c[0] + c[1] + c[2]) / 3);
      const low = Math.min(...intensities),
        high = Math.max(...intensities);
      if (high - low > 3) {
        // Fit a lighting plane in projected space, sharing vertex normals across
        // neighboring patches. The resulting native SVG gradient removes bands.
        const count = pts.length,
          cx = pts.reduce((a, p) => a + p[0], 0) / count,
          cy = pts.reduce((a, p) => a + p[1], 0) / count,
          ci = intensities.reduce((a, v) => a + v, 0) / count;
        let xx = 0,
          yy = 0,
          xy = 0,
          xi = 0,
          yi = 0;
        pts.forEach((p, i) => {
          const x = p[0] - cx,
            y = p[1] - cy,
            v = intensities[i] - ci;
          xx += x * x;
          yy += y * y;
          xy += x * y;
          xi += x * v;
          yi += y * v;
        });
        const det = xx * yy - xy * xy;
        if (Math.abs(det) > 1e-5) {
          const gx = (xi * yy - yi * xy) / det,
            gy = (yi * xx - xi * xy) / det,
            g2 = gx * gx + gy * gy;
          if (g2 > 1e-5) {
            const id = `${prefix}-shade-${shadeId++}`;
            const x1 = cx + (gx * (low - ci)) / g2,
              y1 = cy + (gy * (low - ci)) / g2,
              x2 = cx + (gx * (high - ci)) / g2,
              y2 = cy + (gy * (high - ci)) / g2;
            const a = colors[intensities.indexOf(low)],
              b = colors[intensities.indexOf(high)];
            gradient = `<defs><linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}"><stop stop-color="rgb(${a.join(",")})"/><stop offset="1" stop-color="rgb(${b.join(",")})"/></linearGradient></defs>`;
            fillColor = `url(#${id})`;
          }
        }
      }
    }
    const d =
      pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join("") + "Z";
    projected.push({
      depth:
        (f.overlay ? 100 : 0) + (f.depthBias ?? 0) + pts.reduce((s, p) => s + p[2], 0) / pts.length,
      markup: `${gradient}<path d="${d}" fill="${fillColor}" stroke="${fillColor}" stroke-width="${f.strokeWidth ?? (f.opacity > 0.99 ? 1.05 : 0.35)}" stroke-linejoin="round"${f.opacity < 0.999 ? ` opacity="${f.opacity.toFixed(3)}"` : ""}/>`,
      path: !gradient && f.cull && f.opacity > 0.999 ? d : undefined,
      style:
        !gradient && f.cull && f.opacity > 0.999
          ? `fill="${fillColor}" stroke="${fillColor}" stroke-width="${f.strokeWidth ?? 1.05}" stroke-linejoin="round"`
          : undefined,
    });
  }
  for (let i = 0; i < model.solids.length; i++) {
    const s = model.solids[i];
    if (s.opacity < 0.004) continue;
    const c = project(s.center);
    const k = camera.distance ? camera.distance / (camera.distance - c[2]) : 1;
    const u = s.axes.map((a) => dot(a, right) * scale * k),
      v = s.axes.map((a) => -dot(a, up) * scale * k);
    const xx = u.reduce((t, n) => t + n * n, 0),
      yy = v.reduce((t, n) => t + n * n, 0),
      xy = u.reduce((t, n, j) => t + n * v[j], 0);
    const theta = Math.atan2(2 * xy, xx - yy) / 2;
    const spread = Math.sqrt((xx - yy) ** 2 + 4 * xy * xy);
    const rx = Math.sqrt((xx + yy + spread) / 2),
      ry = Math.sqrt(Math.max(0, (xx + yy - spread) / 2));
    const color = (factor: number) =>
      `rgb(${s.material.color.map((c) => Math.round(Math.min(255, c * factor))).join(",")})`;
    const keyId = `${prefix}-solid-${i}`;
    const fill = s.material.unlit ? color(1) : `url(#${keyId})`;
    const shade = s.material.unlit
      ? ""
      : `<defs><radialGradient id="${keyId}" cx="35%" cy="22%" r="88%"><stop stop-color="${color(1.14)}"/><stop offset=".46" stop-color="${color(1.0)}"/><stop offset=".82" stop-color="${color(0.87)}"/><stop offset="1" stop-color="${color(0.69)}"/></radialGradient></defs>`;
    const zRadius = Math.sqrt(s.axes.reduce((sum, a) => sum + dot(a, eye) ** 2, 0));
    projected.push({
      depth: c[2] + zRadius * 0.55,
      markup: `${shade}<ellipse cx="${c[0]}" cy="${c[1]}" rx="${rx}" ry="${ry}" transform="rotate(${(theta * 180) / Math.PI} ${c[0]} ${c[1]})" fill="${fill}" opacity="${s.opacity}"/>`,
    });
  }
  for (let i = 0; i < model.panels.length; i++) {
    const panel = model.panels[i];
    if (panel.opacity < 0.004 || dot(panel.normal, eye) < 0.025) continue;
    const c = project(panel.center),
      u = project(add(panel.center, panel.axes[0])),
      v = project(add(panel.center, panel.axes[1]));
    const id = `${prefix}-panel-${i}`;
    const matrix = `matrix(${u[0] - c[0]} ${u[1] - c[1]} ${v[0] - c[0]} ${v[1] - c[1]} ${c[0]} ${c[1]})`;
    const defs = `<defs><radialGradient id="${id}-rim" cx=".7" cy=".36" r=".74"><stop stop-color="#939ea6"/><stop offset=".4" stop-color="#b3bfc7"/><stop offset=".7" stop-color="#dce3e7"/><stop offset=".83" stop-color="#c8d2d7"/><stop offset="1" stop-color="#73828c"/></radialGradient><linearGradient id="${id}-cover" x1="0" y1="0" x2="1" y2=".7"><stop stop-color="#e0e6e8"/><stop offset=".5" stop-color="#bec9cf"/><stop offset="1" stop-color="#8f9ba4"/></linearGradient></defs>`;
    const holes = Array.from({ length: 5 }, (_, j) => {
      const a = (j * Math.PI * 2) / 5 - panel.spin;
      return `<circle cx="${Math.cos(a) * 0.75}" cy="${Math.sin(a) * 0.75}" r=".038" fill="#718089"/><circle cx="${Math.cos(a) * 0.75 + 0.01}" cy="${Math.sin(a) * 0.75 - 0.009}" r=".020" fill="#edf1f2"/>`;
    }).join("");
    const art =
      panel.kind === "dish"
        ? `<circle r="1" fill="#67737b"/><circle r=".94" fill="url(#${id}-rim)"/><path d="M.24 -.79C-.55 -.79 -.82 -.11 -.65 .43" fill="none" stroke="#e4eaed" stroke-width=".035" opacity=".8"/><circle cx="${Math.cos(-Math.PI / 2 + panel.spin) * 0.64}" cy="${-Math.sin(-Math.PI / 2 + panel.spin) * 0.64}" r=".066" fill="#1b242b"/>`
        : `<circle r=".97" fill="#6d7a82"/><circle r=".91" fill="url(#${id}-cover)"/>${holes}`;
    projected.push({
      depth: c[2] + 0.003,
      markup: `${defs}<g transform="${matrix}" opacity="${panel.opacity}">${art}</g>`,
    });
  }
  for (const l of model.labels) {
    const n = norm(cross(l.right, l.up));
    if (dot(n, eye) < 0.03) continue;
    const a = project(l.origin),
      b = project(add(l.origin, l.right)),
      c = project(add(l.origin, l.up));
    const text = l.text.replaceAll("&", "&amp;").replaceAll("<", "&lt;");
    projected.push({
      depth: 100 + a[2],
      markup: `<text transform="matrix(${(b[0] - a[0]).toFixed(4)} ${(b[1] - a[1]).toFixed(4)} ${(a[0] - c[0]).toFixed(4)} ${(a[1] - c[1]).toFixed(4)} ${a[0].toFixed(2)} ${a[1].toFixed(2)})" font-family="Arial,sans-serif" font-size="${l.size}" font-weight="700" font-style="${l.italic ? "italic" : "normal"}" fill="${l.color}" text-anchor="middle">${text}</text>`,
    });
  }
  projected.sort((a, b) => a.depth - b.depth);
  // Adjacent opaque faces with identical paint can share one compound path.
  // Keep depth order and never merge two-sided or transparent faces.
  const output: string[] = [];
  let path = "",
    style = "";
  const flush = () => {
    if (path) output.push(`<path d="${path}" ${style}/>`);
    path = "";
    style = "";
  };
  for (const item of projected) {
    if (item.path && item.style) {
      if (style && style !== item.style) flush();
      style = item.style;
      path += item.path;
    } else {
      flush();
      output.push(item.markup);
    }
  }
  flush();
  return output.join("");
}
