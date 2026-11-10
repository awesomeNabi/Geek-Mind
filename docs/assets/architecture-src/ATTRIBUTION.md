# Architecture image sources

The current five-stage global architecture is supplied by the project owner in `docs/assets/geek-mind-architecture.pdf` (uploaded as `Geek_Mind_Agent_Architecture(1).pdf`, 2026-11-10). This PDF is the canonical artwork. Its content and layout are preserved in the website SVG and PNG exports; no generative image editing is used.

Regenerate the display assets from the repository root with Poppler:

```bash
pdftocairo -svg docs/assets/geek-mind-architecture.pdf docs/assets/geek-mind-architecture.svg
pdftoppm -f 1 -singlefile -scale-to 3600 -png docs/assets/geek-mind-architecture.pdf docs/assets/geek-mind-architecture
```

The website and repository README use the self-contained SVG. The enlargement dialog also links to the original PDF. The PNG is a high-resolution raster export retained for existing image links. Text and lines remain vector paths in the SVG, and the two hardware photographs are embedded.

`build-architecture.py` is the legacy four-stage generator and must not be used to regenerate the current diagram. The earlier HTML composition is also retained as a historical source.

- **Unitree Go2 product image** — Unitree Robotics official shop:  
  <https://shop.unitree.com/products/unitree-go2>  
  Source asset: <https://shop.unitree.com/cdn/shop/files/24_1024x1024.png?v=1718274083>
- **ARX5 arm photograph** — TidyBot++ Bill of Materials documentation:  
  <https://tidybot2.github.io/docs/bom/>  
  Original asset: <https://tidybot2.github.io/docs/images/bom/parts/IMG_2296.jpg>  
  TidyBot++ documentation is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The source photographs are used only to identify the supported hardware. The ARX5 photograph is cropped and its white background is removed deterministically for layout.
