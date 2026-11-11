"""Configuration commune des tests : Qt sans écran, racine du projet importable."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture(scope="session")
def application():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
