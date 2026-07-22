#!/usr/bin/env python3
"""
AppImage Builder GUI — Universal tool to create AppImages from Linux binaries.
"""

import sys
import os

# Ensure the package root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import AppImageBuilderApp


def main():
    app = AppImageBuilderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
