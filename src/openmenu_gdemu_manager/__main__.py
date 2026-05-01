from .config.paths import migrate_legacy_runtime_data
from .app.logger import setup_logging
from .app.bootstrap import run


def main() -> None:
    migrate_legacy_runtime_data()
    setup_logging()
    run()


if __name__ == "__main__":
    main()
