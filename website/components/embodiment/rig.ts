/** Screen-space articulated rig for the hand-drawn reference view.
 * Each upper shell maps its authored hip/knee to the posed hip/knee. Lower
 * links are redrawn between the same joint and the planted/swinging contact.
 * Thus changing a joint never detaches the shell, shin or sensor housing.
 */
import type { DogPose } from "./robots";
export type P2 = [number, number];
export type LegName = "front" | "rear" | "farFront" | "farRear";
type Anchors = { hip: P2; knee: P2; foot: P2; wheelKnee: P2; wheel: P2 };
export const DOG_RIG: Record<LegName, Anchors> = {
  front: {
    hip: [580, 305],
    knee: [752, 455],
    foot: [640, 724],
    wheelKnee: [724, 439],
    wheel: [615, 710],
  },
  rear: {
    hip: [882, 213],
    knee: [960, 452],
    foot: [818, 658],
    wheelKnee: [1002, 326],
    wheel: [925, 575],
  },
  farFront: {
    hip: [330, 270],
    knee: [375, 501],
    foot: [211, 719],
    wheelKnee: [425, 374],
    wheel: [225, 600],
  },
  farRear: {
    hip: [675, 229],
    knee: [716, 352],
    foot: [650, 508],
    wheelKnee: [720, 278],
    wheel: [530, 472],
  },
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const bodyRise = (pose: DogPose) => pose.morph * 90 + pose.bodyLift * 45;
export function solveLeg(name: LegName, pose: DogPose) {
  const a = DOG_RIG[name],
    q = pose.morph;
  const phase = pose.step * (name === "front" || name === "farRear" ? 1 : -1);
  const angle = phase * 0.075 * (1 - q),
    cs = Math.cos(angle),
    sn = Math.sin(angle);
  const dx = a.knee[0] - a.hip[0],
    dy = a.knee[1] - a.hip[1];
  const rise = bodyRise(pose);
  const hip: P2 = [a.hip[0], a.hip[1] - rise];
  const knee: P2 = [
    lerp(a.hip[0] + dx * cs - dy * sn, a.wheelKnee[0], q),
    lerp(a.hip[1] + dx * sn + dy * cs, a.wheelKnee[1], q) - pose.bodyLift * 45,
  ];
  const foot: P2 = [a.foot[0] + phase * 28, a.foot[1] - Math.max(0, phase) * 34];
  return { hip, knee, foot, wheel: a.wheel, upper: similarity(a.hip, a.knee, hip, knee) };
}
export function similarity(a: P2, b: P2, c: P2, d: P2) {
  const ux = b[0] - a[0],
    uy = b[1] - a[1],
    vx = d[0] - c[0],
    vy = d[1] - c[1],
    n = ux * ux + uy * uy;
  const r = (vx * ux + vy * uy) / n,
    s = (vy * ux - vx * uy) / n;
  return `matrix(${r} ${s} ${-s} ${r} ${c[0] - r * a[0] + s * a[1]} ${c[1] - s * a[0] - r * a[1]})`;
}
export function portraitCamera(pose: DogPose) {
  // Widen the framing as larger wheels appear so the square hero retains the
  // complete wheel silhouette (the landscape reference crops its nearest tire).
  const q = pose.morph;
  return `translate(${lerp(-42, 10, q)} ${lerp(77, 125, q)}) scale(${lerp(0.63, 0.54, q)})`;
}
