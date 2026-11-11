"""Lancement du simulateur :  python -m simulateur [options]"""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import time

from ssd.icd import PORT_TC_DEFAUT, PORT_TM_DEFAUT, VITESSE_TREUIL_M_S

from .simulateur import AIDE, Simulateur


def _lire_clavier(file: "queue.Queue[str]") -> None:
    for ligne in sys.stdin:
        file.put(ligne)
    # Fin de l'entrée standard (lancement sans console) : le simulateur
    # continue de tourner, il s'arrête avec Ctrl+C.


def main(arguments: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python -m simulateur",
        description="Simulateur du DPF et de la PFP pour la station sol.")
    analyseur.add_argument("--adresse-ssd", default="127.0.0.1",
                           help="adresse IP de la station sol (défaut : 127.0.0.1)")
    analyseur.add_argument("--port-ssd", type=int, default=PORT_TM_DEFAUT,
                           help=f"port d'écoute de la station sol (défaut : {PORT_TM_DEFAUT})")
    analyseur.add_argument("--port-ecoute", type=int, default=PORT_TC_DEFAUT,
                           help=f"port d'écoute du DPF simulé (défaut : {PORT_TC_DEFAUT})")
    analyseur.add_argument("--periode", type=float, default=5.0,
                           help="période des HK en secondes (défaut : 5 ; exigence : <= 60)")
    analyseur.add_argument("--vitesse", type=float, default=VITESSE_TREUIL_M_S,
                           help=f"vitesse du treuil en m/s (défaut : {VITESSE_TREUIL_M_S})")
    options = analyseur.parse_args(arguments)

    simulateur = Simulateur(options.adresse_ssd, options.port_ssd, options.port_ecoute,
                            options.periode, options.vitesse)
    try:
        simulateur.ouvrir()
    except OSError as erreur:
        print(f"Impossible d'ouvrir le port UDP {options.port_ecoute} : {erreur}",
              file=sys.stderr)
        return 1

    print(f"Simulateur DPF/PFP : écoute sur le port UDP {options.port_ecoute}, "
          f"envoi vers {options.adresse_ssd}:{options.port_ssd}, "
          f"HK toutes les {options.periode:g} s, treuil à {options.vitesse:g} m/s.")
    print(AIDE)

    clavier: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=_lire_clavier, args=(clavier,), daemon=True).start()
    try:
        while True:
            simulateur.pas()
            try:
                ligne = clavier.get_nowait()
            except queue.Empty:
                pass
            else:
                if ligne.strip().lower() in ("quitter", "q", "exit"):
                    break
                reponse = simulateur.commander(ligne)
                if reponse:
                    print(reponse)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        simulateur.fermer()
    print("Simulateur arrêté.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
