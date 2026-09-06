import { copyFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const source = new URL('../../docs/assets/', import.meta.url);
const destination = new URL('../public/media/', import.meta.url);
mkdirSync(destination, { recursive: true });
const files = [
  ['geek-mind-architecture.png', 'geek-mind-architecture.png'],
  ['geek-mind-demo.mp4', 'geek-mind-demo.mp4'],
  ['geek-mind-demo-cover.jpg', 'geek-mind-demo-cover.jpg'],
  ['geek-mind-frontend-demo.gif', 'geek-mind-frontend-demo.gif'],
  ['architecture-src/unitree-go2.png', 'unitree-go2.png'],
  ['architecture-src/arx-x5.png', 'arx-x5.png'],
  ['architecture-src/ATTRIBUTION.md', 'ATTRIBUTION.md'],
];
for (const [from, to] of files) copyFileSync(new URL(from, source), new URL(to, destination));
console.log(`Prepared ${files.length} existing project assets in ${fileURLToPath(destination)}`);
