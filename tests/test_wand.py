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
# ---- hatch ----
hw = Wand([(0, 0), (3000, 0)], dicke=240, schraffur="schraeg", schraffur_abstand=60)
n_k = len(hw.prims(schraffur=False)); n_s = len(hw.prims())
check(n_s > n_k + 20, "Schraffur erzeugt Linien")
for pl, _c in hw.prims()[n_k:]:
    for (x, y) in pl:
        assert -1e-6 <= x <= 3000 + 1e-6 and -120 - 1e-6 <= y <= 120 + 1e-6, "Schraffur ausserhalb"
check(True, "Schraffur bleibt im Wandkoerper")
kw = Wand([(0, 0), (3000, 0)], dicke=240, schraffur="kreuz", schraffur_abstand=60)
check(len(kw.prims()) > len(hw.prims()), "Kreuzschraffur hat mehr Linien")
check(len(Wand([(0, 0), (3000, 0)]).prims()) == n_k, "ohne Schraffur nur Kontur")
# door gap: no hatch line inside the gap
hd = Wand([(0, 0), (3000, 0)], dicke=240, schraffur="schraeg", schraffur_abstand=40)
hd2 = Oeffnung("tuer", 1500, 0, 0.0, breite=1000)
wand_verknuepfen([hd, hd2])
for pl, _c in hd.prims()[len(hd.prims(schraffur=False)):]:
    assert not (max(p[0] for p in pl) > 1000 + 1e-6 and min(p[0] for p in pl) < 2000 - 1e-6), "Schraffur in der Tuerluecke"
check(True, "keine Schraffur in der Tuerluecke")
d = json.loads(json.dumps(hw.to_dict())); d.pop("typ")
check(Wand(**d).schraffur == "schraeg" and Wand(**d).schraffur_abstand == 60, "Schraffur wird gespeichert")
# ---- join ----
a = Wand([(0, 0), (3000, 0)], dicke=240); b = Wand([(3100, 50), (3100, 2000)], dicke=240)
r = core.wand_verbinden(a, b)
check(isinstance(r, dict) and r["punkte"] == [(0, 0), (3100, 0), (3100, 2000)] or
      [tuple(round(c, 3) for c in p) for p in r["punkte"]] == [(0, 0), (3100, 0), (3100, 2000)], "Verbinden: Ecke am Schnittpunkt")
check(not r["rev_a"] and not r["rev_b"], "Verbinden: keine Umkehrung noetig")
c = Wand([(3100, 2000), (3100, 50)], dicke=240)          # drawn the other way round
r2 = core.wand_verbinden(a, c)
check(r2["rev_b"] and not r2["rev_a"], "Verbinden: B wird umgedreht")
r3 = core.wand_verbinden(Wand([(3000, 0), (0, 0)], dicke=240, ausrichtung="links"), b)
check(r3["rev_a"] and r3["ausrichtung"] == "rechts", "Verbinden: A umgedreht tauscht die Lage")
g = Wand([(3150, 0), (6000, 0)], dicke=240)
rg = core.wand_verbinden(a, g)
check([round(p[0]) for p in rg["punkte"]] == [0, 3000, 3150, 6000], "Verbinden gerade (Parallele mit kleiner Luecke)")
check(core.wand_verbinden(a, a) == "gleich", "Verbinden: gleiche Wand")
check(core.wand_verbinden(a, Wand([(0, 0), (1, 0), (1, 1)], geschlossen=True)) == "geschlossen", "Verbinden: geschlossen")
check(core.wand_verbinden(a, Wand([(0, 9000), (3000, 9000)])) == "parallel", "Verbinden: parallel und weit weg")
check(core.wand_verbinden(a, Wand([(9000, 5000), (9000, 6000)])) == "zu_weit", "Verbinden: zu weit")
# the joined wall is one outline with a mitred outer corner
m = Wand(r["punkte"], dicke=240)
check(not any(len(pl) == 2 and abs(pl[0][0] - 3100) < 1e-6 and abs(pl[1][0] - 3100) < 1e-6
              and abs(pl[0][1]) < 1e-6 for pl, _c in m.prims()), "keine Endkappe mehr in der Ecke")
# ---- fill, windows, tolerance, defaults ----
vw = Wand([(0, 0), (3000, 0)], dicke=240, schraffur="voll")
check(len(vw.flaechen()) == 1 and len(vw.prims()) == len(vw.prims(schraffur=False)), "Vollflaeche: Flaeche, keine Linien")
check(Wand([(0, 0), (3000, 0)]).schraffur_abstand == 180, "Standard-Linienabstand 180")
fw = Wand([(0, 0), (3000, 0)], dicke=240, schraffur="voll")
fo = Oeffnung("fenster", 1500, 0, 0.0, breite=1000); wand_verknuepfen([fw, fo])
check(len(fw.flaechen()) == 2 and fw._luecken == [] and len(fw._fenster) == 1, "Fenster: Flaeche ausgespart, Kanten laufen durch")
hf = Wand([(0, 0), (3000, 0)], dicke=240, schraffur="schraeg", schraffur_abstand=40)
wand_verknuepfen([hf, fo])
for pl, _c in hf.prims()[len(hf.prims(schraffur=False)):]:
    assert not (max(p[0] for p in pl) > 1000 + 1e-6 and min(p[0] for p in pl) < 2000 - 1e-6), "Schraffur im Fenster"
check(True, "keine Schraffur im Fenster")
for ausr in ("mitte", "links", "rechts"):
    for ang in (0, 30, 77):
        a_ = math.radians(ang)
        wx = Wand([(100, 200), (100 + 3000 * math.cos(a_), 200 + 3000 * math.sin(a_))], dicke=240, ausrichtung=ausr)
        px, py = 100 + 1700 * math.cos(a_), 200 + 1700 * math.sin(a_)      # on the line
        od = Oeffnung("tuer", px, py, 0.0); wand_verknuepfen([wx, od])
        assert len(wx._luecken) == 1, f"Tuer auf der Linie ({ausr}, {ang})"
check(True, "Tuer auf der Wandlinie wird in jeder Lage gefunden")
d = json.loads(json.dumps(vw.to_dict()))
check("_fenster" not in d and d["schraffur"] == "voll", "Vollflaeche gespeichert, keine Laufzeitdaten")
check(core.WAND_SCHRAFFUREN[-1] == "voll", "Schraffurart voll vorhanden")
for k in ("tb.wz.wand", "tb.wz.tuer", "tb.wz.fenster", "dlg.wand.titel", "dlg.wand.titel_tuer", "dlg.wand.spiegeln",
          "dlg.wand.umkehren", "menu.wand.spiegeln", "menu.wand.umkehren", "menu.wand.tuer_bearbeiten",
          "msg.wand.klick", "menu.einfuegen.wand", "menu.wand.verbinden", "menu.wand.schraffur", "dlg.wand.schraffur",
          "msg.wand.zwei", "msg.wand.verb_zu_weit", "tb.wz.wandverb", "dlg.wand.schr.voll", "msg.wand.verb_erste"):
    check(k in I.TEXTE["de"] and k in I.TEXTE["en"], k)
check(core.BEFEHLE.get("WAND") == "tool:wand", "Befehl WAND")
check(core.BEFEHLE.get("WANDVERBINDEN") == "wand:verbinden", "Befehl WANDVERBINDEN")
check(core.WAND_LAYER_FARBE[0] == "#c29bff", "Wandebene in der Standardfarbe")
from katiecad.ui import icons as IC
check(all(n in IC.NAMEN for n in ("wand", "tuer", "fenster", "wandverb")), "Icons registriert")
# doppelt liegende Waende: eine Tuer / ein Fenster schneidet in alle
_a = core.Wand([(0, 0), (4000, 0)], dicke=240, schraffur="schraeg")
_b = core.Wand([(0, 0), (4000, 0)], dicke=240, schraffur="schraeg")
_t = core.Oeffnung("tuer", 1000, 0)
_f = core.Oeffnung("fenster", 3000, 0)
core.wand_verknuepfen([_a, _b, _t, _f])
check(bool(_a._luecken) and bool(_b._luecken), "Doppelte Waende: Tuer schneidet in beide")
check(bool(_a._fenster) and bool(_b._fenster), "Doppelte Waende: Fenster in beiden")
# Wandanschluss (T) und gemeinsame Kontur
_B = core.Wand([(0, 0), (6000, 0)], dicke=240, schraffur="schraeg")
_A = core.Wand([(3000, -3000), (3000, -300)], dicke=240, schraffur="schraeg")
_r = core.wand_verbinden(_A, _B)
check(isinstance(_r, dict) and _r.get("modus") == "t" and abs(_r["punkt"][1]) < 1e-6 and abs(_r["punkt"][0] - 3000) < 1e-6,
      "T-Anschluss: Wandende wird auf die andere Wand gesetzt")
_A.punkte[_r["index"]] = _r["punkt"]
core.wand_verknuepfen([_B, _A])
check(max(p[1] for pl, _c in _A.prims(schraffur=False) for p in pl) < 1.0
      and max(p[1] for pl, _c in _A.prims(schraffur=False) for p in pl) > -121,
      "T-Anschluss: Wandflaechen enden an der Flaeche der anderen Wand, Kappe verschwindet")
_A2 = core.Wand([(3000, -3000), (3000, 500)], dicke=240)
core.wand_verknuepfen([_B, _A2])
check(all(not (-100 < min(p[1] for p in pl) and max(p[1] for p in pl) < 100) for pl, _c in _A2.prims(schraffur=False)),
      "Ueberstand: nichts im Inneren der anderen Wand gezeichnet")
_W1 = core.Wand([(0, 0), (3000, 0)]); _W2 = core.Wand([(3100, 100), (3100, 3000)])
check(core.wand_verbinden(_W1, _W2).get("modus") != "t", "Ecke bleibt Ecke (Verschmelzen)")
check("_abzug" not in json.loads(json.dumps(_A.to_dict())), "Laufzeitdaten werden nicht gespeichert")
check("msg.wand.angeschlossen" in I.TEXTE["de"] and "msg.wand.angeschlossen" in I.TEXTE["en"], "Meldung angeschlossen")
print(f"test_wand - {ok} Checks bestanden")
