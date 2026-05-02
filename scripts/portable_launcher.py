import os
import sys
from pathlib import Path


def configure_portable_environment() -> None:
    if not getattr(sys, "frozen", False):
        return

    portable_root = Path(sys.executable).resolve().parent
    os.environ.setdefault("OPENMENU_GDEMU_MANAGER_HOME", str(portable_root / "data"))
    os.environ.setdefault(
        "OPENMENU_GDEMU_MANAGER_DOCUMENTS",
        str(portable_root / "data" / "Documents"),
    )


if __name__ == "__main__":
    configure_portable_environment()

    from openmenu_gdemu_manager.__main__ import main

    main()
