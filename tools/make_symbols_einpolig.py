# -*- coding: utf-8 -*-
"""Generator for the single-pole symbols (folder "12 Single-pole").

Writes ONLY into the given output directory (default: ./symbols_einpolig),
never into symbols/. Copy the folder "12 Single-pole" into symbols/ yourself.

Conventions (as in the hand-made library): origin = upper pin, 15 mm long,
pin 1 on top (y=0, direction 90), pin 2 at the bottom (y=-15, direction 270),
mask on the left, line weight 0.35, text 2 mm. Every symbol carries the
attribute POLE (number of poles, shown beside the pole stroke) and its mask is
already marked "single-pole representation" (second drawing, never counted).

    PYTHONPATH=. python tools/make_symbols_einpolig.py [output directory]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import make_symbols as MS                      # noqa: E402
from katiecad.model.core import (ElektroMaske, AttributDefinition,   # noqa: E402
                                 Verbindungspunkt)

KATEGORIE = "12 Single-pole"
SYMS = []


class S(MS.Sym):
    def maske(self, x, y, ind, rolle="haupt"):
        self.el.append(ElektroMaske(x, y, {"IND": ind, "MAN": "MAN", "TYP": "TYP", "PER": "PER"},
                                    rolle=rolle, einpolig=True, staerke=None, **MS.STYLE))

    def pol(self, y=-3.3, pole="3"):
        """Pole stroke on the connection line + attribute POLE next to it."""
        self.line(-1.0, y - 1.0, 1.0, y + 1.0)
        self.el.append(AttributDefinition(
            1.5, y, None, 2.0, 0.0, "Arial", "mitte_links", tag="POLE",
            prompt="Pole (z. B. 3, 3+N)", wert=pole, sichtbar=True, staerke=None,
            **MS.STYLE))

    def pins(self, oben="1", unten="2"):
        self.pin(0.0, 0.0, oben)
        self.pin(0.0, -15.0, unten)
        v = [e for e in self.el if isinstance(e, Verbindungspunkt)]
        v[-2].richtungen = [90]
        v[-1].richtungen = [270]


def neu(name, de, pole="3"):
    s = S(name, KATEGORIE, de)
    SYMS.append(s)
    s.pole = pole
    return s


def zuleitung(s, y1=-5.0, y2=-10.0):
    s.line(0, 0, 0, y1)
    s.line(0, y2, 0, -15)


def trennstelle(s):
    """Switch blade (open) between -5 and -10."""
    s.line(0, -10, -2.5, -5)


def ausloeser_x(s):
    """Tripping cross at the contact (as in the multi-pole breaker)."""
    s.line(-0.7, -4.3, 0.7, -5.7)
    s.line(0.7, -4.3, -0.7, -5.7)


# ---- Leitungsschutzschalter --------------------------------------
s = neu("LS 1p", "Leitungsschutzschalter einpolig")
zuleitung(s); trennstelle(s); ausloeser_x(s)
s.poly([(-4.0, -6.8), (-5.5, -6.8), (-5.5, -8.2), (-4.0, -8.2)], closed=True)   # thermal/magnetic box
s.pol(); s.pins(); s.maske(-7.5, -13.0, "-F")

# ---- Motorschutzschalter ------------------------------------------
s = neu("MSS 1p", "Motorschutzschalter einpolig")
zuleitung(s); trennstelle(s); ausloeser_x(s)
s.circle(-4.5, -7.5, 1.3)
s.pol(); s.pins(); s.maske(-7.5, -13.0, "-Q")

# ---- Hauptschalter / Lasttrenner -----------------------------------
s = neu("Hauptschalter 1p", "Hauptschalter / Lasttrenner einpolig")
zuleitung(s); trennstelle(s)
s.line(-2.98, -7.5, -5.5, -7.5)                     # actuator
s.line(-5.5, -6.2, -5.5, -8.8)
s.pol(); s.pins(); s.maske(-8.0, -13.0, "-Q")

# ---- Schuetz (Hauptkontakt) ----------------------------------------
s = neu("Schuetz 1p", "Schütz-Hauptkontakt einpolig")
zuleitung(s); trennstelle(s)
s.line(-0.7, -4.3, 0.7, -5.7)                       # contactor mark (half cross) -> NO contact
s.line(-0.7, -5.7, 0.7, -4.3)
s.poly([(-5.5, -6.5), (-3.5, -6.5), (-3.5, -8.5), (-5.5, -8.5)], closed=True)   # coil box
s.line(-3.5, -7.5, -1.5, -7.5, dash=True)
s.pol(); s.pins(); s.maske(-7.5, -13.0, "-K", rolle="hilfs")

# ---- FI / RCD -------------------------------------------------------
s = neu("FI 1p", "Fehlerstromschutzschalter einpolig", pole="4")
zuleitung(s); trennstelle(s)
s.circle(-5.0, -7.5, 1.6)
s.line(-3.4, -7.5, -1.4, -7.5, dash=True)
s.pol(); s.pins(); s.maske(-8.5, -13.0, "-F")

# ---- Sicherung -------------------------------------------------------
s = neu("Sicherung 1p", "Sicherung einpolig")
s.line(0, 0, 0, -15)
s.poly([(-1.5, -4.5), (1.5, -4.5), (1.5, -10.5), (-1.5, -10.5)], closed=True)
s.pol(y=-2.6); s.pins(); s.maske(-3.0, -13.0, "-F")

# ---- NH-Sicherungslasttrenner ---------------------------------------
s = neu("NH 1p", "NH-Sicherungslasttrenner einpolig")
s.line(0, 0, 0, -15)
s.poly([(-1.5, -4.5), (1.5, -4.5), (1.5, -10.5), (-1.5, -10.5)], closed=True)
s.line(-2.5, -7.5, 2.5, -7.5)
s.pol(y=-2.6); s.pins(); s.maske(-3.0, -13.0, "-F")

# ---- Ueberspannungsschutz -----------------------------------------
s = neu("SPD 1p", "Überspannungsschutz einpolig")
s.line(0, 0, 0, -4)
s.poly([(-1.5, -4), (1.5, -4), (1.5, -9), (-1.5, -9)], closed=True)
s.poly([(1.0, -5.0), (0.0, -7.0), (-1.0, -5.0)], closed=False)
s.line(0, -9, 0, -15)
s.pol(y=-2.6); s.pins(); s.maske(-3.0, -13.0, "-F")

# ---- Motor (one connection: the feeder) ----------------------------
s = neu("Motor 1p", "Motor 3~ einpolig")
s.line(0, 0, 0, -6.0)
s.circle(0.0, -10.5, 4.5)
s.text(0.0, -9.5, "M", 3.0); s.text(0.0, -12.2, "3~", 2.0)
s.pin(0.0, 0.0, "1")
[e for e in s.el if isinstance(e, Verbindungspunkt)][-1].richtungen = [90]
s.pol(y=-2.5); s.maske(-5.0, -13.0, "-M")

# ---- Transformator ----------------------------------------------------
s = neu("Trafo 1p", "Transformator einpolig")
s.line(0, 0, 0, -3.5)
s.circle(0.0, -6.0, 2.5); s.circle(0.0, -11.0, 2.5)
s.line(0, -13.5, 0, -15)
s.pol(y=-1.75); s.pins(); s.maske(-4.0, -13.0, "-T")


def main(out):
    import shutil
    MS.OUT = out
    ziel = os.path.join(out, KATEGORIE)
    if os.path.isdir(ziel):
        shutil.rmtree(ziel)
    namen = set()
    for s in SYMS:
        assert s.name not in namen, s.name
        namen.add(s.name)
        s.save()
    print(len(SYMS), "Symbole nach", ziel)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "symbols_einpolig"))
