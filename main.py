from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.utils.paths import ensure_runtime_dirs
from app.utils.logging_setup import setup_logging


def main() -> int:
    ensure_runtime_dirs()
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("ScanDiego")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
