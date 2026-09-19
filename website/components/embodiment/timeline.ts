import { ORBIT_RIG } from "./orbit-rig";
/** Seconds, radians and normalized amplitudes. The source clip occupies 0–7.6 s;
 * the PiPER extension and return dissolve bring the loop to 15 seconds. */
export const ANIMATION = {
  duration: 15,
  fps: 24,
  stepStart: 1.65,
  stepEnd: 3.1,
  stepFrequency: 1.9,
  bodyMorph: [3.3, 5.1],
  orbitBlend: 0.13,
  feetFade: [3.15, 4.1],
  wheelsFade: [4.1, 5.1],
  orbit: [5.43, 6.43],
  armFade: [7.6, 8.65],
  returnFade: [14.1, 15],
  dogYaw: ORBIT_RIG.yaw,
  dogPitch: ORBIT_RIG.pitch,
  dogScale: ORBIT_RIG.scale,
  armYaw: -0.25,
  armPitch: 0.18,
  armScale: 137,
} as const;
export const clamp = (v: number) => Math.max(0, Math.min(1, v));
export const ease = (v: number) => {
  const t = clamp(v);
  return t * t * (3 - 2 * t);
};
export const ramp = (t: number, a: number, b: number) => ease((t - a) / (b - a));
export function sampleTimeline(seconds: number) {
  const t = ((seconds % ANIMATION.duration) + ANIMATION.duration) % ANIMATION.duration;
  const armIn = ramp(t, ...ANIMATION.armFade),
    returning = ramp(t, ...ANIMATION.returnFade);
  const stepEnvelope =
    ramp(t, ANIMATION.stepStart - 0.05, ANIMATION.stepStart + 0.2) *
    (1 - ramp(t, ANIMATION.stepEnd - 0.25, ANIMATION.stepEnd + 0.05));
  const step =
    Math.sin((t - ANIMATION.stepStart) * Math.PI * 2 * ANIMATION.stepFrequency) * stepEnvelope;
  const armProgress = ramp(t, 9.0, 10.8),
    reach = ramp(t, 11.4, 12.7),
    restore = ramp(t, 13, 14.0);
  const dogTime = returning > 0 ? 0 : t;
  const wheelOpacity = ramp(dogTime, ...ANIMATION.wheelsFade);
  return {
    t,
    dogOpacity: 1 - armIn + returning,
    armOpacity: armIn * (1 - returning),
    dog: {
      morph: ramp(dogTime, ...ANIMATION.bodyMorph),
      step: returning > 0 ? 0 : step,
      footOpacity: 1 - ramp(dogTime, ...ANIMATION.feetFade),
      wheelOpacity,
      spin: 0,
      bodyLift: Math.sin(t * 12) * 0.018 * stepEnvelope,
    },
    dogCamera: {
      center: ORBIT_RIG.center,
      distance: ORBIT_RIG.distance,
      yaw: ANIMATION.dogYaw - Math.PI * 2 * ramp(dogTime, ...ANIMATION.orbit),
      pitch: ANIMATION.dogPitch,
      scale:
        ANIMATION.dogScale * (1 + 0.025 * ramp(dogTime, 1.6, 2.2) * (1 - ramp(dogTime, 3.0, 3.6))),
    },
    arm: {
      shoulder: 1.02 - 0.06 * armProgress * (1 - restore) + 0.045 * reach * (1 - restore),
      elbow: 1.35 + 0.16 * armProgress * (1 - restore) - 0.12 * reach * (1 - restore),
      wrist: 0.92 - 0.1 * reach * (1 - restore),
      grip: ramp(t, 10.5, 11.1) * (1 - ramp(t, 12.2, 12.8)),
      yaw: ANIMATION.armYaw + 0.12 * armProgress * (1 - restore),
    },
    stage: returning > 0.5 || t < 3.4 ? "足式" : t < 7.95 ? "轮式" : "松灵 PiPER",
    stageIndex: returning > 0.5 || t < 3.4 ? 0 : t < 7.95 ? 1 : 2,
  };
}
