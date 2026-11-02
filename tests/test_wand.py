import sys, os, json, math
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.model.core import Wand
import katiecad.ui.app as A
import katiecad.fileio.pdf as PDF
ok = 0
def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1

w = Wand([(0, 0), (4000, 0), (4000, 3000)], dicke=240)
check(w.typ == "wand" and isinstance(w, core.Polylinie), "Wand ist Polylinie-Unterklasse")
n0 = len(w.prims())
o = w.oeffnung_hinzufuegen("tuer", 1500, 0)
check(o is not None and abs(o["abstand"] + o["breite"] / 2 - 1500) < 1e-6, "Tuer zentriert am Klickpunkt")
check(len(w.prims()) > n0, "Tuer erzeugt Linien (Laibung, Fluegel, Bogen)")
# door gap: no wall edge line inside the opening
innen = [pl for pl, _c in w.prims() if len(pl) == 2 and abs(pl[0][1] - 120) < 1e-6
         and abs(pl[1][1] - 120) < 1e-6 and pl[0][0] < 1500 < pl[1][0]]
check(not innen, "Wandkante ist in der Tuer unterbrochen")
xs = [p[0] for pl, _c in w.prims() for p in pl]
check(min(xs) == 0.0 and max(xs) == 4120.0, "Ausdehnung mit Mitreck-Ecke")
# thickness
bb = w.bbox()
check(abs(bb[1] + 120) < 1e-6, "bbox beruecksichtigt die Wandstaerke")
# window keeps both faces
w2 = Wand([(0, 0), (3000, 0)], dicke=300)
w2.oeffnung_hinzufuegen("fenster", 1500, 0)
glas = [pl for pl, _c in w2.prims() if len(pl) == 2 and abs(pl[0][1] - pl[1][1]) < 1e-9 and abs(pl[0][1]) <= 150.0001 and abs(pl[0][0] - pl[1][0]) > 100]
check(len(glas) >= 4, "Fenster: Wandkanten laufen durch + Glaslinien")
# alignment
wl = Wand([(0, 0), (1000, 0)], dicke=200, ausrichtung="links")
ys = sorted({round(p[1]) for pl, _c in wl.prims() for p in pl})
check(ys == [-200, 0] or ys == [0, 200], f"Ausrichtung links: {ys}")
# JSON round trip
d = json.loads(json.dumps(w.to_dict()))
d.pop("typ")
w3 = Wand(**d)
check(w3.dicke == 240 and len(w3.oeffnungen) == 1 and w3.oeffnungen[0]["art"] == "tuer", "Serialisierung")
check(len(w3.prims()) == len(w.prims()), "Rekonstruktion identisch")
# scale / mirror
core.Element.skalieren if hasattr(core.Element, "skalieren") else None
w4 = Wand([(0, 0), (1000, 0)], dicke=100); w4.oeffnung_hinzufuegen("tuer", 500, 0)
auf = w4.oeffnungen[0]["aufschlag"]
w4.skalieren(0, 0, 2.0)
check(w4.dicke == 200 and abs(w4.oeffnungen[0]["breite"] - 2000) < 1e-6, "Skalieren")
w4.spiegeln(0, 0, 1, 0)
check(w4.oeffnungen[0]["aufschlag"] != auf, "Spiegeln vertauscht Aufschlag")
# closed wall
wc = Wand([(0, 0), (3000, 0), (3000, 2000), (0, 2000)], geschlossen=True, dicke=200)
check(sum(1 for _p, c in wc.prims() if c) == 2, "Geschlossene Wand: innere und aeussere Kontur")
# pdf prims + app prims
pp = PDF._prims(w, 1.0, 1.0, False)
check(len(pp) == len(w.prims()) and all(p[0] == "l" for p in pp), "PDF-Primitive")
for k in ("tb.wz.wand", "tb.wz.tuer", "tb.wz.fenster", "dlg.wand.titel", "dlg.wand.hinweis", "msg.wand.klick",
          "menu.einfuegen.wand"):
    check(k in I.TEXTE["de"] and k in I.TEXTE["en"], k)
check(core.BEFEHLE.get("WAND") == "tool:wand", "Befehl WAND")
from katiecad.ui import icons as IC
check(all(n in IC.NAMEN for n in ("wand", "tuer", "fenster")), "Icons registriert")
print(f"test_wand - {ok} Checks bestanden")
