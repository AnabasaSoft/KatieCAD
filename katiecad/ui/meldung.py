# -*- coding: utf-8 -*-
"""
katiecad/ui/meldung.py - Message boxes in the design of the program (MIT).

Drop-in replacement for the functions of tkinter.messagebox that KatieCAD uses
(showinfo, showwarning, showerror, askyesno, askyesnocancel, askokcancel). The
native boxes ignore the colour scheme; these follow it. Same arguments
(title, message, parent=..., default=...) and same return values.
"""
import tkinter as tk
from tkinter import ttk

from katiecad.common.i18n import tr
from katiecad.model.core import FARBEN, UI_SCHRIFT

YES, NO, OK, CANCEL = "yes", "no", "ok", "cancel"
_SYMBOLE = {"info": ("i", "cyan"), "frage": ("?", "cyan"),
            "warnung": ("!", "orange"), "fehler": ("✕", "rot")}


def _wurzel(parent):
    if parent is not None:
        try:
            return parent.winfo_toplevel()
        except tk.TclError:
            pass
    return getattr(tk, "_default_root", None)


def _dialog(titel, text, art, tasten, vorgabe, abbruch, parent=None):
    """tasten: [(value, label)] left to right. Returns the value of the pressed button
    (`abbruch` for Esc / closing the window)."""
    wurzel = _wurzel(parent)
    if wurzel is None:                      # no window at all: native fallback
        from tkinter import messagebox as _mb
        return {"info": _mb.showinfo, "warnung": _mb.showwarning,
                "fehler": _mb.showerror}.get(art, _mb.showinfo)(titel, text) \
            if art != "frage" else abbruch
    dlg = tk.Toplevel(wurzel)
    dlg.title(str(titel))
    dlg.configure(bg=FARBEN["bg_mittel"])
    dlg.resizable(False, False)
    try:
        if wurzel.winfo_viewable():
            dlg.transient(wurzel)
    except tk.TclError:
        pass
    ergebnis = {"wert": abbruch}

    def schliessen(wert):
        ergebnis["wert"] = wert
        try:
            dlg.grab_release()
        except tk.TclError:
            pass
        dlg.destroy()

    kopf = tk.Frame(dlg, bg=FARBEN["bg_mittel"], padx=22, pady=20)
    kopf.pack(fill=tk.BOTH, expand=True)
    zeichen, farbe = _SYMBOLE.get(art, _SYMBOLE["info"])
    cv = tk.Canvas(kopf, width=44, height=44, bg=FARBEN["bg_mittel"], highlightthickness=0)
    cv.create_oval(3, 3, 41, 41, outline=FARBEN[farbe], width=2)
    cv.create_text(22, 23, text=zeichen, fill=FARBEN[farbe], font=(UI_SCHRIFT[0] if isinstance(
        UI_SCHRIFT, tuple) else UI_SCHRIFT, 17, "bold"))
    cv.pack(side=tk.LEFT, anchor="n", padx=(0, 16))
    tk.Label(kopf, text=str(text), bg=FARBEN["bg_mittel"], fg=FARBEN["text"],
             font=(UI_SCHRIFT[0] if isinstance(UI_SCHRIFT, tuple) else UI_SCHRIFT, 10),
             justify=tk.LEFT, anchor="w", wraplength=420).pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Frame(dlg, bg=FARBEN["rand"], height=1).pack(fill=tk.X)
    fuss = tk.Frame(dlg, bg=FARBEN["bg_mittel"], padx=18, pady=12)
    fuss.pack(fill=tk.X)
    knoepfe = {}
    for wert, label in reversed(tasten):
        b = ttk.Button(fuss, text=label, width=12, command=lambda w=wert: schliessen(w))
        b.pack(side=tk.RIGHT, padx=(8, 0))
        knoepfe[wert] = b

    def fokus_wechseln(richtung):
        werte = [w for w, _l in tasten]
        aktuell = dlg.focus_get()
        for i, w in enumerate(werte):
            if knoepfe[w] is aktuell:
                knoepfe[werte[(i + richtung) % len(werte)]].focus_set()
                return
        knoepfe[werte[0]].focus_set()

    dlg.bind("<Return>", lambda e: schliessen(vorgabe if not isinstance(dlg.focus_get(), ttk.Button)
                                              else next((w for w, b in knoepfe.items()
                                                         if b is dlg.focus_get()), vorgabe)))
    dlg.bind("<KP_Enter>", lambda e: schliessen(vorgabe))
    dlg.bind("<Escape>", lambda e: schliessen(abbruch))
    dlg.bind("<Left>", lambda e: fokus_wechseln(-1))
    dlg.bind("<Right>", lambda e: fokus_wechseln(+1))
    if any(w == YES for w, _l in tasten):             # J / Y = yes, N = no
        for k in ("j", "J", "y", "Y"):
            dlg.bind(f"<{k}>", lambda e: schliessen(YES))
        if any(w == NO for w, _l in tasten):
            for k in ("n", "N"):
                dlg.bind(f"<{k}>", lambda e: schliessen(NO))
    dlg.protocol("WM_DELETE_WINDOW", lambda: schliessen(abbruch))
    dlg.update_idletasks()
    try:                                              # centred over the main window
        x = wurzel.winfo_rootx() + (wurzel.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = wurzel.winfo_rooty() + (wurzel.winfo_height() - dlg.winfo_reqheight()) // 3
        dlg.geometry("+%d+%d" % (max(0, x), max(0, y)))
    except tk.TclError:
        pass
    try:
        dlg.grab_set()
    except tk.TclError:
        pass
    knoepfe.get(vorgabe, next(iter(knoepfe.values()))).focus_set()
    wurzel.wait_window(dlg)
    return ergebnis["wert"]


def showinfo(title=None, message=None, parent=None, **kw):
    return _dialog(title, message, "info", [(OK, tr("dlg.ok"))], OK, OK, parent)


def showwarning(title=None, message=None, parent=None, **kw):
    return _dialog(title, message, "warnung", [(OK, tr("dlg.ok"))], OK, OK, parent)


def showerror(title=None, message=None, parent=None, **kw):
    return _dialog(title, message, "fehler", [(OK, tr("dlg.ok"))], OK, OK, parent)


def askyesno(title=None, message=None, parent=None, default=YES, **kw):
    return _dialog(title, message, "frage", [(YES, tr("dlg.ja")), (NO, tr("dlg.nein"))],
                   default, NO, parent) == YES


def askokcancel(title=None, message=None, parent=None, default=OK, **kw):
    return _dialog(title, message, "frage", [(OK, tr("dlg.ok")), (CANCEL, tr("dlg.abbrechen"))],
                   default, CANCEL, parent) == OK


def askyesnocancel(title=None, message=None, parent=None, default=YES, **kw):
    w = _dialog(title, message, "frage",
                [(YES, tr("dlg.ja")), (NO, tr("dlg.nein")), (CANCEL, tr("dlg.abbrechen"))],
                default, CANCEL, parent)
    return True if w == YES else (False if w == NO else None)
