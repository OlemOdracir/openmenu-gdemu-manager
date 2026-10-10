import logging
from .config.paths import migrate_legacy_runtime_data
from .app.logger import setup_logging, install_qt_logging, operation_context


def main():
    setup_logging()
    with operation_context("startup"):
        try:
            migrate_legacy_runtime_data()
            # Qt/UI imports must follow logging so portable DLL failures survive.
            from .app.bootstrap import run
            install_qt_logging()
        except Exception:
            logging.getLogger(__name__).exception("Application startup failed")
            raise
    run()


if __name__ == "__main__":
    main()
