# -*- coding: utf-8 -*-
"""
katiecad/ui/menuleiste.py - Own menu bar for Linux/X11 and Windows (MIT).

Why: the native Tk menu bar grabs mouse and keyboard. On X11/XWayland
(GNOME) this grab is not honoured: after switching to another application
the open menu stays on screen on top of the foreign window. This menu bar
has no grab; it simply closes when the window loses the focus or when the
user clicks elsewhere. On Windows it replaces the native bar, which is always
white and cannot follow the colour scheme.

The menus are still ordinary (never posted) tk.Menu objects used as data
model: this class only reads their entries (label, accelerator, state,
check marks) and calls `menu.invoke(index)`.
"""

import tkinter as tk
import tkinter.font as tkfont


class _Pop:
    """One drop-down (or sub-menu) window with its rows."""
    __slots__ = ("pop", "zeilen", "aktiv", "ebene")

    def __init__(self, pop, ebene):
        self.pop, self.zeilen, self.aktiv, self.ebene = pop, [], None, ebene


class MenuLeiste(tk.Frame):
    def __init__(self, parent, bg, fg, aktiv_bg, aktiv_fg, sperr_fg="#6b5c8a"):
        super().__init__(parent, bg=bg, bd=0, highlightthickness=0)
        self._bg, self._fg = bg, fg
        self._abg, self._afg = aktiv_bg, aktiv_fg
        self._sperr = sperr_fg
        self._eintraege = []           # [(label_widget, tk.Menu)]
        self._offen = None             # index of the open menu
        self._stapel = []              # open windows: [drop-down, sub-menu, sub-sub-menu ...]
        self._cache = {}               # index -> _Pop: built once
        self._subcache = {}            # str(tk.Menu) -> _Pop of a sub-menu
        try:
            self._font = tkfont.nametofont("TkMenuFont")
        except tk.TclError:
            self._font = tkfont.nametofont("TkDefaultFont")
        top = self.winfo_toplevel()
        top.bind("<FocusOut>", self._fokus_aus, add="+")
        top.bind("<Unmap>", lambda e: self.schliessen(), add="+")
        top.bind("<Configure>", self._fenster_bewegt, add="+")
        top.bind("<F10>", self._f10, add="+")
        top.bind_all("<ButtonPress>", self._klick, add="+")
        top.bind_all("<Key>", self._taste, add="+")

    # ------------------------------------------------------------
    def farben_setzen(self, bg, fg, aktiv_bg, aktiv_fg, sperr_fg=None):
        """New colours (colour scheme change); takes effect with the next setze()."""
        self._bg, self._fg, self._abg, self._afg = bg, fg, aktiv_bg, aktiv_fg
        if sperr_fg:
            self._sperr = sperr_fg
        self.config(bg=bg)

    def setze(self, eintraege):
        """eintraege: [(label, tk.Menu)] - rebuilds the bar."""
        self.schliessen()
        for w, _m in self._eintraege:
            w.destroy()
        for p in list(self._cache.values()) + list(self._subcache.values()):
            try:
                p.pop.destroy()
            except tk.TclError:
                pass
        self._cache = {}
        self._subcache = {}
        self._eintraege = []
        for i, (label, menu) in enumerate(eintraege):
            w = tk.Label(self, text=label, bg=self._bg, fg=self._fg,
                         font=self._font, padx=8, pady=3, bd=0)
            w.pack(side=tk.LEFT)
            w.bind("<Button-1>", lambda e, i=i: self._umschalten(i))
            w.bind("<Enter>", lambda e, i=i: self._ueber(i))
            self._eintraege.append((w, menu))
        self.after(200, self._vorbauen)

    def _vorbauen(self):
        """Builds all drop-downs once in the background (opening is then
        instant); they are only refreshed when opened."""
        for i in range(len(self._eintraege)):
            if i not in self._cache:
                try:
                    self._cache[i] = self._pop_bauen(self._eintraege[i][1], 0)
                except tk.TclError:
                    return

    def _faerben(self):
        for i, (w, _m) in enumerate(self._eintraege):
            if i == self._offen:
                w.config(bg=self._abg, fg=self._afg)
            else:
                w.config(bg=self._bg, fg=self._fg)

    # ------------------------------------------------------------
    def _umschalten(self, i):
        if self._offen == i:
            self.schliessen()
        else:
            self.oeffnen(i)

    def _ueber(self, i):
        if self._offen is not None and self._offen != i:
            self.oeffnen(i)

    def oeffnen(self, i, tastatur=False):
        self._stapel_schliessen(0)
        self._offen = i
        self._faerben()
        w, menu = self._eintraege[i]
        if i not in self._cache:
            self._cache[i] = self._pop_bauen(menu, 0)
        p = self._cache[i]
        p.aktiv = None
        self._auffrischen(p)
        self._anzeigen(p, w.winfo_rootx(), w.winfo_rooty() + w.winfo_height())
        self._stapel = [p]
        if tastatur:
            self._weiter(+1)

    def _anzeigen(self, p, x, y, links_von=None):
        """Shows window p at (x, y); stays on the screen. links_von = x where the window
        goes to the left of its parent if there is no room on the right."""
        br, ho = p.pop.winfo_reqwidth(), p.pop.winfo_reqheight()
        sb, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if links_von is not None and x + br > sb:
            x = links_von - br
        x = max(0, min(x, sb - br))
        y = max(0, min(y, sh - ho))
        p.pop.geometry("+%d+%d" % (x, y))
        p.pop.deiconify()
        p.pop.lift()

    def _pop_bauen(self, menu, ebene):
        pop = tk.Toplevel(self)
        pop.withdraw()
        pop.overrideredirect(True)
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass
        rahmen = tk.Frame(pop, bg=self._fg, bd=0)
        rahmen.pack(fill=tk.BOTH, expand=True)
        innen = tk.Frame(rahmen, bg=self._bg, bd=0)
        innen.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        p = _Pop(pop, ebene)
        try:
            ende = menu.index("end")
        except tk.TclError:
            ende = None
        if ende is not None:
            for idx in range(ende + 1):
                self._zeile(innen, menu, idx, p)
        pop.update_idletasks()
        return p

    def _auffrischen(self, p):
        """Takes over state and check marks of the menu entries."""
        for nr, z in enumerate(p.zeilen):
            zeile, idx, _alt, (l1, l2, l3), menu = z
            typ = menu.type(idx)
            try:
                state = menu.entrycget(idx, "state")
            except tk.TclError:
                state = "normal"
            marke = ""
            if typ in ("checkbutton", "radiobutton"):
                try:
                    var = menu.entrycget(idx, "variable")
                    wert = menu.tk.globalgetvar(str(var))
                    soll = menu.entrycget(idx, "onvalue" if typ == "checkbutton"
                                          else "value")
                    if str(wert) == str(soll):
                        marke = "\u2713"
                except tk.TclError:
                    pass
            fg = self._fg if state != "disabled" else self._sperr
            for wdg in (zeile, l1, l2, l3):
                wdg.config(bg=self._bg)
            l1.config(text=marke, fg=fg)
            l2.config(fg=fg)
            l3.config(fg=fg)
            p.zeilen[nr] = (zeile, idx, state, (l1, l2, l3), menu)

    def _zeile(self, innen, menu, idx, p):
        typ = menu.type(idx)
        if typ == "tearoff":
            return
        if typ == "separator":
            tk.Frame(innen, bg=self._fg, height=1).pack(
                fill=tk.X, padx=2, pady=3)
            return
        try:
            text = menu.entrycget(idx, "label")
        except tk.TclError:
            text = ""
        try:
            accel = menu.entrycget(idx, "accelerator")
        except tk.TclError:
            accel = ""
        try:
            state = menu.entrycget(idx, "state")
        except tk.TclError:
            state = "normal"
        marke = ""
        if typ in ("checkbutton", "radiobutton"):
            try:
                var = menu.entrycget(idx, "variable")
                wert = menu.tk.globalgetvar(str(var))
                soll = menu.entrycget(idx, "onvalue" if typ == "checkbutton"
                                      else "value")
                if str(wert) == str(soll):
                    marke = "\u2713"
            except tk.TclError:
                pass
        zeile = tk.Frame(innen, bg=self._bg, bd=0)
        zeile.pack(fill=tk.X)
        fg = self._fg if state != "disabled" else self._sperr
        l1 = tk.Label(zeile, text=marke, bg=self._bg, fg=fg, font=self._font,
                      width=2, anchor="w")
        l2 = tk.Label(zeile, text=text, bg=self._bg, fg=fg, font=self._font,
                      anchor="w", padx=2, pady=3)
        l3 = tk.Label(zeile, text=accel + ("  \u25b8" if typ == "cascade" else ""),
                      bg=self._bg, fg=fg, font=self._font, anchor="e", padx=10)
        l1.pack(side=tk.LEFT)
        l3.pack(side=tk.RIGHT)
        l2.pack(side=tk.LEFT, fill=tk.X, expand=True)
        nr = len(p.zeilen)
        p.zeilen.append((zeile, idx, state, (l1, l2, l3), menu))
        for wdg in (zeile, l1, l2, l3):
            wdg.bind("<Enter>", lambda e, p=p, nr=nr: self._markieren(p, nr))
            wdg.bind("<ButtonRelease-1>", lambda e, p=p, nr=nr: self._ausloesen(p, nr))

    def _markieren(self, p, nr, mit_untermenue=True):
        if p.aktiv is not None and p.aktiv < len(p.zeilen):
            z = p.zeilen[p.aktiv]
            for w in (z[0],) + z[3]:
                w.config(bg=self._bg)
            fg = self._fg if z[2] != "disabled" else self._sperr
            for w in z[3]:
                w.config(fg=fg)
        p.aktiv = nr
        if nr is None:
            return
        z = p.zeilen[nr]
        if z[2] == "disabled":
            self._stapel_schliessen(p.ebene + 1)
            return
        for w in (z[0],) + z[3]:
            w.config(bg=self._abg)
        for w in z[3]:
            w.config(fg=self._afg)
        if mit_untermenue and self._ist_cascade(z):
            self._sub_oeffnen(p, nr)
        else:
            self._stapel_schliessen(p.ebene + 1)

    @staticmethod
    def _ist_cascade(z):
        try:
            return z[4].type(z[1]) == "cascade"
        except tk.TclError:
            return False

    def _sub_oeffnen(self, p, nr):
        """Opens the sub-menu of row nr of window p (to the right of the row)."""
        zeile, idx, _st, _w, menu = p.zeilen[nr]
        try:
            ziel = self.nametowidget(menu.entrycget(idx, "menu"))
        except (tk.TclError, KeyError):
            return
        schluessel = str(ziel)
        if (len(self._stapel) > p.ebene + 1
                and self._stapel[p.ebene + 1] is self._subcache.get(schluessel)):
            return                                   # already open
        self._stapel_schliessen(p.ebene + 1)
        sub = self._subcache.get(schluessel)
        if sub is None:
            sub = self._subcache[schluessel] = self._pop_bauen(ziel, p.ebene + 1)
        sub.ebene = p.ebene + 1
        sub.aktiv = None
        self._auffrischen(sub)
        px = p.pop.winfo_rootx()
        self._anzeigen(sub, px + p.pop.winfo_width() - 2, zeile.winfo_rooty() - 2,
                       links_von=px + 2)
        del self._stapel[p.ebene + 1:]
        self._stapel.append(sub)

    def _stapel_schliessen(self, ab):
        """Closes the sub-menus from level `ab` on (0 = everything)."""
        for p in self._stapel[ab:]:
            try:
                p.pop.withdraw()
            except tk.TclError:
                pass
        del self._stapel[ab:]

    def _ausloesen(self, p, nr):
        if nr is None or nr >= len(p.zeilen):
            return
        z = p.zeilen[nr]
        _z, idx, state, _w, menu = z
        if state == "disabled":
            return
        if self._ist_cascade(z):                     # a click opens the sub-menu
            self._markieren(p, nr)
            return
        self.schliessen()
        # after closing, so that dialogs are not blocked by the pop-up
        self.after(10, lambda: self._aufrufen(menu, idx))

    @staticmethod
    def _aufrufen(menu, idx):
        try:
            menu.invoke(idx)
        except tk.TclError:
            pass

    # ------------------------------------------------------------
    def schliessen(self):
        self._stapel_schliessen(0)
        if self._offen is not None:
            self._offen = None
            self._faerben()

    def ist_offen(self):
        return self._offen is not None

    # ------------------------------------------------------------
    def _fokus_aus(self, event):
        if self._offen is None or event.widget is not self.winfo_toplevel():
            return
        # focus moves within the application? Then it is not "away".
        self.after(80, self._fokus_pruefen)

    def _fokus_pruefen(self):
        try:
            if self.winfo_toplevel().focus_displayof() is None:
                self.schliessen()
        except tk.TclError:
            pass

    def _fenster_bewegt(self, event):
        if self._offen is None or event.widget is not self.winfo_toplevel():
            return
        self.schliessen()

    def _klick(self, event):
        if self._offen is None:
            return
        w = event.widget
        fenster = {id(p.pop) for p in self._stapel}
        try:
            while w is not None:
                if w is self or id(w) in fenster:
                    return
                w = w.master
        except Exception:
            return
        self.schliessen()

    def _f10(self, event=None):
        if self._eintraege and self._offen is None:
            self.oeffnen(0, tastatur=True)
            return "break"

    def _weiter(self, richtung):
        if not self._stapel:
            return
        p = self._stapel[-1]
        n = len(p.zeilen)
        if not n:
            return
        nr = p.aktiv
        for _ in range(n):
            if nr is None:
                nr = 0 if richtung > 0 else n - 1
            else:
                nr = (nr + richtung) % n
            if p.zeilen[nr][2] != "disabled":
                self._markieren(p, nr, mit_untermenue=False)
                return

    def _taste(self, event):
        if self._offen is None or not self._stapel:
            return
        k = event.keysym
        p = self._stapel[-1]
        if k == "Escape":
            if len(self._stapel) > 1:
                self._stapel_schliessen(len(self._stapel) - 1)
            else:
                self.schliessen()
        elif k == "Down":
            self._weiter(+1)
        elif k == "Up":
            self._weiter(-1)
        elif k == "Right":
            z = p.zeilen[p.aktiv] if p.aktiv is not None and p.aktiv < len(p.zeilen) else None
            if z is not None and z[2] != "disabled" and self._ist_cascade(z):
                self._sub_oeffnen(p, p.aktiv)
                if len(self._stapel) > p.ebene + 1:
                    self._weiter(+1)
            elif len(self._stapel) == 1:
                self.oeffnen((self._offen + 1) % len(self._eintraege), tastatur=True)
        elif k == "Left":
            if len(self._stapel) > 1:
                self._stapel_schliessen(len(self._stapel) - 1)
            else:
                self.oeffnen((self._offen - 1) % len(self._eintraege), tastatur=True)
        elif k in ("Return", "KP_Enter"):
            if p.aktiv is not None:
                z = p.zeilen[p.aktiv]
                if self._ist_cascade(z) and z[2] != "disabled":
                    self._sub_oeffnen(p, p.aktiv)
                    if len(self._stapel) > p.ebene + 1:
                        self._weiter(+1)
                else:
                    self._ausloesen(p, p.aktiv)
        else:
            return
        return "break"
