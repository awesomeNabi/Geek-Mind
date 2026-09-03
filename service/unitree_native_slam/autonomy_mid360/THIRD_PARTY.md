# Third-party source provenance

The service contains only the packages used by the current Mid360 navigation
launch. Generated files and repository metadata were excluded.

| Component | Upstream | Revision copied from | License declaration |
| --- | --- | --- | --- |
| FAST-LIO and Open3D localization fork | `https://github.com/55Dupup/FUCK-MAGIC-NAVIGATION-FAST-LIO.git` | `bcb2b8790961b95f782034ac6019ccec9459e599` plus the local navigation changes present on 2026-07-13 | BSD in package metadata; FAST-LIO license file retained |
| autonomy_stack_go2 selected packages | `https://github.com/jizhang-cmu/autonomy_stack_go2.git` | `43d5f54b389b251713f0097893c30fa76c870d54` | BSD or package-specific declarations in each `package.xml` |
| Livox-SDK2 | `https://github.com/Livox-SDK/Livox-SDK2.git` | `f5d9375f84efe2b15bc0a052d3e18482ed13adf4` | MIT license file retained |
| livox_ros_driver2 | `https://github.com/Livox-SDK/livox_ros_driver2.git` | `13eb05e4e6dd7a765b934d0c5fd6236676a57b49` | MIT license file retained |
| mid360_go2_nav_bridge | local integration package | local working tree on 2026-07-13 | MIT in `package.xml` |

Before publishing a public repository, review the package-level `TODO: License
declaration` entries inherited from the Unitree message packages. This file is
provenance documentation, not a replacement for legal review.
