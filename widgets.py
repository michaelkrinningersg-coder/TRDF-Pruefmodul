"""
TRDF-Pruefmodul - Wiederverwendbare GUI-Bausteine
=================================================

Uebernommen aus LabDoku Desktop (das sie seinerseits aus MessKomplize hat),
damit die Werkzeuge dieselbe Handschrift haben: abgerundete Buttons,
verzoegerte Tooltips, Icon-Handling und ein gemeinsames Farbschema.

Bewusst unveraendert gehalten - Aenderungen hier sollten in allen drei
Anwendungen gleich passieren, sonst laufen die Oberflaechen auseinander.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk


# --- Zentrales Farb- und Stilschema (angelehnt an LabDoku-Web) ------------
class Style:
    BG = "#f1f5f9"           # slate-100  (App-Hintergrund)
    CARD = "#ffffff"          # Karten/Panels
    HEADER = "#0f172a"        # slate-900  (Header dunkel)
    HEADER_FG = "#f8fafc"
    TEXT = "#1e293b"          # slate-800
    MUTED = "#64748b"         # slate-500
    BORDER = "#cbd5e1"        # slate-300
    ACCENT = "#2563eb"        # blue-600   (Primaeraktion)
    ACCENT_DARK = "#1d4ed8"
    ACCENT_FG = "#ffffff"

    # Zustandsfarben
    OK = "#16a34a"                # gruen  (bestaetigt)
    WARN = "#b45309"              # amber  (offen, noch nicht bestaetigt)
    ERROR = "#dc2626"             # rot    (Fehler)
    WARN_BG = "#fffbeb"           # amber-50
    ERROR_BG = "#fef2f2"          # rot-50
    OK_BG = "#f0fdf4"             # gruen-50

    FONT = "Segoe UI"
    FONT_FALLBACK = "Arial"

    @classmethod
    def font(cls, size=10, weight="normal"):
        # Segoe UI ist unter Windows Standard; Tk faellt sonst automatisch
        # auf eine aehnliche Schrift zurueck.
        return (cls.FONT, size, weight)


def get_asset_path(filename):
    """Findet Assets sowohl im Skript- als auch im PyInstaller-Modus."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, filename)


def apply_window_icon(root):
    """Setzt das App-Icon (Icon.ico bevorzugt, sonst Icon.png)."""
    ico_path = get_asset_path("Icon.ico")
    png_path = get_asset_path("Icon.png")
    try:
        if os.path.exists(ico_path):
            root.iconbitmap(ico_path)
    except Exception:
        pass
    try:
        if os.path.exists(png_path):
            icon_image = tk.PhotoImage(file=png_path)
            root.iconphoto(True, icon_image)
            root._window_icon_image = icon_image  # Referenz halten
    except Exception:
        pass


class ToolTip:
    """Verzoegerter Mouseover-Hinweis (600 ms), wie in MessKomplize."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.id = self.widget.after(600, self.showtip)

    def leave(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        self.hidetip()

    def showtip(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#ffffe0",
                       relief=tk.SOLID, borderwidth=1, font=("Arial", 9))
        lbl.pack(ipadx=3, ipady=3)
        # Am rechten oder unteren Bildschirmrand nach innen ruecken - ein
        # Hinweis, der halb aus dem Bild ragt, ist halb gelesen.
        try:
            tw.update_idletasks()
            breite, hoehe = tw.winfo_reqwidth(), tw.winfo_reqheight()
            rand_x = self.widget.winfo_screenwidth() - breite - 4
            rand_y = self.widget.winfo_screenheight() - hoehe - 4
            if x > rand_x or y > rand_y:
                tw.wm_geometry(f"+{max(0, min(x, rand_x))}+"
                               f"{max(0, min(y, rand_y))}")
        except tk.TclError:
            pass

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class RoundedButton(tk.Canvas):
    """Abgerundeter Button auf Canvas-Basis (aus MessKomplize uebernommen).

    Unterstuetzt Hover-Effekt und disabled-Zustand. Farben lassen sich
    zur Laufzeit aendern.
    """

    def __init__(self, parent, command=None, text="", textvariable=None, width=160,
                 height=40, radius=12, bg=Style.ACCENT, fg=Style.ACCENT_FG,
                 hover=None, font=None, state="normal"):
        super().__init__(parent, width=width, height=height, highlightthickness=0,
                         bd=0, relief="flat", bg=parent["bg"] if "bg" in parent.keys() else Style.BG)
        self._command = command
        self._text = text
        self._textvariable = textvariable
        self._width = width
        self._height = height
        self._radius = max(6, min(radius, width // 2, height // 2))
        self._bg = bg
        self._fg = fg
        self._hover = hover or _darken(bg)
        self._font = font or Style.font(10, "bold")
        self._state = state
        self._hovering = False
        self._trace_id = None

        if self._textvariable is not None:
            self._trace_id = self._textvariable.trace_add("write", lambda *a: self._redraw())

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        # Bei Groessenaenderung (z. B. pack(fill="x")) die tatsaechliche
        # Breite uebernehmen, damit langer Text nicht abgeschnitten wird.
        self.bind("<Configure>", self._on_configure)
        self._redraw()

    def _on_configure(self, event):
        changed = False
        if event.width > 1 and event.width != self._width:
            self._width = event.width
            self._radius = max(6, min(self._radius, event.width // 2))
            changed = True
        if event.height > 1 and event.height != self._height:
            self._height = event.height
            changed = True
        if changed:
            self._redraw()

    def _on_click(self, event=None):
        if self._state != "disabled" and self._command:
            self._command()

    def _on_enter(self, event=None):
        self._hovering = True
        if self._state != "disabled":
            self.configure(cursor="hand2")
        self._redraw()

    def _on_leave(self, event=None):
        self._hovering = False
        self._redraw()

    def _current_text(self):
        if self._textvariable is not None:
            return self._textvariable.get()
        return self._text

    def _colors(self):
        if self._state == "disabled":
            return "#e2e8f0", "#94a3b8"
        if self._hovering:
            return self._hover, self._fg
        return self._bg, self._fg

    def _redraw(self):
        self.delete("all")
        fill_color, text_color = self._colors()
        w, h, r = self._width, self._height, self._radius
        points = [
            r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h,
            w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0,
        ]
        self.create_polygon(points, smooth=True, splinesteps=24,
                            fill=fill_color, outline=fill_color)
        self.create_text(w // 2, h // 2, text=self._current_text(),
                        fill=text_color, font=self._font)

    def config(self, **kwargs):
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "text" in kwargs:
            self._text = kwargs.pop("text")
        if "bg" in kwargs:
            self._bg = kwargs.pop("bg")
            self._hover = _darken(self._bg)
        if "fg" in kwargs:
            self._fg = kwargs.pop("fg")
        if "font" in kwargs:
            self._font = kwargs.pop("font")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
        if kwargs:
            super().config(**kwargs)
        self._redraw()

    configure = config

    def cget(self, key):
        """Fragt eine Eigenschaft ab - auch die, die kein Canvas kennt.

        `config(text=...)` geht, `cget("text")` ging bisher nicht: die
        Beschriftung ist gemalt und keine Canvas-Eigenschaft. Wer einen
        Knopf setzt, will ihn aber auch lesen koennen.
        """
        if key == "text":
            return self._current_text()
        if key in ("bg", "background"):
            return self._bg
        if key in ("fg", "foreground"):
            return self._fg
        if key == "state":
            return self._state
        return super().cget(key)


def maximieren(fenster):
    """Oeffnet ein Fenster so gross wie der Bildschirm.

    Unter Windows kennt Tk dafuer den Zustand "zoomed", unter X11 das
    Attribut "-zoomed"; wo beides fehlt, bleibt die Bildschirmgroesse.
    Der Reihe nach versucht, weil ein nicht unterstuetzter Weg einen
    TclError wirft und nicht etwa still nichts tut.

    Von Hand aufziehen muesste man das Fenster sonst bei jedem Lauf neu -
    und die Reiter brauchen die Breite.
    """
    fenster.update_idletasks()
    for versuch in (lambda: fenster.state("zoomed"),
                    lambda: fenster.attributes("-zoomed", True)):
        try:
            versuch()
            return
        except tk.TclError:
            continue
    fenster.geometry(f"{fenster.winfo_screenwidth()}x"
                     f"{fenster.winfo_screenheight()}+0+0")


class Klappbereich(tk.Frame):
    """Ein Kasten, der sich zusammenlegen laesst.

    Oben eine Zeile mit Dreieck und Titel, darunter der Inhalt. Ein
    Klick auf die Zeile klappt zu oder auf. Gebraucht ueberall, wo
    etwas selten angefasst wird und trotzdem Platz wegnimmt - die
    Schwellenfelder einer Pruefung etwa: man stellt sie einmal ein und
    sieht danach lieber die Tabelle.

    Zum Hineinpacken ist `inhalt` da; ob offen oder zu, sagt `offen`.
    """

    ZU = "\u25b8"      # nach rechts: hier steckt noch etwas
    AUF = "\u25be"     # nach unten: es steht darunter

    def __init__(self, eltern, titel: str, offen: bool = False,
                 bg=None, nach_dem_klappen=None, **rest):
        farbe = Style.BG if bg is None else bg
        super().__init__(eltern, bg=farbe, **rest)
        self.titel = str(titel)
        self.offen = bool(offen)
        self._nach_dem_klappen = nach_dem_klappen
        self.kopf = tk.Label(self, text=self._kopftext(), bg=farbe,
                             fg=Style.TEXT, font=Style.font(9, "bold"),
                             anchor="w", cursor="hand2", padx=2)
        self.kopf.pack(fill="x")
        self.kopf.bind("<Button-1>", lambda e: self.umschalten())
        self.inhalt = tk.Frame(self, bg=farbe)
        if self.offen:
            self.inhalt.pack(fill="x", pady=(2, 0))

    def _kopftext(self) -> str:
        return f"{self.AUF if self.offen else self.ZU}  {self.titel}"

    def umschalten(self):
        self.zeigen(not self.offen)

    def zeigen(self, offen: bool):
        """Auf- oder zuklappen - und sagen, dass es geschehen ist."""
        self.offen = bool(offen)
        if self.offen:
            self.inhalt.pack(fill="x", pady=(2, 0))
        else:
            self.inhalt.pack_forget()
        self.kopf.config(text=self._kopftext())
        if self._nach_dem_klappen is not None:
            self._nach_dem_klappen(self.offen)

    def titel_setzen(self, titel: str):
        """Den Titel aendern - er traegt oft eine Zahl mit."""
        self.titel = str(titel)
        self.kopf.config(text=self._kopftext())


def _darken(hex_color, factor=0.85):
    """Verdunkelt eine Hex-Farbe fuer Hover-Effekte."""
    try:
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def make_badge(parent, text, color, fg="#ffffff"):
    """Kleines farbiges Status-Label ("Badge")."""
    lbl = tk.Label(parent, text=text, bg=color, fg=fg,
                   font=Style.font(8, "bold"), padx=8, pady=2)
    return lbl


# --- Rollbereich ----------------------------------------------------------
# Eine Leinwand mit einem Rahmen darin und einer Rollleiste daneben: das
# Mittel, mit dem ein Fenster mehr Inhalt zeigt, als hineinpasst. Fuenf
# Stellen im Programm hatten das je eigen gebaut, und alle fuenf trugen
# denselben Fehler.
#
# Der Fehler: die beiden <Configure>-Behandlungen schaukeln sich auf. Die
# Leinwand setzt die Breite des inneren Rahmens; der Rahmen aendert
# dadurch seine Groesse und setzt den Rollbereich; der neue Rollbereich
# aendert die Rollleiste; die aendert die Breite der Leinwand - und die
# setzt wieder die Breite des Rahmens. Unter X11 laeuft sich das ein,
# unter Windows nicht: dort kam ein update() aus dieser Schleife nicht
# mehr zurueck, und der Bau blieb im Test des QP-Reiters stehen, bis
# GitHub ihn nach sechs Stunden abschnitt.
#
# Die Loesung ist nicht, eine der beiden Behandlungen weglassen - beide
# werden gebraucht. Sie ist, jede nur dann etwas tun zu lassen, wenn
# sich wirklich etwas aendert. Damit ist die Kette nach einem Durchlauf
# zu Ende, statt sich zu wiederholen.

def _zahlen(text) -> tuple:
    """Aus "0 0 300 500" die vier Zahlen - () wo nichts zu lesen ist."""
    if not text:
        return ()
    try:
        return tuple(int(float(stueck)) for stueck in str(text).split())
    except (TypeError, ValueError):
        return ()


def rollleinwand(eltern, breite: int, hoehe: int, sichtbar: int,
                 sichtbar_breit: int = 0) -> tuple:
    """Eine Leinwand zum Malen, die groesser sein darf als ihr Platz.

    Zurueck kommt (Rahmen, Leinwand). Gerollt wird, was nicht
    hineinpasst - und nur das: ein Rollbalken an einem Bild, das ganz
    zu sehen ist, sieht aus wie ein Fehler. Gestaucht wird nichts: wo
    ein Bild eine Skala hat, ist sie sein Sinn, und ein gestauchtes
    Bild zeigt eine andere Tiefe als die, die daneben steht.

    Der Unterschied zu `rollbereich`: dort rollt ein Rahmen voller
    Widgets, hier rollt das Gemalte selbst. Beides steht hier, damit
    es nicht jedes Fenster wieder selbst baut.
    """
    breite, hoehe = int(breite), int(hoehe)
    sichtbar = int(sichtbar)
    sichtbar_breit = int(sichtbar_breit) or breite
    rahmen = tk.Frame(eltern, bg=Style.BG)
    leinwand = tk.Canvas(rahmen, width=sichtbar_breit, height=sichtbar,
                         bg=Style.CARD, highlightthickness=1,
                         highlightbackground=Style.BORDER,
                         scrollregion=(0, 0, breite, hoehe))
    leinwand.grid(row=0, column=0, sticky="nw")
    if hoehe > sichtbar:
        senkrecht = ttk.Scrollbar(rahmen, orient="vertical",
                                  command=leinwand.yview)
        leinwand.configure(yscrollcommand=senkrecht.set)
        senkrecht.grid(row=0, column=1, sticky="ns")

        def rollen(ereignis, schritt=0):
            weite = schritt or (-1 if getattr(ereignis, "delta", 0) > 0
                                else 1)
            leinwand.yview_scroll(weite, "units")

        leinwand.bind("<MouseWheel>", rollen)
        leinwand.bind("<Button-4>", lambda e: rollen(e, -1))
        leinwand.bind("<Button-5>", lambda e: rollen(e, 1))
    if breite > sichtbar_breit:
        waagerecht = ttk.Scrollbar(rahmen, orient="horizontal",
                                   command=leinwand.xview)
        leinwand.configure(xscrollcommand=waagerecht.set)
        waagerecht.grid(row=1, column=0, sticky="ew")
    return rahmen, leinwand


def rollbereich(eltern, bg=None, padx=0, pady=0, rad=True, rand=0):
    """Ein rollbarer Bereich. Zurueck kommt der Rahmen zum Hineinpacken.

    `padx`/`pady` polstern innen, `rand` aussen. `rad` schaltet die
    Behandlung des Mausrads ab - manche Fenster rollen selbst, weil sie
    zuerst pruefen, ob sie ueberhaupt im Vordergrund sind.

    Am Rahmen haengen `leinwand` und `rollleiste` - fuer den Fall, dass
    der Aufrufer selbst rollen oder messen will.
    """
    farbe = Style.BG if bg is None else bg
    aussen = tk.Frame(eltern, bg=farbe)
    aussen.pack(fill="both", expand=True, padx=rand)
    leinwand = tk.Canvas(aussen, bg=farbe, highlightthickness=0)
    rolle = ttk.Scrollbar(aussen, orient="vertical", command=leinwand.yview)
    leinwand.configure(yscrollcommand=rolle.set)
    leinwand.pack(side="left", fill="both", expand=True)
    rolle.pack(side="right", fill="y")
    innen = tk.Frame(leinwand, bg=farbe, padx=padx, pady=pady)
    eintrag = leinwand.create_window((0, 0), window=innen, anchor="nw")

    def bereich_setzen(_ereignis=None):
        umriss = leinwand.bbox("all")
        if umriss is None:
            return
        if _zahlen(leinwand.cget("scrollregion")) != tuple(umriss):
            leinwand.configure(scrollregion=umriss)

    def breite_setzen(ereignis):
        vorher = _zahlen(leinwand.itemcget(eintrag, "width"))
        if vorher == (ereignis.width,):
            return
        leinwand.itemconfigure(eintrag, width=ereignis.width)

    innen.bind("<Configure>", bereich_setzen)
    leinwand.bind("<Configure>", breite_setzen)

    if rad:
        def rollen(schritt):
            # Nicht ueber den Inhalt hinaus: passt alles ins Fenster,
            # wanderte der Inhalt beim Drehen am Rad aus dem Bild,
            # obwohl es nichts zu rollen gab.
            oben, unten = leinwand.yview()
            if (schritt > 0 and unten >= 1.0) or (schritt < 0 and oben <= 0.0):
                return
            leinwand.yview_scroll(schritt, "units")

        for ziel in (leinwand, innen):
            ziel.bind("<Button-4>", lambda e: rollen(-2))
            ziel.bind("<Button-5>", lambda e: rollen(2))
            ziel.bind("<MouseWheel>",
                      lambda e: rollen(-1 if e.delta > 0 else 1))

    innen.leinwand = leinwand
    innen.rollleiste = rolle
    return innen
