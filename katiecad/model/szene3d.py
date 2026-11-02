# -*- coding: utf-8 -*-
"""
katiecad/model/szene3d.py - Scene logic of the 3D wireframe view (NO Tkinter).

Collects the 3D bodies and the flat 2D drawing of a sheet, picks objects,
and does the maths of the 3D manipulator (X/Y/Z arrows).
"""

import copy
import math

from katiecad.model.core import (Koerper3D, Gruppe3D, Skizze3D, Bemassung3D, Text3D, Linie, Rechteck,
                                 Polylinie, Kreis, Bogen, Ellipse, ZUSAMMENGESETZT, bogen_punkte,
                                 bogen_sweep, profil_aus_element, extrusion)
from katiecad.model import geom3d as G
from katiecad.model.core import G_dot_tiefe as core_dot_tiefe

KOERPER_TYPEN = (Koerper3D, Gruppe3D)


RAUM_TYPEN = (Koerper3D, Gruppe3D, Skizze3D, Bemassung3D, Text3D)


def ist_3d(el):
    return isinstance(el, KOERPER_TYPEN)


def ist_raum(el):
    """Elements with real 3D coordinates (bodies, sketches on planes, 3D dimensions)."""
    return isinstance(el, RAUM_TYPEN)


def zuege3(el):
    """3D polylines [(points, closed)] of every non-body element (2D shapes at z = 0)."""
    if isinstance(el, Skizze3D):
        pts = el.zug3()
        return [(pts, el.geschlossen())] if len(pts) >= 2 else []
    if isinstance(el, Bemassung3D):
        return [(z, False) for z in el.zuege3()]
    if isinstance(el, Text3D):
        return [(z, False) for z in el.zuege3() if len(z) >= 2] if el.ebene is not None else []
    return [([(x, y, 0.0) for (x, y) in zug], closed) for zug, closed in flache_zuege(el)]


def koerper_netze(elemente):
    """[(top-level element, Netz)] of all 3D bodies."""
    out = []
    for el in elemente:
        if ist_3d(el):
            for nz in el.netze():
                out.append((el, nz))
    return out


def _front_aus_profil(korpus):
    """Direction of the front of a cabinet carcass from its plan: the first edge of the base
    rectangle (profile point 0 -> 1) is the front; it survives moving, turning and mirroring."""
    pr = getattr(korpus, "profil", None)
    if getattr(korpus, "art", "") != "prisma" or getattr(korpus, "ebene", None) or not pr or len(pr) < 4:
        return None
    cx = sum(p[0] for p in pr) / len(pr)
    cy = sum(p[1] for p in pr) / len(pr)
    dx = (pr[0][0] + pr[1][0]) / 2.0 - cx
    dy = (pr[0][1] + pr[1][1]) / 2.0 - cy
    ln = math.hypot(dx, dy)
    return None if ln < 1e-6 else (dx / ln, dy / ln, 0.0)


def _offen_richtung(teile):
    """Cabinet without door: direction of its open front (None = closed / no cabinet).
    Recognised by the part names of schrank.schrank_bauen: carcass + mounting plate, no door."""
    namen = {getattr(t, "bez", None): t for t in teile if not isinstance(t, Gruppe3D)}
    korpus, platte = namen.get("Schaltschrank"), namen.get("Montageplatte")
    if korpus is None or "Tür" in namen:
        return None
    if platte is None:                      # no mounting plate: the front edge tells the side
        return _front_aus_profil(korpus)
    bk, bp = korpus.bbox3(), platte.bbox3()
    if not bk or not bp:
        return None
    d = tuple(((bk[i] + bk[i + 3]) - (bp[i] + bp[i + 3])) / 2.0 for i in range(3))
    ln = math.sqrt(sum(c * c for c in d))
    return None if ln < 1e-6 else tuple(c / ln for c in d)


TUER_TEILE = ("Tür", "Türgriff", "Schloss")


def ohne_tueren(elemente, aus=True):
    """Elements with the door parts (door, handle, lock) of cabinet blocks left out - for a
    viewport that shows the cabinet without door. The reduced copy of a block is kept on the
    block, so ids stay stable (hidden-line cache) as long as its parts do not change."""
    if not aus:
        return list(elemente)

    def reduziert(g):
        if not isinstance(g, Gruppe3D):
            return g
        if not any(getattr(t, "bez", None) in TUER_TEILE or isinstance(t, Gruppe3D)
                   for t in g.teile):
            return g
        schluessel = tuple(id(t) for t in g.teile)
        c = getattr(g, "_ohne_tuer", None)
        if c is not None and c[0] == schluessel:
            return c[1]
        neu = [reduziert(t) for t in g.teile if getattr(t, "bez", None) not in TUER_TEILE]
        if all(a is b for a, b in zip(neu, g.teile)) and len(neu) == len(g.teile):
            erg = g
        else:
            erg = copy.copy(g)
            erg.teile = neu
        g._ohne_tuer = (schluessel, erg)
        return erg

    return [reduziert(el) for el in elemente]


def koerper_netze_offen(elemente):
    """Like koerper_netze, plus {id(mesh): direction} of the open sides (cabinets without door)."""
    paare, offen = [], {}

    def sammeln(top, el):
        if isinstance(el, Gruppe3D):
            r = _offen_richtung(el.teile)
            for t in el.teile:
                if isinstance(t, Gruppe3D):
                    sammeln(top, t)
                    continue
                netze = t.netze()
                paare.extend((top, nz) for nz in netze)
                if r is not None and getattr(t, "bez", None) == "Schaltschrank" and netze:
                    offen[id(netze[0])] = r
        else:
            paare.extend((top, nz) for nz in el.netze())

    for el in elemente:
        if ist_3d(el):
            sammeln(el, el)
    return paare, offen


def verdeckt_ergebnis(paare, offen, kamera, cx, cy, cache=None, signatur_extra=()):
    """Hidden-line run over [(element, mesh)] -> {id(element): (visible polylines, hidden polylines)}
    in pixels. `cache` is a one-element list holding (signature, result)."""
    sig = [round(kamera.yaw, 4), round(kamera.pitch, 4), tuple(round(v, 3) for v in kamera.ziel),
           round(kamera.abstand, 3), round(kamera.skala, 5), kamera.perspektive,
           round(cx, 2), round(cy, 2), tuple(signatur_extra)]
    gruppen, index = [], {}
    for el, nz in paare:
        if id(el) not in index:
            index[id(el)] = len(gruppen)
            gruppen.append((id(el), []))
        gruppen[index[id(el)]][1].append(nz)
        sig.append((id(el), len(nz.punkte), round(sum(c for p in nz.punkte for c in p), 2),
                    offen.get(id(nz))))
    sig = tuple(sig)
    if cache and cache[0] and cache[0][0] == sig:
        return cache[0][1]
    n_tri = sum(len(nz.dreiecke()) for _k, netze in gruppen for nz in netze)
    erg = G.sichtbare_linien_je(gruppen, kamera, cx, cy, proben=10 if n_tri < 1500 else 5,
                                offen=offen)
    if cache is not None:
        cache[:] = [(sig, erg)]
    return erg


def flache_zuege(el):
    """2D polylines [(points, closed)] of a 2D element or composite (3D bodies
    are skipped: they are drawn as solids)."""
    if ist_3d(el):
        return []
    if isinstance(el, Linie):
        return [([(el.x1, el.y1), (el.x2, el.y2)], False)]
    if isinstance(el, Rechteck):
        return [([(el.x1, el.y1), (el.x2, el.y1), (el.x2, el.y2), (el.x1, el.y2)], True)]
    if isinstance(el, Polylinie):
        return [(list(el.punkte), bool(el.geschlossen))] if len(el.punkte) >= 2 else []
    if isinstance(el, Kreis):
        n = 48
        return [([(el.cx + el.r * math.cos(2 * math.pi * i / n),
                   el.cy + el.r * math.sin(2 * math.pi * i / n)) for i in range(n)], True)]
    if isinstance(el, Bogen):
        sw = bogen_sweep(el.start, el.ende)
        n = max(8, int(sw / 6))
        return [(bogen_punkte(el.cx, el.cy, el.r, el.start, el.ende, n), False)]
    if isinstance(el, ZUSAMMENGESETZT):
        out = []
        for k in el.aufgeloest():
            out.extend(flache_zuege(k))
        return out
    return []


def szene_punkte(elemente):
    """All 3D points of the scene (2D shapes at z = 0) for 'zoom extents'."""
    pts = []
    for _el, nz in koerper_netze(elemente):
        pts.extend(nz.punkte)
    for el in elemente:
        if ist_3d(el):
            continue
        for zug, _c in zuege3(el):
            pts.extend(zug)
    return pts


def _abstand_zug(kamera, cx, cy, mx, my, zug, geschlossen):
    pts = list(zug) + ([zug[0]] if geschlossen and len(zug) > 2 else [])
    best = None
    for a, b in zip(pts, pts[1:]):
        seg = kamera.proj_segment(a, b, cx, cy)
        if seg is None:
            continue
        d = G.abstand_punkt_segment(mx, my, seg[0], seg[1])
        if best is None or d < best:
            best = d
    return best


def auswahl_im_rahmen(elemente, kamera, cx, cy, rahmen, kreuzend):
    """Elements inside (kreuzend=False) or touching (True) the screen rectangle
    rahmen = (x1, y1, x2, y2) - same logic as the 2D selection window."""
    x1, y1, x2, y2 = rahmen
    out = []
    for el in elemente:
        pts = []
        if ist_3d(el):
            for nz in el.netze():
                pts.extend(nz.punkte)
        else:
            for zug, _c in zuege3(el):
                pts.extend(zug)
        sp = [q for q in (kamera.proj(p, cx, cy) for p in pts) if q is not None]
        if not sp:
            continue
        bx1, by1 = min(q[0] for q in sp), min(q[1] for q in sp)
        bx2, by2 = max(q[0] for q in sp), max(q[1] for q in sp)
        if kreuzend:
            if bx2 >= x1 and bx1 <= x2 and by2 >= y1 and by1 <= y2:
                out.append(el)
        elif bx1 >= x1 and bx2 <= x2 and by1 >= y1 and by2 <= y2:
            out.append(el)
    return out


def pick(elemente, kamera, cx, cy, mx, my, tol=8.0):
    """Object under the screen point: 3D bodies first, then 2D shapes."""
    best, bd = None, None
    for el, nz in koerper_netze(elemente):
        d = G.abstand_zu_netz(nz, kamera, cx, cy, mx, my)
        if d is not None and d <= tol and (bd is None or d < bd):
            best, bd = el, d
    if best is not None:
        return best
    for el in reversed(elemente):
        if ist_3d(el):
            continue
        if isinstance(el, Text3D) and el.ebene is None:
            q = kamera.proj(el.p, cx, cy)
            if q:
                zeilen = (el.inhalt or " ").split("\n")
                w = max(len(z) for z in zeilen) * el.hoehe * kamera.skala * 0.65
                h = len(zeilen) * el.hoehe * kamera.skala * 1.3
                if q[0] - tol <= mx <= q[0] + w + tol and q[1] - h - tol <= my <= q[1] + tol:
                    if bd is None or 0.0 < bd:
                        best, bd = el, 0.0
            continue
        for zug, geschlossen in zuege3(el):
            d = _abstand_zug(kamera, cx, cy, mx, my, zug, geschlossen)
            if d is not None and d <= tol and (bd is None or d < bd):
                best, bd = el, d
    return best


def drehen3d(auswahl, p0, achse, winkel_deg):
    """Rotates the selection about the axis through p0. 3D objects turn about any axis,
    2D shapes only about Z. Returns the number of rotated objects."""
    n = 0
    z_achse = abs(achse[0]) < 1e-9 and abs(achse[1]) < 1e-9
    for el in auswahl:
        if hasattr(el, "drehen3"):
            el.drehen3(p0, achse, winkel_deg)
            n += 1
        elif z_achse and hasattr(el, "drehen"):
            el.drehen(p0[0], p0[1], winkel_deg if achse[2] > 0 else -winkel_deg)
            n += 1
    return n


def auswahl_zentrum3(auswahl):
    """Centre of the bounding box of the selection in 3D (2D shapes at z = 0)."""
    xs, ys, zs = [], [], []
    for el in auswahl:
        if ist_3d(el):
            b = el.bbox3()
            if b:
                xs += [b[0], b[3]]; ys += [b[1], b[4]]; zs += [b[2], b[5]]
        elif ist_raum(el):
            c = el.zentrum3()
            xs.append(c[0]); ys.append(c[1]); zs.append(c[2])
        elif hasattr(el, "bbox"):
            b = el.bbox()
            xs += [b[0], b[2]]; ys += [b[1], b[3]]; zs += [0.0]
    if not xs:
        return None
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)


def extrudierbar(el):
    if isinstance(el, Skizze3D):
        return len(el.profil()) >= 3
    return (not ist_raum(el)) and profil_aus_element(el) is not None


# --------------------------------------------------------------------------
# Manipulator (axes X / Y / Z)
# --------------------------------------------------------------------------
ACHSEN = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def achsen_info(kamera, zentrum, cx, cy, laenge_px=70.0):
    """For each axis: {"von": (x, y), "bis": (x, y), "dir": (ux, uy) unit vector
    on the screen, "px_pro_mm": scale along the axis}. Axes pointing at the
    viewer (almost zero length on screen) are left out."""
    p0 = kamera.proj(zentrum, cx, cy)
    if p0 is None:
        return {}
    L = laenge_px / max(kamera.skala, 1e-9)
    out = {}
    for name, a in ACHSEN.items():
        q = (zentrum[0] + a[0] * L, zentrum[1] + a[1] * L, zentrum[2] + a[2] * L)
        p1 = kamera.proj(q, cx, cy)
        if p1 is None:
            continue
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        l = math.hypot(dx, dy)
        if l < 12.0:
            continue
        out[name] = {"von": (p0[0], p0[1]), "bis": (p1[0], p1[1]),
                     "dir": (dx / l, dy / l), "px_pro_mm": l / L}
    return out


def manip_treffer(infos, mx, my, tol=7.0):
    best, bd = None, None
    for name, i in infos.items():
        d = G.abstand_punkt_segment(mx, my, i["von"], i["bis"])
        if d <= tol and (bd is None or d < bd):
            best, bd = name, d
    return best


def verschiebung_mm(info, dx_px, dy_px, raster=None):
    """Signed distance along the axis for a mouse movement of (dx, dy) pixels."""
    mm = (dx_px * info["dir"][0] + dy_px * info["dir"][1]) / info["px_pro_mm"]
    if raster and raster > 0:
        mm = round(mm / raster) * raster
    return mm


def verschieben_achse(auswahl, achse, mm):
    a = ACHSEN[achse]
    for el in auswahl:
        if hasattr(el, "verschieben"):
            if ist_raum(el):
                el.verschieben(a[0] * mm, a[1] * mm, a[2] * mm)
            elif achse != "z":
                el.verschieben(a[0] * mm, a[1] * mm)


def gruppe_bilden(elemente, auswahl, name="3D-Block"):
    """Puts the selected 3D bodies into one Gruppe3D (replaces them in `elemente`).
    Returns the group or None."""
    teile = [e for e in auswahl if ist_3d(e)]
    if len(teile) < 2:
        return None
    ids = {id(t) for t in teile}
    pos = min(i for i, e in enumerate(elemente) if id(e) in ids)
    rest = [e for e in elemente if id(e) not in ids]
    g = Gruppe3D(teile, name, layer=teile[0].layer, farbe=teile[0].farbe,
                 linientyp=teile[0].linientyp, eig_farbe=teile[0].eig_farbe,
                 staerke=teile[0].staerke)
    rest.insert(min(pos, len(rest)), g)
    elemente[:] = rest
    return g


def _schnittkoerper(k):
    """Cutters (holes, cut-outs) of a body as closed meshes, slightly longer than the cut so
    that no coplanar faces remain after the subtraction."""
    host = k.netz()
    out = []
    if k.art != "prisma":
        return out
    if not k.ebene:
        oben = max(k.z0, k.z0 + k.hoehe)
        unten = min(k.z0, k.z0 + k.hoehe)
        for (x, y, r, tiefe) in k.loecher:
            h = (oben - unten) if tiefe is None else min(abs(tiefe), oben - unten)
            extra = 1.0 if tiefe is None else 0.0
            out.append(G.prisma_netz(G.kreis_profil(x, y, r, 24), oben - h - extra,
                                     h + extra + 1.0, True))
    for a in k.ausschnitte:
        e, tiefe = a["ebene"], a["tiefe"]
        extra = 0.0
        if tiefe is None:
            tiefe = max([core_dot_tiefe(e, p) for p in host.punkte] or [0.0])
            extra = 1.0
        tiefe = max(tiefe, 1e-3)
        out.append(G.netz_abbilden(G.prisma_netz(a["profil"], 1.0, -(tiefe + 1.0 + extra),
                                                 a["rund"]), e))
    return out


def verschmelzen(elemente, auswahl, vorher=None):
    """Boolean union of the selected 3D bodies (also the parts of 3D blocks) to ONE body
    (replaces them in `elemente`). Returns the new body; ValueError (csg3d.CSGFehler)
    if the bodies cannot be merged; None if fewer than two bodies are selected."""
    from katiecad.model import csg3d
    ziele = [e for e in auswahl if ist_3d(e) and e in elemente]
    teile = [k for e in ziele for k in e.koerper()]
    if len(teile) < 2:
        return None
    erg = csg3d.vereinigen([(k.netz(), _schnittkoerper(k)) for k in teile])
    if vorher:
        vorher()                      # e.g. undo snapshot - only when the merge worked
    ids = {id(t) for t in ziele}
    pos = min(i for i, e in enumerate(elemente) if id(e) in ids)
    rest = [e for e in elemente if id(e) not in ids]
    n = Koerper3D(art="netz", netzdaten=erg, layer=ziele[0].layer, farbe=ziele[0].farbe,
                  linientyp=ziele[0].linientyp, eig_farbe=ziele[0].eig_farbe,
                  staerke=ziele[0].staerke)
    rest.insert(min(pos, len(rest)), n)
    elemente[:] = rest
    return n


def gruppe_aufloesen(elemente, gruppen):
    """Replaces the groups by their parts; returns the freed parts."""
    frei = []
    for g in gruppen:
        if not isinstance(g, Gruppe3D) or g not in elemente:
            continue
        i = next(k for k, e in enumerate(elemente) if e is g)
        elemente[i:i + 1] = g.teile
        frei.extend(g.teile)
    return frei


def extrudieren(elemente, ziele, hoehe, z0=0.0, original_behalten=False):
    """Replaces the closed 2D shapes `ziele` by prisms of the given (signed) height."""
    neu = []
    for el in ziele:
        k = extrusion(el, hoehe, z0)
        if k is None:
            continue
        if not original_behalten:
            for i, e in enumerate(elemente):
                if e is el:
                    elemente[i] = k
                    break
        else:
            elemente.append(k)
        neu.append(k)
    return neu


# --------------------------------------------------------------------------
# Holes (bores)
# --------------------------------------------------------------------------
def loch_ziele(auswahl):
    """Prism bodies of the selection (also inside 3D blocks) that can get a hole."""
    out = []
    for el in auswahl:
        if ist_3d(el):
            out.extend(k for k in el.koerper() if k.art == "prisma")
    return out


def loch_oben_z(koerper):
    return max(koerper.z0, koerper.z0 + koerper.hoehe)


def loch_setzen(koerper, x, y, r, tiefe=None):
    """Adds a hole; False if the centre lies outside the base polygon."""
    if koerper.art != "prisma" or r <= 0:
        return False
    if koerper.profil and not G.punkt_in_polygon(x, y, koerper.profil):
        return False
    koerper.loch_hinzufuegen(x, y, r, tiefe)
    return True


# --------------------------------------------------------------------------
# Faces, work planes, sketches
# --------------------------------------------------------------------------
def flaeche_pick(elemente, kamera, cx, cy, mx, my, tol=10.0):
    """Face of a body under the screen point -> (body, plane, face points) or None.
    Directly on an edge or corner (no face is hit exactly) the visible face whose
    outline is within `tol` pixels wins, so edge points can be snapped."""
    o, d = kamera.strahl(mx, my, cx, cy)
    best = None
    for el in elemente:
        if not ist_3d(el):
            continue
        for k in el.koerper():
            nz = k.netz()
            tr_ = G.flaeche_treffer(nz, o, d)
            if tr_ is None or (best is not None and tr_[0] >= best[0]):
                continue
            pts = [nz.punkte[i] for i in nz.flaechen[tr_[1]]]
            e = G.ebene_von_flaeche(pts, k.zentrum3())
            if e is not None:
                best = (tr_[0], k, e, pts)
    if best is not None:
        return best[1], best[2], best[3]
    # fallback: front-facing face with the outline closest to the cursor
    cand = None
    for el in elemente:
        if not ist_3d(el):
            continue
        for k in el.koerper():
            nz = k.netz()
            zen = k.zentrum3()
            for f in nz.flaechen:
                pts = [nz.punkte[i] for i in f]
                e = G.ebene_von_flaeche(pts, zen)
                if e is None:
                    continue
                w = G.ebene_basis(e)[2]
                _o2, d2 = kamera.strahl(mx, my, cx, cy)
                if G.v_dot(w, d2) > 1e-6:                     # back face
                    continue
                dist = _abstand_zug(kamera, cx, cy, mx, my, pts, True)
                if dist is None or dist > tol:
                    continue
                key = (round(dist, 1), G.v_dot(w, d2))        # nearer outline, then more frontal
                if cand is None or key < cand[0]:
                    cand = (key, k, e, pts)
    if cand is None:
        return None
    return cand[1], cand[2], cand[3]


def punkt_auf_ebene(kamera, cx, cy, mx, my, ebene, raster=None):
    """Local plane coordinates (x, y) under the screen point (grid snapped) or None."""
    o, d = kamera.strahl(mx, my, cx, cy)
    p = G.strahl_auf_ebene(ebene, o, d)
    if p is None:
        return None
    if raster and raster > 0:
        p = (round(p[0] / raster) * raster, round(p[1] / raster) * raster)
    return p


def _zug_fang(zug, geschlossen, out):
    """End points + edge midpoints of a short polyline (round shapes: nothing)."""
    pts = list(zug)
    if len(pts) > 24:
        return
    for p in pts:
        out.append((p, "end"))
    kanten = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if geschlossen and len(pts) > 2 else [])
    for a, b in kanten:
        out.append((((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2), "mitte"))


def _kreis_fang(c, r, u, v, out):
    out.append((c, "zentrum"))
    for sx, sy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        out.append(((c[0] + r * (sx * u[0] + sy * v[0]), c[1] + r * (sx * u[1] + sy * v[1]),
                     c[2] + r * (sx * u[2] + sy * v[2])), "end"))


def _el_fang(el, out):
    if isinstance(el, Bemassung3D):
        return
    if isinstance(el, Skizze3D):
        if el.form == "kreis" and len(el.daten) >= 3:
            u, v, _w = G.ebene_basis(el.ebene)
            c = G.ebene_punkt(el.ebene, el.daten[0], el.daten[1])
            _kreis_fang(c, float(el.daten[2]), u, v, out)
        else:
            _zug_fang(el.zug3(), True, out)
        return
    if isinstance(el, Kreis):
        _kreis_fang((el.cx, el.cy, 0.0), el.r, (1, 0, 0), (0, 1, 0), out)
        return
    if isinstance(el, Bogen):
        out.append(((el.cx, el.cy, 0.0), "zentrum"))
        bp = bogen_punkte(el.cx, el.cy, el.r, el.start, el.ende, 2)
        for x, y in (bp[0], bp[-1]):
            out.append(((x, y, 0.0), "end"))
        return
    if isinstance(el, Ellipse):
        out.append(((el.cx, el.cy, 0.0), "zentrum"))
        return
    if isinstance(el, ZUSAMMENGESETZT):
        for k in el.aufgeloest():
            _el_fang(k, out)
        return
    for zug, closed in flache_zuege(el):
        _zug_fang([(x, y, 0.0) for x, y in zug], closed, out)


def fang_kandidaten(elemente):
    """Snap candidates [(3D point, kind)] with kind end / mitte / zentrum."""
    out = []
    for _el, nz in koerper_netze(elemente):
        if len(nz.punkte) > 24:                       # round body: only the cap centres
            zs = [p[2] for p in nz.punkte]
            z0, z1 = min(zs), max(zs)
            for zz in (z0, z1):
                ring = [p for p in nz.punkte if abs(p[2] - zz) < 1e-6]
                if ring:
                    out.append(((sum(p[0] for p in ring) / len(ring),
                                 sum(p[1] for p in ring) / len(ring), zz), "zentrum"))
            continue
        for p in nz.punkte:
            out.append((p, "end"))
        for i, j in nz.kanten:
            a, b = nz.punkte[i], nz.punkte[j]
            out.append((((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2), "mitte"))
    for el in elemente:
        if not ist_3d(el):
            _el_fang(el, out)
    return out


def fang_suche(elemente, kamera, cx, cy, mx, my, tol=12.0, filt=None):
    """Nearest snap candidate within `tol` pixels -> (point, kind) or None.
    Centres win over end points, end points over midpoints on a tie."""
    rang = {"zentrum": 0, "end": 1, "mitte": 2}
    best, bw = None, None
    for p, art in fang_kandidaten(elemente):
        if filt is not None and not filt(p):
            continue
        q = kamera.proj(p, cx, cy)
        if q is None:
            continue
        d = math.hypot(q[0] - mx, q[1] - my)
        if d > tol:
            continue
        w = (round(d / 4.0), rang.get(art, 3), d)
        if bw is None or w < bw:
            best, bw = (p, art), w
    return best


def fang_punkt(elemente, kamera, cx, cy, mx, my, tol=12.0):
    """Nearest snap point of the scene within `tol` pixels (point only)."""
    r = fang_suche(elemente, kamera, cx, cy, mx, my, tol)
    return r[0] if r else None


def host_finden(elemente, ebene, punkt=None):
    """Body whose face lies in the work plane `ebene`. With `punkt` (local plane point,
    e.g. the sketch centre) the body whose face contains that point wins, so two bodies
    with faces in the same plane are told apart; otherwise the first match."""
    u, v, w = G.ebene_basis(ebene)
    erste = None
    for el in elemente:
        if not ist_3d(el):
            continue
        for k in el.koerper():
            if k.art != "prisma":
                continue
            nz = k.netz()
            zen = k.zentrum3()
            for f in nz.flaechen:
                pts = [nz.punkte[i] for i in f]
                e2 = G.ebene_von_flaeche(pts, zen)
                if e2 is None:
                    continue
                w2 = G.ebene_basis(e2)[2]
                if G.v_dot(w, w2) < 0.999:
                    continue
                if abs(G.v_dot(G.v_sub(tuple(ebene[:3]), tuple(e2[:3])), w2)) > 1e-3:
                    continue
                if erste is None:
                    erste = k
                if punkt is None:
                    return k
                wp = G.ebene_punkt(ebene, punkt[0], punkt[1])
                lok = [G.ebene_lokal(ebene, p) for p in pts]
                if G.punkt_in_polygon(G.ebene_lokal(ebene, wp)[0], G.ebene_lokal(ebene, wp)[1],
                                      [(q[0], q[1]) for q in lok]):
                    return k
    return erste


def skizze_in_ausschnitt(elemente, skizze, tiefe=None):
    """Cuts the sketch into the body it lies on (hole / pocket); True if done."""
    prof = skizze.profil()
    mitte = (sum(p[0] for p in prof) / len(prof), sum(p[1] for p in prof) / len(prof)) if prof else None
    host = host_finden(elemente, skizze.ebene, mitte)
    if host is None or len(prof) < 3:
        return False
    host.ausschnitt_hinzufuegen(skizze.ebene, prof, tiefe, skizze.rund())
    for i, e in enumerate(elemente):
        if e is skizze:
            del elemente[i]
            break
    return True


def extrusion_abschliessen(elemente, koerper):
    """After pulling a sketch downwards (negative height) the prism becomes a
    pocket of the body it was sitting on. True if converted."""
    if not isinstance(koerper, Koerper3D) or not koerper.ebene or koerper.hoehe >= -1e-9:
        return False
    pr = koerper.profil
    mitte = (sum(p[0] for p in pr) / len(pr), sum(p[1] for p in pr) / len(pr)) if pr else None
    host = host_finden([e for e in elemente if e is not koerper], koerper.ebene, mitte)
    if host is None:
        return False
    host.ausschnitt_hinzufuegen(koerper.ebene, koerper.profil, abs(koerper.hoehe), koerper.rund)
    for i, e in enumerate(elemente):
        if e is koerper:
            del elemente[i]
            break
    return True


# --------------------------------------------------------------------------
# Dimensions of a body (size editing)
# --------------------------------------------------------------------------
def _profil_art(k):
    pr = k.profil
    if len(pr) == 4:
        xs = sorted(set(round(p[0], 6) for p in pr)); ys = sorted(set(round(p[1], 6) for p in pr))
        if len(xs) == 2 and len(ys) == 2:
            return "rechteck"
    if k.rund and len(pr) >= 8:
        return "kreis"
    return "frei"


def parameter(el):
    """[(key, value_mm)] that can be edited for a body / sketch; [] if none."""
    if isinstance(el, Koerper3D):
        if el.art == "kugel" and el.kugel:
            return [("radius", el.kugel[3])]
        art = _profil_art(el)
        out = []
        if art == "rechteck":
            xs = [p[0] for p in el.profil]; ys = [p[1] for p in el.profil]
            out += [("breite", max(xs) - min(xs)), ("tiefe", max(ys) - min(ys))]
        elif art == "kreis":
            cx = sum(p[0] for p in el.profil) / len(el.profil)
            cy = sum(p[1] for p in el.profil) / len(el.profil)
            out.append(("radius", max(math.hypot(p[0] - cx, p[1] - cy) for p in el.profil)))
        else:
            out.append(("faktor", 100.0))
        if el.art in ("prisma", "pyramide"):
            out.append(("hoehe", abs(el.hoehe)))
        return out
    if isinstance(el, Skizze3D):
        d = el.daten
        if el.form == "kreis" and len(d) >= 3:
            return [("radius", d[2])]
        if el.form == "rechteck" and len(d) >= 4:
            return [("breite", abs(d[2] - d[0])), ("tiefe", abs(d[3] - d[1]))]
    return []


def parameter_setzen(el, par):
    """Applies the values of `par` (key -> mm); bodies keep their lower left corner /
    centre. Returns True if something changed."""
    if isinstance(el, Skizze3D):
        d = el.daten
        if el.form == "kreis" and "radius" in par and par["radius"] > 0:
            d[2] = par["radius"]
            return True
        if el.form == "rechteck" and len(d) >= 4:
            x1, x2 = sorted((d[0], d[2])); y1, y2 = sorted((d[1], d[3]))
            w = par.get("breite", x2 - x1); t = par.get("tiefe", y2 - y1)
            if w <= 0 or t <= 0:
                return False
            el.daten = [x1, y1, x1 + w, y1 + t]
            return True
        return False
    if not isinstance(el, Koerper3D):
        return False
    ok = False
    if el.art == "kugel" and el.kugel and par.get("radius", 0) > 0:
        el.kugel = (el.kugel[0], el.kugel[1], el.kugel[2], par["radius"])
        ok = True
    elif el.profil:
        art = _profil_art(el)
        xs = [p[0] for p in el.profil]; ys = [p[1] for p in el.profil]
        fx = fy = 1.0
        ax, ay = min(xs), min(ys)
        if art == "rechteck":
            w0, t0 = max(xs) - min(xs), max(ys) - min(ys)
            fx = par.get("breite", w0) / w0 if w0 > 1e-12 else 1.0
            fy = par.get("tiefe", t0) / t0 if t0 > 1e-12 else 1.0
        elif art == "kreis":
            ax = sum(xs) / len(xs); ay = sum(ys) / len(ys)
            r0 = max(math.hypot(p[0] - ax, p[1] - ay) for p in el.profil)
            fx = fy = par.get("radius", r0) / r0 if r0 > 1e-12 else 1.0
        else:
            ax = sum(xs) / len(xs); ay = sum(ys) / len(ys)
            fx = fy = par.get("faktor", 100.0) / 100.0
        if fx > 0 and fy > 0 and (abs(fx - 1) > 1e-12 or abs(fy - 1) > 1e-12):
            el.profil = [(ax + (x - ax) * fx, ay + (y - ay) * fy) for (x, y) in el.profil]
            if el.spitze:
                el.spitze = (ax + (el.spitze[0] - ax) * fx, ay + (el.spitze[1] - ay) * fy)
            ok = True
    if el.art in ("prisma", "pyramide") and par.get("hoehe", 0) > 0:
        el.hoehe = math.copysign(par["hoehe"], el.hoehe if el.hoehe else 1.0)
        ok = True
    return ok


# --------------------------------------------------------------------------
# 3D view inside a layout viewport
# --------------------------------------------------------------------------
def vp_ansicht_setzen(vp, elemente, yaw, pitch, persp=False):
    """Switches viewport `vp` to the 3D wireframe view and fits it to the model."""
    k = G.Kamera(yaw=yaw, pitch=pitch, perspektive=persp)
    pts = szene_punkte(elemente)
    if pts:
        k.anpassen(pts, vp.breite, vp.hoehe, rand=max(2.0, min(vp.breite, vp.hoehe) * 0.05))
        vp.zoom = k.skala
        vp.modell_zentrum_x, vp.modell_zentrum_y = k.ziel[0], k.ziel[1]
        zielz, abstand = k.ziel[2], k.abstand
    else:
        zielz, abstand = 0.0, 1500.0
    verdeckt = bool((vp.ansicht3d or {}).get("verdeckt"))    # setting stays when the view changes
    vp.ansicht3d = {"yaw": float(yaw), "pitch": float(pitch), "persp": bool(persp),
                    "zielz": float(zielz), "abstand": float(abstand)}
    if verdeckt:
        vp.ansicht3d["verdeckt"] = True


def vp_kamera(vp, skala):
    a = vp.ansicht3d or {}
    return G.Kamera(yaw=a.get("yaw", -45.0), pitch=a.get("pitch", 35.264),
                    ziel=(vp.modell_zentrum_x, vp.modell_zentrum_y, a.get("zielz", 0.0)),
                    abstand=a.get("abstand", 1500.0), skala=skala,
                    perspektive=bool(a.get("persp")))


def szene_segmente(elemente, kamera, cx, cy, sichtbar=None, verdeckt=False, cache=None, aufloesung=1.0):
    """Projected wireframe of the scene: ([(element, ((x1, y1), (x2, y2))...)], [(element, (x, y), text)]).
    verdeckt=True: only the visible edges of the 3D bodies (hidden-line removal, no dashed lines)."""
    linien, texte = [], []
    if verdeckt:
        sicht_el = [el for el in elemente if sichtbar is None or sichtbar(el)]
        paare, offen = koerper_netze_offen(sicht_el)
        f = float(aufloesung)            # PDF (mm): compute magnified, so the pixel tolerances fit
        if f != 1.0:
            k2 = copy.copy(kamera)
            k2.skala = kamera.skala * f
            erg = verdeckt_ergebnis(paare, offen, k2, cx * f, cy * f, cache) if paare else {}
        else:
            erg = verdeckt_ergebnis(paare, offen, kamera, cx, cy, cache) if paare else {}
        fertig = set()
        for el, _nz in paare:
            if id(el) in fertig:
                continue
            fertig.add(id(el))
            for pl in erg.get(id(el), ([], []))[0]:
                linien.extend((el, ((a[0] / f, a[1] / f), (b[0] / f, b[1] / f)))
                              for a, b in zip(pl, pl[1:]))
    for el in elemente:
        if sichtbar is not None and not sichtbar(el):
            continue
        if ist_3d(el):
            if verdeckt:
                continue
            for nz in el.netze():
                for (i, j) in nz.kanten:
                    seg = kamera.proj_segment(nz.punkte[i], nz.punkte[j], cx, cy)
                    if seg:
                        linien.append((el, seg))
            continue
        for zug, geschlossen in zuege3(el):
            pts = list(zug) + ([zug[0]] if geschlossen and len(zug) > 2 else [])
            for a, b in zip(pts, pts[1:]):
                seg = kamera.proj_segment(a, b, cx, cy)
                if seg:
                    linien.append((el, seg))
        if isinstance(el, Bemassung3D):
            q = kamera.proj(el.text_pos3(), cx, cy)
            if q:
                texte.append((el, (q[0], q[1]), el.wert_text()))
        elif isinstance(el, Text3D) and el.ebene is None:
            q = kamera.proj(el.p, cx, cy)
            if q:
                texte.append((el, (q[0], q[1]), el.inhalt))
    return linien, texte


def clip_segment(seg, rect):
    """Liang-Barsky: segment clipped to rect (x1, y1, x2, y2) or None."""
    (x0, y0), (x1, y1) = seg
    xmin, ymin, xmax, ymax = rect
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    return ((x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy))


# ============================================================
# Stretch (command STRECKEN in 3D)
# ============================================================
def _teile_flach(elemente):
    out = []
    for el in elemente:
        if isinstance(el, Gruppe3D):
            out.extend(_teile_flach(el.teile))
        else:
            out.append(el)
    return out


def auswahl_bbox3(elemente):
    bs = [b for b in (t.bbox3() for t in _teile_flach(elemente) if hasattr(t, "bbox3")) if b]
    if not bs:
        return None
    return (min(b[0] for b in bs), min(b[1] for b in bs), min(b[2] for b in bs),
            max(b[3] for b in bs), max(b[4] for b in bs), max(b[5] for b in bs))


def _koerper_dehnen(k, i, lo, hi, nlo, nhi):
    """Resizes the extent [lo, hi] of the body `k` along axis i to [nlo, nhi].
    -> False if this kind of body cannot be stretched (work plane, merged body, sphere,
    cut-outs)."""
    if k.art not in ("prisma", "pyramide") or k.ebene or k.ausschnitte:
        return False
    if hi - lo < 1e-9 or nhi - nlo < 1e-6:
        return False
    if i == 2:
        if k.hoehe >= 0:
            k.z0, k.hoehe = nlo, nhi - nlo
        else:
            k.z0, k.hoehe = nhi, -(nhi - nlo)
        return True
    f = (nhi - nlo) / (hi - lo)

    def m(u):
        return nlo + (u - lo) * f

    k.profil = [((m(x), y) if i == 0 else (x, m(y))) for (x, y) in k.profil]
    if k.spitze:
        k.spitze = (m(k.spitze[0]), k.spitze[1]) if i == 0 else (k.spitze[0], m(k.spitze[1]))
    k.loecher = [((m(x), y, r, t) if i == 0 else (x, m(y), r, t)) for (x, y, r, t) in k.loecher]
    return True


def strecken(elemente, i, seite, delta, tol=None, gross=0.5):
    """Stretches 3D objects along axis i (0 = X, 1 = Y, 2 = Z): the face of the
    selection on `seite` (+1 = maximum side, -1 = minimum side) moves by `delta`.
    Parts that reach the moving face (within `tol`, default 1 % of the extent, at least 5 mm) and are large along the axis (>= `gross` of the whole
    extent, e.g. carcass or door) change their size, small parts there (rails, handles ...)
    move along, all other parts stay. -> (stretched, moved, unchanged)"""
    teile = _teile_flach(elemente)
    bb = auswahl_bbox3(elemente)
    if bb is None or abs(delta) < 1e-12:
        return 0, 0, 0
    lo_g, hi_g = bb[i], bb[i + 3]
    C = hi_g if seite > 0 else lo_g
    gesamt = max(hi_g - lo_g, 1e-9)
    if tol is None:                  # parts slightly set back (door, side panels) still count
        tol = max(5.0, 0.01 * gesamt)
    n_dehn = n_bew = n_fest = 0
    for t in teile:
        b = t.bbox3() if hasattr(t, "bbox3") else None
        if not b:
            n_fest += 1
            continue
        lo, hi = b[i], b[i + 3]
        beruehrt = hi >= C - tol if seite > 0 else lo <= C + tol
        if not beruehrt:
            continue
        gross_genug = (hi - lo) >= gross * gesamt
        if gross_genug and isinstance(t, Koerper3D):
            nlo, nhi = (lo, hi + delta) if seite > 0 else (lo + delta, hi)
            if _koerper_dehnen(t, i, lo, hi, nlo, nhi):
                n_dehn += 1
                continue
            n_fest += 1                      # large but not stretchable: stays
            continue
        if hasattr(t, "verschieben"):
            d = [0.0, 0.0, 0.0]
            d[i] = delta
            t.verschieben(*d)
            n_bew += 1
        else:
            n_fest += 1
    return n_dehn, n_bew, n_fest
