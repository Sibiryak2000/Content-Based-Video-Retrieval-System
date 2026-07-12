"""Entry point for the Content-Based Video Retrieval GUI shell.

Run from the ContBVideoRetr directory:
    python main.py
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from MainWindow import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Content-Based Video Retrieval")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
