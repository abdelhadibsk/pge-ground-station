"""Lancement de la station sol :  python -m ssd [--config config.ini]"""

from __future__ import annotations

import argparse
import sys

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from . import style
from .config import Configuration
from .ihm import IHM


def main(arguments: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python -m ssd",
        description="Station sol du Système Profiler Ballon (PGE).")
    analyseur.add_argument("--config", default=None,
                           help="fichier de configuration .ini (défaut : valeurs intégrées)")
    options = analyseur.parse_args(arguments)
    try:
        config = Configuration.charger(options.config)
    except (OSError, ValueError, KeyError) as erreur:
        print(f"Configuration invalide : {erreur}", file=sys.stderr)
        return 2

    pg.setConfigOptions(antialias=True)
    application = QApplication(sys.argv[:1])
    application.setStyle("Fusion")
    application.setStyleSheet(style.FEUILLE)
    fenetre = IHM(config)
    fenetre.show()
    fenetre.demarrer()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
