# V2 portable startup evidence

Local development build: `2.0.0.dev3`, Windows 11, Python 3.12.10,
PySide6 6.11.2, PyInstaller 6.22.3.

Build completed on 2026-10-09. After relocating the worktree and restoring
its local environment, the executable self-test exited with code 0 through
native Windows Qt at system DPI and reported:

```json
{
  "version": "2.0.0.dev3",
  "startup": true,
  "icons": true,
  "errors": [],
  "sd_scanned": false,
  "network_requested": false
}
```

Archive: `OpenMenuGDEMUManager-2.0.0-dev3-portable-windows.zip`

SHA256: `D6C6B77ABBD028BA76F26C3FF0BFFB7CE7ABF4E26E3DB43269169F4211445DFD`

ZIP CRC integrity passed. The archived executable's SHA256 matches the built
executable. The archive contains no runtime data, virtual environment or local
prototype artifacts. Source startup also passed from the restored environment.
This package supersedes dev2 for the corrected dialog integration. Older
packages remain historical local artifacts.

These are local packaging/startup checks, separate from the independent
reviewer's approval of the corrected code and dialog design. They do not certify
a clean Windows VM, online provider availability, full CDI integrity or
Dreamcast game boot. Those release gates remain pending.
See [automated regression evidence](V2_VALIDATION.md) and
[independent audit](V2_INDEPENDENT_AUDIT.md).
