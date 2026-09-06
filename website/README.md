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

Project media is copied from `../docs/assets/` before development or building. Update the original media there; the copied files are ignored by Git. The frontend poster is derived from the existing GIF. Hardware attribution is preserved in the footer and the media attribution file; font licensing is in `public/fonts/OFL.txt`.

Visual reference: https://robbyant-research.github.io/Zero-WAM/

The Go2 + Mid360 / Humble and legacy Go2 + ARX / Foxy deployment profiles remain distinct. Website changes do not modify the robotics runtime.
