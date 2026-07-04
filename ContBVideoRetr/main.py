"""Entry point for the Content-Based Video Retrieval GUI shell.

Run from the ContRetr directory:
    python main.py
"""

import os
import sys

# Ensure this directory is importable when launched from elsewhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
