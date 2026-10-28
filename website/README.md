# Geek Mind project website

Public project page: https://awesomeNabi.github.io/Geek-Mind/

This static React / Vite site is deployed by `.github/workflows/pages.yml`. GitHub Pages must use **GitHub Actions** as its source. It requires no login, server, or robot connection.

## Local development

From this directory, with Node.js 22 and pnpm 11.19.0:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

## Build and preview

```sh
pnpm build
pnpm preview
```

The build checks TypeScript and generates `dist/`. Relative asset paths support GitHub project paths such as `/Geek-Mind/`.

Edit `app/page.tsx` for content and interactions, and `app/globals.css` for layout and responsive styles. `index.html` contains metadata.

Typography follows the selected language. English preserves the original Georgia display headings and italic wordmark, Roboto Mono body and UI, and original hero letter spacing and responsive sizes. Only `html[lang=zh-CN]` switches display headings, dialogs and SVG scene titles to the self-hosted **Source Han Sans CN (思源黑体)** variable font; Chinese body text keeps Roboto Mono with Chinese fallbacks. The unmodified Simplified Chinese regional font from [Adobe Source Han Sans](https://github.com/adobe-fonts/source-han-sans/blob/release/Variable/WOFF2/TTF/Subset/SourceHanSansCN-VF.ttf.woff2) is bundled at `public/fonts/SourceHanSansCN-VF.woff2` (7.7 MB), with its SIL Open Font License at `public/fonts/SourceHanSans-OFL.txt`. It includes the full regional glyph set so new Chinese headings do not require rebuilding a text-specific font subset. `font-display: swap` keeps text visible while the font loads.

The top-right **CN / EN** buttons switch all page copy, controls, accessible labels, the document language and metadata without reloading. English is the initial default; the selected language is saved in `localStorage` when available. Edit `lib/translations.ts` for Chinese copy and `lib/i18n.tsx` for language state. Product names, original architecture artwork, videos and recorded action commands retain their source language.

The combined embodiment tab uses the project owner's original `../docs/assets/go2-piper-combined.jpg` (Go2 with an AgileX PiPER arm), displayed at its original 4:3 aspect ratio. This photo does not establish PiPER runtime support; the linked legacy ARX/Foxy guide is explicitly identified separately.

The hero uses the original detailed silver SVG dog throughout the footed and wheeled stages, including its curved shells, sensors, joints and UNITREE marking. The four-second presentation applies only a gentle rigid rotation (at most ±2.2°) and translation to the whole illustration. There is no switch to the simplified 3D model, perspective stretch or 360° orbit. The 24-second loop runs through legged Go2, wheeled Go2, a Ranger mobile base and PiPER. Ranger is drawn from [AgileX's official product photos](https://global.agilex.ai/products/ranger), retaining the silver panels, dark deck, battery, suspension and four wheels. Its body stays rigid while the wheels steer and the chassis travels sideways and returns. Check shape preservation and transition continuity with `node scripts/check-scene.mjs`; use `?scene-review&t=14.2` on the dev server to inspect the Ranger keyframe. These controls are absent from the production build.

Section 01 leads with the real-world user–agent demonstration, with a smaller operator-interface walkthrough underneath. The hero Demo link jumps directly to the new player. The supplied `demo_v1.mp4` is kept intact as `../docs/assets/geek-mind-real-world-demo.mp4` (2:34, H.264/AAC); its poster is a frame from that recording. The player keeps the original audio, uses native controls and inline playback, and loads the video only when requested. The earlier project video remains in section 05.

The simulation section presents Optimus-1 and StarDojo. Edit `components/OptimusBenchmark.tsx` for the Optimus score, execution flow, replay controls, and expandable action trace. Its result definition and recorded episode data come from `../docs/assets/optimus-benchmark.json`; the same JSON is published with the media for inspection. The 24.36% overall is the mean of five advanced groups, separate from the wooden-shovel demonstration. The original GIF loads when the visitor selects play; stop restores a static first-frame poster.

Project media is copied from `../docs/assets/` before development or building. Update the original media there; the copied files are ignored by Git. The frontend poster is derived from the existing GIF. Hardware attribution is preserved in the footer and the media attribution file; font licensing is in `public/fonts/OFL.txt`.

Visual reference: https://robbyant-research.github.io/Zero-WAM/

The Go2 + Mid360 / Humble and legacy Go2 + ARX / Foxy deployment profiles remain distinct. Website changes do not modify the robotics runtime.
