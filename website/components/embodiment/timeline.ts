import { rigidPresentation } from "./rig";
/** Seconds, radians and normalized amplitudes. The original silver artwork
 * moves gently in its reference view; the four-stage showcase loops in 24 seconds. */
export const ANIMATION = {
  duration: 24,
  fps: 24,
  stepStart: 1.65,
  stepEnd: 3.1,
  stepFrequency: 1.9,
  bodyMorph: [3.3, 5.1],
  feetFade: [3.15, 4.1],
  wheelsFade: [4.1, 5.1],
  showcase: [5.4, 9.4],
  rangerFade: [10.6, 11.65],
  rangerSteer: [12.1, 12.8],
  rangerTravel: [12.85, 14.15],
  rangerReturn: [14.45, 15.65],
  rangerStraighten: [15.7, 16.2],
  armFade: [16.6, 17.65],
  returnFade: [23.1, 24],
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
  const rangerIn = ramp(t, ...ANIMATION.rangerFade),
    armIn = ramp(t, ...ANIMATION.armFade),
    returning = ramp(t, ...ANIMATION.returnFade);
  const stepEnvelope =
    ramp(t, ANIMATION.stepStart - 0.05, ANIMATION.stepStart + 0.2) *
    (1 - ramp(t, ANIMATION.stepEnd - 0.25, ANIMATION.stepEnd + 0.05));
  const step = stepEnvelope > 0
    ? Math.sin((t - ANIMATION.stepStart) * Math.PI * 2 * ANIMATION.stepFrequency) * stepEnvelope
    : 0;
  const armProgress = ramp(t, 18.0, 19.8),
    reach = ramp(t, 20.4, 21.7),
    restore = ramp(t, 22, 23.0);
  const dogTime = returning > 0 ? 0 : t;
  const wheelOpacity = ramp(dogTime, ...ANIMATION.wheelsFade);
  const turn = dogTime > ANIMATION.showcase[0] && dogTime < ANIMATION.showcase[1]
    ? Math.sin(Math.PI * 2 * ramp(dogTime, ...ANIMATION.showcase))
    : 0;
  const travel = ramp(t, ...ANIMATION.rangerTravel) - ramp(t, ...ANIMATION.rangerReturn);
  return {
    t,
    dogOpacity: 1 - rangerIn + returning,
    rangerOpacity: rangerIn * (1 - armIn),
    armOpacity: armIn * (1 - returning),
    dog: {
      morph: ramp(dogTime, ...ANIMATION.bodyMorph),
      step: returning > 0 ? 0 : step,
      footOpacity: 1 - ramp(dogTime, ...ANIMATION.feetFade),
      wheelOpacity,
      spin: 0,
      bodyLift: stepEnvelope > 0 ? Math.sin(t * 12) * 0.018 * stepEnvelope : 0,
    },
    dogTransform: rigidPresentation(turn),
    ranger: {
      steer: .65 * ramp(t, ...ANIMATION.rangerSteer) * (1 - ramp(t, ...ANIMATION.rangerStraighten)),
      roll: travel * .9,
    },
    rangerTransform: [1, 0, 0, 1, 34 * travel, 0],
    arm: {
      shoulder: 1.02 - 0.06 * armProgress * (1 - restore) + 0.045 * reach * (1 - restore),
      elbow: 1.35 + 0.16 * armProgress * (1 - restore) - 0.12 * reach * (1 - restore),
      wrist: 0.92 - 0.1 * reach * (1 - restore),
      grip: ramp(t, 19.5, 20.1) * (1 - ramp(t, 21.2, 21.8)),
      yaw: ANIMATION.armYaw + 0.12 * armProgress * (1 - restore),
    },
    stage: returning > 0.5 || t < 3.4 ? "足式" : t < 11.125 ? "轮式" : t < 17.125 ? "Ranger 底盘" : "松灵 PiPER",
    stageIndex: returning > 0.5 || t < 3.4 ? 0 : t < 11.125 ? 1 : t < 17.125 ? 2 : 3,
  };
}
