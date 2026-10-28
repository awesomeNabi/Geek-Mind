/** Fixed-view Ranger illustration, drawn from AgileX's official product photos.
 * The deck stays rigid; the four wheel assemblies steer about their own axes.
 * Reference: https://global.agilex.ai/products/ranger
 */
export type RangerPose = { steer: number; roll: number };
type Point = [number, number];

export function rangerDefs(id: string) {
  return `<defs>
    <linearGradient id="${id}-body" x1="0" y1="0" x2=".25" y2="1"><stop stop-color="#fbfcfc"/><stop offset=".44" stop-color="#e2e7e9"/><stop offset="1" stop-color="#b5bec4"/></linearGradient>
    <linearGradient id="${id}-front" x1="0" y1="0" x2="1" y2=".4"><stop stop-color="#b1bbc2"/><stop offset=".17" stop-color="#e8edef"/><stop offset=".68" stop-color="#d7dde1"/><stop offset="1" stop-color="#f2f4f5"/></linearGradient>
    <linearGradient id="${id}-deck" x1="0" y1="0" x2=".7" y2="1"><stop stop-color="#727b80"/><stop offset=".45" stop-color="#4b5359"/><stop offset="1" stop-color="#252e33"/></linearGradient>
    <linearGradient id="${id}-bumper" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#4b5357"/><stop offset=".45" stop-color="#242b30"/><stop offset="1" stop-color="#151b1e"/></linearGradient>
    <linearGradient id="${id}-battery" x1="0" y1="0" x2="1" y2=".4"><stop stop-color="#444c51"/><stop offset=".65" stop-color="#2c3338"/><stop offset="1" stop-color="#171e22"/></linearGradient>
    <linearGradient id="${id}-tire" x1="0" y1=".15" x2="1" y2=".8"><stop stop-color="#4e5559"/><stop offset=".35" stop-color="#32393d"/><stop offset=".75" stop-color="#161d21"/><stop offset="1" stop-color="#293136"/></linearGradient>
    <radialGradient id="${id}-rim" cx=".35" cy=".25" r=".8"><stop stop-color="#e4e9eb"/><stop offset=".33" stop-color="#bcc7cd"/><stop offset=".65" stop-color="#77858d"/><stop offset=".83" stop-color="#d5dde0"/><stop offset="1" stop-color="#65727b"/></radialGradient>
    <linearGradient id="${id}-strut"><stop stop-color="#191f23"/><stop offset=".36" stop-color="#657078"/><stop offset=".55" stop-color="#263037"/><stop offset="1" stop-color="#10171b"/></linearGradient>
  </defs>`;
}

const point = (p: Point) => `${p[0].toFixed(3)} ${p[1].toFixed(3)}`;
function ellipse(cx: number, cy: number, r: number, ux: number, uy: number) {
  const k = 0.55228475;
  const p = (x: number, y: number): Point => [cx + r * ux * x, cy + r * (uy * x + y)];
  return `M${point(p(1, 0))}C${point(p(1, k))} ${point(p(k, 1))} ${point(p(0, 1))}C${point(p(-k, 1))} ${point(p(-1, k))} ${point(p(-1, 0))}C${point(p(-1, -k))} ${point(p(-k, -1))} ${point(p(0, -1))}C${point(p(k, -1))} ${point(p(1, -k))} ${point(p(1, 0))}Z`;
}

function bolt(x: number, y: number, radius = 1.7) {
  return `<circle cx="${x}" cy="${y}" r="${radius}" fill="#74828b"/><circle cx="${x - .25}" cy="${y - .35}" r="${radius * .55}" fill="#e6ecee"/>`;
}

function wheel(id: string, x: number, y: number, radius: number, mountY: number, pose: RangerPose, far = false) {
  // A circular wheel is projected with a fixed vertical axis and a rotating
  // horizontal axis. Steering changes its view, never the body proportions.
  const yaw = pose.steer * .75, c = Math.cos(yaw), s = Math.sin(yaw);
  const ux = .72 * c + .62 * s, uy = -.18 * c + .32 * s;
  const nx = -.72 * s + .62 * c, ny = .18 * s + .32 * c;
  const depth = radius * .4;
  const front: Point = [x + nx * depth / 2, y + ny * depth / 2];
  const back: Point = [x - nx * depth / 2, y - ny * depth / 2];
  const ring = (at: Point, r: number, theta: number): Point => [at[0] + r * Math.cos(theta) * ux, at[1] + r * (Math.cos(theta) * uy + Math.sin(theta))];
  const surfaces = Array.from({ length: 32 }, (_, i) => {
    const a = i * Math.PI / 16, b = (i + 1) * Math.PI / 16;
    const tone = Math.round(36 + 12 * Math.cos(a + .9));
    return `<path d="M${point(ring(back, radius, a))}L${point(ring(back, radius, b))}L${point(ring(front, radius, b))}L${point(ring(front, radius, a))}Z" fill="rgb(${tone} ${tone + 6} ${tone + 9})"/>`;
  }).join('');
  const grooves = Array.from({ length: 24 }, (_, i) => {
    const a = i * Math.PI / 12 + pose.roll;
    const p = ring(front, radius * .96, a), q = ring(front, radius * .83, a + .10);
    return `<path d="M${point(p)}Q${point(ring(front, radius * .91, a + .10))} ${point(q)}" fill="none" stroke="#10171b" stroke-width="1.7" opacity=".78"/>`;
  }).join('');
  const spokes = Array.from({ length: 6 }, (_, i) => {
    const a = i * Math.PI / 3 + pose.roll;
    const p = ring(front, radius * .35, a);
    return `<circle cx="${p[0]}" cy="${p[1]}" r="1.9" fill="#3e4b54"/>`;
  }).join('');
  const coils = Array.from({ length: 12 }, (_, i) => {
    const cy = mountY + 10 + i * (y - mountY - 27) / 12;
    return `<path d="M${x - 10} ${cy}q10 5 20 0m-20 0q10 -5 20 0" fill="none" stroke="#10171c" stroke-width="2.1"/><path d="M${x - 9} ${cy - 1}q6 -2 11 -.8" fill="none" stroke="#6b757c" stroke-width=".8"/>`;
  }).join('');
  return `<g data-ranger-wheel="${x}" opacity="${far ? .88 : 1}">
    <path d="${ellipse(...back, radius, ux, uy)}" fill="#141b1f"/>
    ${surfaces}
    <path d="${ellipse(...front, radius, ux, uy)}" fill="url(#${id}-tire)" stroke="#11191e" stroke-width="1.2"/>
    ${grooves}
    <path d="${ellipse(...front, radius * .63, ux, uy)}" fill="#161f25" stroke="#66727a" stroke-width="1.5"/>
    <path d="${ellipse(...front, radius * .54, ux, uy)}" fill="url(#${id}-rim)" stroke="#c9d2d6" stroke-width="1.1"/>
    <path d="${ellipse(...front, radius * .40, ux, uy)}" fill="#9ba8af" stroke="#6f7d86" stroke-width="1"/>
    ${spokes}
    <path d="${ellipse(...front, radius * .17, ux, uy)}" fill="#66757e"/>
    <path d="M${x - 11} ${mountY}h22l-2 ${y - mountY - 7}q-9 12 -18 0Z" fill="url(#${id}-strut)"/>
    <path d="M${x - 2} ${mountY + 3}v${y - mountY - 18}" stroke="#bac7cf" stroke-width="2.4" opacity=".65"/>
    ${coils}
    <path d="M${x - 12} ${y - 16}h8v15h10v-15h8v16q-12 13 -26 0Z" fill="#252f36"/>
    <ellipse cx="${x + 1}" cy="${y}" rx="6.6" ry="7.4" fill="#bdc8ce" stroke="#697882" stroke-width="1.3"/>
    <ellipse cx="${x + 1}" cy="${y}" rx="3.8" ry="4.5" fill="#5c6b75"/>
  </g>`;
}

/** Kept separate so the body is identical at every steering/motion keyframe. */
export function rangerBody(id: string) {
  const rail = (a: Point, b: Point) => `<path d="M${point(a)}L${point(b)}" stroke="#a1adb4" stroke-width="6"/><path d="M${a[0]} ${a[1] - 2}L${b[0]} ${b[1] - 2}" stroke="#e1e7ea" stroke-width="1.6"/><path d="M${a[0]} ${a[1] + 1.3}L${b[0]} ${b[1] + 1.3}" stroke="#3e4c55" stroke-width="1.1"/>`;
  return `<g data-ranger-body="shell">
    <path d="M120 341L313 389L534 333L521 370L313 427L146 389Z" fill="#242d32"/>
    <path d="M306 400L457 363L444 440L322 470L296 454Z" fill="url(#${id}-battery)" stroke="#4c565c" stroke-width="1.1"/>
    <path d="M308 406L444 372L434 431L324 459Z" fill="#343d43"/>
    <path d="M324 460l10 -2v5l-10 3Zm104 -25l10 -3v6l-10 2Z" fill="#b5c0c6" stroke="#58666f" stroke-width=".7"/>
    <path d="M93 342L263 386L255 426L126 391Z" fill="url(#${id}-front)" stroke="#9aa8b0" stroke-width=".9"/>
    <path d="M141 367l33 9 1 12 -32 -9Zm61 16 32 8 -2 11 -30 -8Z" fill="none" stroke="#9ba8b0" stroke-width=".8"/>
    <path d="M82 280Q82 274 90 272L362 210Q370 209 378 211L548 253Q555 255 555 262L555 322L280 391Q272 393 264 390L83 343Z" fill="url(#${id}-body)" stroke="#aab6bd" stroke-width="1.2"/>
    <path d="M83 282L269 329L270 390L84 343Z" fill="url(#${id}-front)"/>
    <path d="M270 329L554 261L554 322L280 391Q273 393 270 390Z" fill="url(#${id}-body)"/>
    <path d="M82 280Q82 274 90 272L362 210Q370 209 378 211L548 253Q555 255 555 262L280 330Q271 332 264 329Z" fill="url(#${id}-deck)" stroke="#9fadb5" stroke-width="1.3"/>
    <path d="M96 279L367 218L539 259L271 323Z" fill="#4b555c" stroke="#7c8b94" stroke-width=".8"/>
    ${rail([118, 279], [372, 221])}${rail([240, 311], [498, 250])}
    <path d="M122 282L243 312M373 225L497 253" fill="none" stroke="#75858f" stroke-width="1.2"/>
    <path d="M254 258l67 -15 51 12 -66 16Z" fill="#3b454d" stroke="#71828c" stroke-width=".8"/>
    <g transform="matrix(1 .258 0 1 94 294)">
      <rect x="1" y="1" width="13" height="33" rx="3" fill="#202b32"/>
      <ellipse cx="7.5" cy="10" rx="3.4" ry="5.5" fill="#08151d" stroke="#6d7d87" stroke-width=".8"/>
      <ellipse cx="7.5" cy="25" rx="3.2" ry="4.2" fill="#10232e" stroke="#506674" stroke-width=".7"/>
      <rect x="22" y="0" width="111" height="4" rx="2" fill="#b8d9e3" stroke="#7c929f" stroke-width=".6"/>
      <rect x="24" y="11" width="42" height="31" rx="1.5" fill="#dde4e7" stroke="#96a4ad" stroke-width=".8"/>
      <rect x="83" y="11" width="42" height="31" rx="1.5" fill="#e6ebed" stroke="#96a4ad" stroke-width=".8"/>
      <ellipse cx="74" cy="25" rx="2.8" ry="4" fill="#34434c"/>
      <rect x="141" y="9" width="13" height="32" rx="3" fill="#1e2b33"/>
      <ellipse cx="147.5" cy="18" rx="3.6" ry="5.5" fill="#0e1b24" stroke="#586d7a" stroke-width=".8"/>
      <ellipse cx="147.5" cy="32" rx="3" ry="4" fill="#0e1b24" stroke="#586d7a" stroke-width=".8"/>
      ${[25,64,84,123].map(x => bolt(x, 14, 1)).join('')}${[25,64,84,123].map(x => bolt(x, 39, 1)).join('')}
    </g>
    <g transform="matrix(1 -.245 0 1 283 333)">
      <path d="M72 0V55M225 0V55" fill="none" stroke="#94a2ab" stroke-width="1"/>
      <path d="M75 1V54M227 0V53" fill="none" stroke="#f7f9fa" stroke-width=".9"/>
      <rect x="10" y="17" width="50" height="5.6" rx="2.8" fill="#1e2b32"/><rect x="10" y="34" width="50" height="5.6" rx="2.8" fill="#1e2b32"/>
      <path d="M109 12H192L172 46H89Z" fill="#24313a"/>
      <path d="M199 12h8l-20 34h-8Zm14 0h7l-20 34h-7Z" fill="#24313a"/>
      <text x="113" y="29" font-family="Arial,sans-serif" font-size="13" letter-spacing=".5" fill="#f0f5f6">AGILE<tspan fill="#cd4949">·X</tspan></text>
      <text x="117" y="38" font-family="Arial,sans-serif" font-size="4.7" letter-spacing="3" fill="#cbd5da">ROBOTICS</text>
      <rect x="237" y="16" width="23" height="5.6" rx="2.8" fill="#1c2931"/><rect x="237" y="33" width="23" height="5.6" rx="2.8" fill="#1c2931"/>
      ${[4,68,78,221,230,267].map(x => bolt(x, 51, 1.4)).join('')}
    </g>
    <path d="M79 341L267 390Q274 393 283 390L558 322L561 333L283 406Q274 409 265 406L79 355Z" fill="url(#${id}-bumper)" stroke="#4d5a63" stroke-width="1"/>
    <path d="M84 343L267 392Q275 395 284 392L554 326" fill="none" stroke="#717f88" stroke-width="1.5"/>
    ${bolt(89, 335)}${bolt(260, 379)}
  </g>`;
}

export function rangerPortrait(id: string, pose: RangerPose) {
  return `<g data-ranger-artwork="fixed-view">
    ${wheel(id, 386, 365, 45, 311, pose, true)}
    ${wheel(id, 139, 423, 55, 329, pose, true)}
    ${wheel(id, 515, 430, 57, 324, pose)}
    ${wheel(id, 299, 489, 60, 383, pose)}
    ${rangerBody(id)}
  </g>`;
}
