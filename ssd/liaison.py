"""Liaisons de communication (diagramme de classes).

« Liaison » est l'interface commune : envoyer(m) / recevoir(). LiaisonEthernet
la réalise sur UDP/IP [EX-COM-010]. Une instance tourne côté IHM ; le
simulateur en utilise une autre pour jouer le DPF.

Ce module ne dépend pas de Qt.
"""

from __future__ import annotations

import socket
from typing import Callable, Protocol

from .messages import ErreurMessage, Message


class Liaison(Protocol):
    """Interface « Liaison » : transporte des Message."""

    def envoyer(self, m: Message) -> None: ...

    def recevoir(self) -> Message | None: ...


class LiaisonEthernet:
    """Liaison UDP/IP entre la SSD et le DPF.

    adresseIP / portUDP : adresse et port du correspondant (où l'on envoie).
    portEcoute          : port local sur lequel on reçoit.

    Le socket est non bloquant : recevoir() retourne None s'il n'y a rien à
    lire. Une trame invalide est comptée, signalée par ``surErreur`` et
    ignorée ; elle n'interrompt jamais la réception.
    """

    TAILLE_TAMPON = 2048

    def __init__(self, adresseIP: str, portUDP: int, portEcoute: int,
                 adresseLocale: str = "0.0.0.0") -> None:
        self.adresseIP = adresseIP
        self.portUDP = int(portUDP)
        self.portEcoute = int(portEcoute)
        self.adresseLocale = adresseLocale
        self.surErreur: Callable[[str], None] | None = None
        self.nbEmis = 0
        self.nbRecus = 0
        self.nbRejetes = 0
        self._socket: socket.socket | None = None

    # -- cycle de vie -------------------------------------------------------

    def ouvrir(self) -> None:
        """Crée le socket UDP et l'attache au port d'écoute (lève OSError)."""
        if self._socket is not None:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((self.adresseLocale, self.portEcoute))
            s.setblocking(False)
        except OSError:
            s.close()
            raise
        self._socket = s
        if self.portEcoute == 0:           # port choisi par le système (tests)
            self.portEcoute = s.getsockname()[1]

    def fermer(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    @property
    def ouverte(self) -> bool:
        return self._socket is not None

    # -- interface Liaison --------------------------------------------------

    def envoyer(self, m: Message) -> None:
        """Envoie un message au correspondant (lève OSError si l'envoi échoue)."""
        if self._socket is None:
            raise OSError("liaison Ethernet fermée")
        self._socket.sendto(m.coder(), (self.adresseIP, self.portUDP))
        self.nbEmis += 1

    def recevoir(self) -> Message | None:
        """Retourne le prochain message valide reçu, ou None s'il n'y en a pas."""
        if self._socket is None:
            return None
        for _ in range(64):                # borne : ne jamais bloquer l'appelant
            try:
                trame, origine = self._socket.recvfrom(self.TAILLE_TAMPON)
            except BlockingIOError:
                return None
            except ConnectionError:
                # Windows signale ainsi qu'un envoi précédent n'a trouvé
                # personne (port fermé en face) : sans effet sur la réception.
                continue
            except OSError as erreur:
                self._signaler(f"erreur de réception : {erreur}")
                return None
            try:
                message = Message.decoder(trame)
            except ErreurMessage as erreur:
                self.nbRejetes += 1
                self._signaler(f"trame rejetée ({origine[0]}:{origine[1]}, "
                               f"{len(trame)} octets) : {erreur}")
                continue
            self.nbRecus += 1
            return message
        return None

    def _signaler(self, texte: str) -> None:
        if self.surErreur is not None:
            self.surErreur(texte)
