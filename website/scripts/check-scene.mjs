// Check rigid artwork, Ranger steering and the four-stage animation sequence.
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

const temp = await mkdtemp(join(tmpdir(), 'geek-mind-scene-'));
try {
  for (const name of ['rig', 'portraits', 'ranger', 'timeline']) {
    const source = await readFile(new URL(`../components/embodiment/${name}.ts`, import.meta.url), 'utf8');
    const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } });
    await writeFile(join(temp, `${name}.mjs`), outputText.replace(/from "\.\/([\w-]+)"/g, 'from "./$1.mjs"'));
  }
  const { sampleTimeline, ANIMATION } = await import(pathToFileURL(join(temp, 'timeline.mjs')));
  const { DOG_RIG, solveLeg } = await import(pathToFileURL(join(temp, 'rig.mjs')));
  const { dogPortrait, armPortrait } = await import(pathToFileURL(join(temp, 'portraits.mjs')));
  const { rangerPortrait, rangerBody } = await import(pathToFileURL(join(temp, 'ranger.mjs')));
  const start = sampleTimeline(ANIMATION.showcase[0]);
  const portrait = dogPortrait('dog', start.dog);
  const points = Object.keys(DOG_RIG).flatMap(name => {
    const leg = solveLeg(name, start.dog);
    return [leg.hip, leg.knee, leg.wheel];
  });
  const apply = ([a, b, c, d, e, f], [x, y]) => [a * x + c * y + e, b * x + d * y + f];
  const distance = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
  let maxAngle = 0;
  for (let frame = 0; frame <= 96; frame++) {
    const time = ANIMATION.showcase[0] + (ANIMATION.showcase[1] - ANIMATION.showcase[0]) * frame / 96;
    const state = sampleTimeline(time);
    assert.deepEqual(state.dog, start.dog, 'No joint or proportion changes during the showcase');
    assert.equal(dogPortrait('dog', state.dog), portrait, 'Original silver shells and details remain unchanged');
    const [a, b, c, d] = state.dogTransform;
    assert(Math.abs(a * d - b * c - 1) < 1e-12, 'No reflection or area scaling');
    const moved = points.map(p => apply(state.dogTransform, p));
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        assert(Math.abs(distance(points[i], points[j]) - distance(moved[i], moved[j])) < 1e-9, 'No stretching of any joint-to-joint distance');
      }
    }
    maxAngle = Math.max(maxAngle, Math.abs(Math.atan2(b, a) * 180 / Math.PI));
  }
  assert(maxAngle > 2 && maxAngle <= 2.2, 'Visible but restrained presentation motion');
  assert.deepEqual(sampleTimeline(0), sampleTimeline(ANIMATION.duration), 'Seamless timeline wrap');
  for (const boundary of ANIMATION.showcase) {
    const before = sampleTimeline(boundary - 0.001), after = sampleTimeline(boundary + 0.001);
    assert.deepEqual(before.dog, after.dog, 'No model swap at either presentation boundary');
    assert(before.dogTransform.every((value, i) => Math.abs(value - after.dogTransform[i]) < 0.0001), 'Smooth entry and exit');
  }
  const chassis = rangerBody('ranger');
  const restingRanger = rangerPortrait('ranger', sampleTimeline(12).ranger);
  assert.notEqual(rangerPortrait('ranger', sampleTimeline(14.2).ranger), restingRanger, 'Wheel steering and rolling are visible');
  assert.equal(rangerPortrait('ranger', sampleTimeline(16.2).ranger), restingRanger, 'Wheels return to their starting orientation');
  assert.deepEqual(sampleTimeline(12).rangerTransform, sampleTimeline(16.2).rangerTransform, 'Chassis returns before the arm transition');
  assert.deepEqual([0, 6, 14, 20, 23.6].map(time => sampleTimeline(time).stageIndex), [0, 1, 2, 3, 0], 'Legged → wheeled → Ranger → PiPER → restart');
  let maxTravel = 0;
  for (let frame = 0; frame <= ANIMATION.duration * ANIMATION.fps; frame++) {
    const time = frame / ANIMATION.fps;
    const state = sampleTimeline(time);
    const ranger = rangerPortrait('ranger', state.ranger);
    assert(!/NaN|Infinity/.test(dogPortrait('dog', state.dog) + ranger + armPortrait('arm', state.arm)), 'Finite SVG throughout the loop');
    const opacities = [state.dogOpacity, state.rangerOpacity, state.armOpacity];
    assert(opacities.every(value => value >= 0 && value <= 1), 'Opacity stays in range');
    assert(Math.abs(opacities.reduce((a, b) => a + b, 0) - 1) < 1e-12, 'Crossfades leave no blank frames');
    assert(ranger.includes(chassis), 'Ranger body contours are identical throughout steering and travel');
    assert.equal((ranger.match(/data-ranger-wheel=/g) ?? []).length, 4, 'Four independent wheel assemblies');
    assert.deepEqual(state.rangerTransform.slice(0, 4), [1, 0, 0, 1], 'Ranger body never scales or shears');
    assert(state.rangerTransform.every(Number.isFinite) && state.rangerTransform[5] === 0, 'Finite horizontal translation');
    assert(state.rangerTransform[4] >= 0 && state.rangerTransform[4] <= 34, 'Travel remains within the framing budget');
    maxTravel = Math.max(maxTravel, state.rangerTransform[4]);
  }
  assert.equal(maxTravel, 34, 'The Ranger completes its short lateral movement');
  for (const boundary of [...ANIMATION.rangerFade, ...ANIMATION.rangerSteer, ...ANIMATION.rangerTravel, ...ANIMATION.rangerReturn, ...ANIMATION.rangerStraighten, ...ANIMATION.armFade]) {
    const before = sampleTimeline(boundary - .001), after = sampleTimeline(boundary + .001);
    for (const key of ['dogOpacity', 'rangerOpacity', 'armOpacity']) {
      assert(Math.abs(before[key] - after[key]) < .0001, 'Smooth fade boundaries');
    }
    assert(Math.abs(before.ranger.steer - after.ranger.steer) < .0001 && Math.abs(before.ranger.roll - after.ranger.roll) < .0001, 'Smooth wheel motion boundaries');
    assert(Math.abs(before.rangerTransform[4] - after.rangerTransform[4]) < .0001, 'Smooth travel boundaries');
  }
  console.log('PASS: 97 dog presentation samples; unchanged silver artwork, preserved joint distances, no scaling/reflection and 2.2-degree motion.');
  console.log('PASS: 577 full-loop samples; four-stage order, rigid Ranger body, four steering wheels, 34-unit travel and return, finite SVG, continuous crossfades and seamless 24-second loop.');
} finally {
  // mkdtemp creates an isolated, owned directory directly beneath the OS temp directory.
  assert(resolve(temp).startsWith(resolve(tmpdir()) + sep + 'geek-mind-scene-'));
  await rm(temp, { recursive: true, force: true });
}
