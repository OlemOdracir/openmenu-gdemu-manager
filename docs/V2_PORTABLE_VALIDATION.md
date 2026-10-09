# V2 portable startup evidence

Local development build: `2.0.0.dev1`, Windows 11, Python 3.12.10,
PySide6 6.11.2, PyInstaller 6.22.3.

Build and smoke check completed on 2026-10-08. The executable self-test exited
with code 0 and reported:

```json
{
  "version": "2.0.0.dev1",
  "startup": true,
  "icons": true,
  "errors": [],
  "sd_scanned": false,
  "network_requested": false
}
```

Archive: `OpenMenuGDEMUManager-2.0.0-dev1-portable-windows.zip`

SHA256: `C9DFDBA826CED558BFAC1CDFF611E388306EAD845442498B7287165D2B76F6D3`

This verifies packaged native startup and resource loading on the development
machine. It does not certify a clean Windows VM, online provider availability,
full CDI integrity or Dreamcast game boot. Those release gates remain pending.
See [automated regression evidence](V2_VALIDATION.md).
