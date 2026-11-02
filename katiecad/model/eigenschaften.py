# -*- coding: utf-8 -*-
"""
katiecad/model/eigenschaften.py - Common properties of a mixed selection
(NO Tkinter). Used by the properties palette (Ctrl+1).
"""
from katiecad.model.core import Text, Viewport, Bemassung, schrift_fett, schrift_name, schrift_setzen

FETT_ANZEIGE = " fett"      # palette: "Arial fett"

VERSCHIEDEN = "*"          # marker for "values differ"
ALLGEMEIN = ("layer", "farbe", "linientyp", "staerke")
TEXTFELDER = ("hoehe", "schriftart", "winkel", "einfuegepunkt")
BEMFELDER = ("dez", "pfeil", "endstueck", "text_override")          # dimensions: number of decimal places (0 ... 6)
DEZ_MAX = 6


def _ziele(auswahl):
    return [e for e in auswahl if not isinstance(e, Viewport)]


def _wert(el, feld):
    if feld == "schriftart":
        return schrift_name(el.schriftart) + (FETT_ANZEIGE if schrift_fett(el.schriftart) else "")
    if feld == "farbe":
        return el.farbe if el.eig_farbe else None      # None = by layer
    if feld == "dez":
        return int(el.dez)
    return getattr(el, feld)


def gemeinsame(auswahl):
    """-> {field: value | VERSCHIEDEN}; text fields (height, font) apply to texts AND dimensions,
    angle / insertion point to texts only, arrow size / end style to dimensions only.
    farbe None = 'by layer'."""
    z = _ziele(auswahl)
    out = {}
    if not z:
        return out
    texte = [e for e in z if isinstance(e, Text)]
    bem = [e for e in z if isinstance(e, Bemassung)]

    def sammeln(f, gruppe):
        werte = {_wert(e, f) for e in gruppe}
        out[f] = werte.pop() if len(werte) == 1 else VERSCHIEDEN

    for f in ALLGEMEIN:
        sammeln(f, z)
    for f in TEXTFELDER:
        gruppe = texte + bem if f in ("hoehe", "schriftart") else texte
        if gruppe:
            sammeln(f, gruppe)
    if bem:
        out["dez"] = None
        sammeln("dez", bem)
        sammeln("pfeil", bem)
        sammeln("endstueck", bem)
        sammeln("text_override", bem)
    return out


def anwenden(auswahl, feld, wert):
    """Sets `feld` on all affected elements. farbe: hex or None (by layer);
    staerke: float or None. Returns the number of changed elements."""
    n = 0
    for e in _ziele(auswahl):
        if feld in BEMFELDER:
            if not isinstance(e, Bemassung):
                continue
            if feld == "dez":
                e.dez = max(0, min(DEZ_MAX, int(float(wert))))
            elif feld == "pfeil":
                e.pfeil = max(0.05, float(wert))
            elif feld == "endstueck":
                e.endstueck = "strich" if wert == "strich" else "pfeil"
            elif feld == "text_override":
                e.text_override = str(wert)
        elif feld in TEXTFELDER:
            if not isinstance(e, Text) and not (isinstance(e, Bemassung) and feld in ("hoehe", "schriftart")):
                continue
            if feld == "schriftart":
                w = str(wert)
                fett = w.endswith(FETT_ANZEIGE)
                e.schriftart = schrift_setzen(w[:-len(FETT_ANZEIGE)] if fett else w, fett)
                n += 1
                continue
            setattr(e, feld, float(wert) if feld in ("hoehe", "winkel") else wert)
        elif feld == "farbe":
            if wert is None:
                e.eig_farbe = False
            else:
                e.farbe, e.eig_farbe = wert, True
        elif feld in ALLGEMEIN:
            setattr(e, feld, wert)
        else:
            continue
        n += 1
    return n
