import sys, os, json, math
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.model.core import Wand, Oeffnung, wand_verknuepfen, wand_in_linien
import katiecad.fileio.pdf as PDF
ok = 0
def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1

w = Wand([(0, 0), (4000, 0), (4000, 3000)], dicke=240)
check(w.typ == "wand" and isinstance(w, core.Polylinie), "Wand ist Polylinie-Unterklasse")
n0 = len(w.prims())
t = Oeffnung("tuer", 1500, 10, 0.0, dicke=240)          # slightly beside the line: still in the wall
f = Oeffnung("fenster", 4000, 1500, 90.0, dicke=240)
wand_verknuepfen([w, t, f])
check(len(w._luecken) == 1, "nur die Tuer schneidet eine Luecke")
check(abs(t._lage()[0] - 1500) < 1e-9 and abs(t._lage()[1]) < 1e-9, "Tuer richtet sich auf die Mittellinie aus")
check(t.dicke == 240 and abs(t.winkel) < 1e-9 and abs(f.winkel - 90) < 1e-9, "Winkel/Dicke aus der Wand")
innen = [pl for pl, _c in w.prims() if len(pl) == 2 and abs(pl[0][1] - 120) < 1e-6
         and abs(pl[1][1] - 120) < 1e-6 and pl[0][0] < 1500 < pl[1][0]]
check(not innen, "Wandkante ist in der Tuer unterbrochen")
xs = [p[0] for pl, _c in w.prims() for p in pl]
check(min(xs) == 0.0 and max(xs) == 4120.0, "Ausdehnung mit Gehrungsecke")
# moving the door: the wall follows (door is a normal object)
t.verschieben(1000, 0)
wand_verknuepfen([w, t, f])
check(abs(t._lage()[0] - 2500) < 1e-9 and abs(w._luecken[0][1] - (2500 - 505) / 4000) < 1e-9, "Tuer verschoben -> Luecke wandert")
# door outside the wall: no gap, free symbol
t.verschieben(0, 1000)
wand_verknuepfen([w, t])
check(w._luecken == [] and t._geo is None, "Tuer ausserhalb: keine Luecke, freies Symbol")
check(len(t.prims()) == 4, "Tuer: 2 Laibungen, Blatt, Bogen")
check(len(f.prims()) == 4, "Fenster: 2 Laibungen + 2 Glaslinien")
# flags: hinge and swing
a = Oeffnung("tuer", 0, 0, 0.0, breite=1000, dicke=200)
def blatt(o):
    return o.prims()[2][0]
b0 = blatt(a)
a.spiegeln = True; b1 = blatt(a)
check(b0[0][0] == -500 and b1[0][0] == 500 and b0[1][1] == b1[1][1], "Scharnier spiegeln: andere Seite, gleicher Aufschlag")
a.spiegeln = False; a.umkehren = True; b2 = blatt(a)
check(b2[1][1] < 0 < b0[1][1], "Aufschlag umkehren: andere Wandseite")
# grips
a.griff_bewegen("w2", 700, 0)
check(abs(a.breite - 1400) < 1e-9, "Endgriff aendert die Breite")
a.griff_bewegen("c", 50, 60)
check((a.x, a.y) == (50, 60), "Mittelgriff verschiebt")
# serialization (runtime fields must not be saved)
for el in (w, t, f):
    d = json.loads(json.dumps(el.to_dict()))
    check("_luecken" not in d and "_geo" not in d, "keine Laufzeitdaten in to_dict")
d = json.loads(json.dumps(t.to_dict())); d.pop("typ")
t2 = Oeffnung(**d)
check(t2.breite == t.breite and t2.art == "tuer", "Oeffnung Rekonstruktion")
d = json.loads(json.dumps(w.to_dict())); d.pop("typ")
check(len(Wand(**d).prims()) == n0, "Wand Rekonstruktion")
# scale / mirror via the registered transforms
w4 = Wand([(0, 0), (1000, 0)], dicke=100); w4.skalieren(0, 0, 2.0)
check(w4.dicke == 200, "Wand skalieren")
o4 = Oeffnung("tuer", 500, 0, 0.0); sb = o4.breite
o4.skalieren(0, 0, 2.0); check(abs(o4.breite - 2 * sb) < 1e-9 and o4.x == 1000, "Oeffnung skalieren")
um = o4.umkehren
core._sp_oeffnung(o4, 0, 0, 1, 0); check(o4.umkehren != um and o4.winkel == 0.0, "Oeffnung spiegeln kehrt Aufschlag um")
# closed wall
wc = Wand([(0, 0), (3000, 0), (3000, 2000), (0, 2000)], geschlossen=True, dicke=200)
check(sum(1 for _p, cl in wc.prims() if cl) == 2, "Geschlossene Wand: innere und aeussere Kontur")
# alignment
wl = Wand([(0, 0), (1000, 0)], dicke=200, ausrichtung="links")
ys = sorted({round(p[1]) for pl, _c in wl.prims() for p in pl})
check(ys == [-200, 0] or ys == [0, 200], f"Ausrichtung links: {ys}")
# pdf prims
for el in (w, t):
    pp = PDF._prims(el, 1.0, 1.0, False)
    check(len(pp) == len(el.prims()) and all(p[0] == "l" for p in pp), "PDF-Primitive")
# blocks: plain lines
w5 = Wand([(0, 0), (4000, 0)], dicke=240); t5 = Oeffnung("tuer", 2000, 0, 0.0)
bl = wand_in_linien([w5, t5])
check(all(type(e) is core.Polylinie for e in bl) and len(bl) > 4, "Block aus Wand + Tuer: einfache Polylinien")
# hit test
check(w.punkt_im_koerper(2000, 100) and not w.punkt_im_koerper(2000, 500), "Klick auf Wandkoerper")
check(t5.trifft(2000, 0) and not t5.trifft(2000, 500), "Klick in die Tuer")
for k in ("tb.wz.wand", "tb.wz.tuer", "tb.wz.fenster", "dlg.wand.titel", "dlg.wand.titel_tuer", "dlg.wand.spiegeln",
          "dlg.wand.umkehren", "menu.wand.spiegeln", "menu.wand.umkehren", "menu.wand.tuer_bearbeiten",
          "msg.wand.klick", "menu.einfuegen.wand"):
    check(k in I.TEXTE["de"] and k in I.TEXTE["en"], k)
check(core.BEFEHLE.get("WAND") == "tool:wand", "Befehl WAND")
from katiecad.ui import icons as IC
check(all(n in IC.NAMEN for n in ("wand", "tuer", "fenster")), "Icons registriert")
print(f"test_wand - {ok} Checks bestanden")
