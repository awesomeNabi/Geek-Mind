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

Section 01 leads with the real-world user–agent demonstration, with a smaller operator-interface walkthrough underneath. The hero Demo link jumps directly to the new player. The supplied `demo_v1.mp4` is kept intact as `../docs/assets/geek-mind-real-world-demo.mp4` (2:34, H.264/AAC); its poster is a frame from that recording. The player keeps the original audio, uses native controls and inline playback, and loads the video only when requested. The earlier project video remains in section 05.

The simulation section presents Optimus-1 and StarDojo. Edit `components/OptimusBenchmark.tsx` for the Optimus score, execution flow, replay controls, and expandable action trace. Its result definition and recorded episode data come from `../docs/assets/optimus-benchmark.json`; the same JSON is published with the media for inspection. The 24.36% overall is the mean of five advanced groups, separate from the wooden-shovel demonstration. The original GIF loads when the visitor selects play; stop restores a static first-frame poster.

Project media is copied from `../docs/assets/` before development or building. Update the original media there; the copied files are ignored by Git. The frontend poster is derived from the existing GIF. Hardware attribution is preserved in the footer and the media attribution file; font licensing is in `public/fonts/OFL.txt`.

Visual reference: https://robbyant-research.github.io/Zero-WAM/

The Go2 + Mid360 / Humble and legacy Go2 + ARX / Foxy deployment profiles remain distinct. Website changes do not modify the robotics runtime.
