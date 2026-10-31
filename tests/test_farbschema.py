import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
ok = 0
def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1

S = core.FARBSCHEMEN
check(list(S)[0] == "violett" and set(S) == {"violett", "schwarz", "hell"}, "drei Schemata, Violett zuerst (Standard)")
check(all(set(v) == set(S["violett"]) for v in S.values()), "alle Schemata haben dieselben Farbschlüssel")
check(S["violett"]["cyan"] == "#c29bff" and S["violett"]["bg_dunkel"] == "#120a1f", "Violett bleibt unverändert")
check(core.FARBSCHEMA["aktuell"] == "violett" and core.FARBEN == S["violett"], "Start im violetten Schema")


def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def kontrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


for n, p in S.items():                        # Lesbarkeit der Paarungen, die das Programm nutzt
    check(kontrast(p["text"], p["bg_mittel"]) >= 7, f"{n}: Text auf Fläche")
    check(kontrast(p["cyan"], p["bg_mittel"]) >= 4.5, f"{n}: Akzent auf Fläche")
    check(kontrast(p["cyan"], p["bg_hell"]) >= 4.5, f"{n}: Akzent auf Eingabefeld")
    check(kontrast(p["bg_dunkel"], p["cyan"]) >= 4.5, f"{n}: Menütext auf markiertem Eintrag")
    check(kontrast(p["select_fg"], p["select_bg"]) >= 7, f"{n}: Auswahl")
    check(kontrast(p["text_hell"], p["bg_hover"]) >= 7, f"{n}: Text beim Überfahren")
alt = dict(core.FARBEN)
m = core.farbschema_anwenden("hell")
check(core.FARBEN == S["hell"] and core.FARBSCHEMA["aktuell"] == "hell", "Schema hell aktiv")
check(m[alt["bg_mittel"].lower()] == S["hell"]["bg_mittel"].lower(), "Zuordnung alt -> neu")
core.farbschema_anwenden("unbekannt")
check(core.FARBSCHEMA["aktuell"] == "violett" and core.FARBEN == S["violett"], "unbekannt -> Violett")
check(core.ZEICHEN_FARBE == "#c29bff", "Zeichenfarbe bleibt fest")
for k in ("menu.ansicht.farbschema", "menu.farbschema.violett", "menu.farbschema.schwarz",
          "menu.farbschema.hell", "msg.farbschema", "dlg.ja", "dlg.nein"):
    check(k in I.TEXTE["de"] and k in I.TEXTE["en"], k)
print(f"test_farbschema - {ok} Checks bestanden")
