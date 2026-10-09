# V2 portable startup evidence

Local development build: `2.0.0.dev2`, Windows 11, Python 3.12.10,
PySide6 6.11.2, PyInstaller 6.22.3.

Build and smoke check completed on 2026-10-08. The executable self-test exited
with code 0 through the native Windows Qt backend at system DPI and reported:

```json
{
  "version": "2.0.0.dev2",
  "startup": true,
  "icons": true,
  "errors": [],
  "sd_scanned": false,
  "network_requested": false
}
```

Archive: `OpenMenuGDEMUManager-2.0.0-dev2-portable-windows.zip`

SHA256: `F4CE14D88098689D2C29CCA958B0E54BCDA3315E24BF633117C2ABE6B4672ABC`

This package supersedes dev1 after the independent audit corrections. Dev1 is
historical evidence, not the current recommended development checkpoint.

This verifies packaged native startup and resource loading on the development
machine. It does not certify a clean Windows VM, online provider availability,
full CDI integrity or Dreamcast game boot. Those release gates remain pending.
See [automated regression evidence](V2_VALIDATION.md) and
[independent audit](V2_INDEPENDENT_AUDIT.md).
