# Third-party Notices

OpenMenu GDEMU Manager is licensed under GPL-3.0-or-later. Some bundled third-party assets use their own compatible licenses listed below.

## Tabler Icons

This project vendors a small subset of Tabler Icons SVG assets.

- Source: https://github.com/tabler/tabler-icons
- License: MIT
- Copyright: Copyright (c) 2020-2026 Pawel Kuna

The full MIT license text is included at:

`src/openmenu_gdemu_manager/resources/vendor/tabler/LICENSE`

## BuildGDI / DiscUtilsGD

This project bundles `buildgdi.exe` v2.1.1 for rebuilding Dreamcast GDI/openMenu menu images.

- Source: https://github.com/Sappharad/GDIbuilder
- Tool page: https://projects.sappharad.com/tools/
- Bundled SHA256: `52C0B7388DEFF46652F35F3F26AC8D2E6B29720E06BD7EDE450DAA0DFF0A8C5E`

DiscUtilsGD, the GDI/GD-ROM library used by GDIbuilder, is licensed under the MIT license. The license text is included at:

`third_party/buildgdi/LICENSE-DiscUtilsGD.txt`

## OpenMenu base assets from GDMENUCardManager

This project bundles the minimal OpenMenu menu assets used to prepare folder `01` on a clean FAT32 SD:

- `third_party/openmenu/IP.BIN`
- `third_party/openmenu/menu_gdi`
- `third_party/openmenu/menu_data`
- `third_party/openmenu/menu_low_data`

Source: https://github.com/sonik-br/GDMENUCardManager

GDMENUCardManager is licensed under GPL-3.0. OpenMenu GDEMU Manager is also GPL-3.0-or-later, so these assets are distributed under compatible terms. The full GPL-3.0 license text from GDMENUCardManager is included at:

`third_party/openmenu/LICENSE-GDMENUCardManager.txt`
