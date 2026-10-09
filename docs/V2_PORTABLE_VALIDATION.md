# V2 portable startup evidence

Local development build: `2.0.0.dev4`, Windows 11, Python 3.12.10,
PySide6 6.11.2, PyInstaller 6.22.3.

Build completed on 2026-10-09 after the final configuration and collection-guide
corrections. The executable self-test exited with code 0 through native Windows
Qt at system DPI, using an isolated local destination, and reported:

```json
{
  "version": "2.0.0.dev4",
  "startup": true,
  "icons": true,
  "errors": [],
  "sd_scanned": false,
  "network_requested": false
}
```

Archive: `OpenMenuGDEMUManager-2.0.0-dev4-portable-windows.zip`

SHA256: `6BEEEE52CC7F6C1FE9765CEBC2750C99BB3AB1777EEB4BC2EC34C027DF75B470`

Executable SHA256: `63d9bc8e8ed86b7931e2d2165b79322225cff772c2a8c24b3e7d08b758e4b903`

ZIP CRC integrity passed. The archived executable's SHA256 matches the built
executable. The archive contains no runtime data, virtual environment or local
prototype artifacts. Source startup also passed from the same environment.
The self-test uses an explicit local root and does not discover physical storage.
This package supersedes dev3 for the read-only configuration diagnosis and its
reachable collection view. Older packages remain historical local artifacts.

These are local packaging/startup checks, separate from the independent
reviewer's approval of the corrected code and dialog design. They do not certify
a clean Windows VM, full CDI integrity or Dreamcast game boot. Those release
gates remain pending. Public-provider search/download/decoding was checked
separately; private/credentialed provider checks remain pending.
See [provider evidence](V2_PROVIDER_VALIDATION.md),
[automated regression evidence](V2_VALIDATION.md) and
[independent audit](V2_INDEPENDENT_AUDIT.md).
