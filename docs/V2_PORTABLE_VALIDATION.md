# V2 portable startup evidence

Local development build: `2.0.0.dev5`, Windows 11, Python 3.12.10,
PySide6 6.11.2, PyInstaller 6.22.3.

Build completed on 2026-10-09 after the CDI structural validator and read-only agent-query
corrections. The executable self-test exited with code 0 through native Windows
Qt at system DPI, using an isolated local destination, and reported:

```json
{
  "version": "2.0.0.dev5",
  "startup": true,
  "icons": true,
  "errors": [],
  "sd_scanned": false,
  "network_requested": false
}
```

Archive: `OpenMenuGDEMUManager-2.0.0-dev5-portable-windows.zip`

SHA256: `2B042924C6BD4067E7A220A5D114E7B40940A732FC51F5F2DC1560CB737905B5`

Executable SHA256: `1e7f5f8a6f388bd203b1e69184df430aeb6887c2c08b3f02b6eebc9f715b0ab7`

ZIP CRC integrity passed. The archived executable's SHA256 matches the built
executable. The archive contains no runtime data, virtual environment or local
prototype artifacts. Source startup also passed from the same environment.
The self-test uses an explicit local root and does not discover physical storage.
This package supersedes dev4 and includes supported CDI descriptor/track-bound
validation. The source installation also provides a read-only JSON CLI; this
GUI portable has no separate CLI executable and no MCP server. Older packages
remain historical local artifacts.

These are local packaging/startup checks, separate from the independent
reviewer's approval of the corrected code and dialog design. They do not certify
a clean Windows VM, payload integrity, unsupported CDI variants or Dreamcast
game boot. Those release gates remain pending; follow
[V2_EXTERNAL_ACCEPTANCE.md](V2_EXTERNAL_ACCEPTANCE.md). Public-provider search/download/decoding was checked
separately; private/credentialed provider checks remain pending.
See [provider evidence](V2_PROVIDER_VALIDATION.md),
[automated regression evidence](V2_VALIDATION.md) and
[independent audit](V2_INDEPENDENT_AUDIT.md).
